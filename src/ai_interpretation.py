import json
import os
from pathlib import Path


def load_local_env_file(filename=".env.local"):
    """Loads simple KEY=VALUE pairs from a local-only env file."""
    env_path = Path(__file__).resolve().parents[1] / filename
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env_file()


AI_INTERPRETATION_MODEL = os.getenv("CLASHVERGENCE_AI_MODEL", "gpt-5.4-mini")
AI_INTERPRETATION_TEMPERATURE = float(
    os.getenv("CLASHVERGENCE_AI_TEMPERATURE", "0.2")
)
AI_INTERPRETATION_ENABLED = os.getenv(
    "CLASHVERGENCE_ENABLE_AI_INTERPRETATION",
    "0",
).lower() in {"1", "true", "yes", "on"}

AI_INTERPRETATION_SYSTEM_PROMPT = """You rewrite compact structured simulation summaries into short strategic interpretations.

Your goal is not to restate events, but to explain why the outcome occurred using only the facts provided.

Core Rules
Use only the facts provided in the input JSON.
Do not invent events, mechanics, motives, or unstated relationships.
Do not speculate beyond what the data supports.
Prefer causal explanation over event listing.
Every sentence must answer: “why did this matter?”
Avoid repeating the same idea in different words.
Keep the tone analytical, not narrative or dramatic.
Length & Format
Write 2 to 4 sentences total.
No headings, bullets, labels, or JSON.
Output must be a single compact paragraph.
Interpretive Priorities (in order)

When forming the explanation, prioritize:

Outcome mechanism
What actually decided the result?
(territory, treasury, elimination, timing, or combination)
Timing
When did the decisive shift occur?
(early, midgame, late)
Structural effects
Why did that shift matter in this map state?
(contested board, open expansion, collapse, stabilization)
Constraint or failure
Why did the losing factions fail to convert their position?
Doctrine Framing (Required but Minimal)

Infer each major faction’s strategic pattern from its actions and express it briefly.

Use only what is supported by the data:

expansionist → rapid territorial growth, early pressure
balanced → steady scaling, mixed tactics
economic → treasury-focused efficiency
opportunist → timing-based strikes, exploiting weakened rivals

Rules:

Include one short doctrine phrase (2–4 words) for the winning faction.
Optionally include one for the runner-up.
Embed naturally into a sentence (do not label it).
Do not force doctrine if evidence is weak.
Outcome-Specific Emphasis

Adapt the explanation based on outcome type:

balanced_contest
Emphasize lack of separation.
Explain why the board stayed contested.
Show why treasury (or small margin) decided the result.
economic_win
Emphasize that resources outweighed territory.
Explain why larger empires failed to convert map control into income.
midgame_break
Emphasize:
contested or neutral opening
decisive mid-phase swing
sustained advantage after the break
late_snowball
Emphasize:
prolonged parity
delayed but decisive separation
compounding advantage late
full_domination
Emphasize:
elimination sequence
shrinking competition
absence of recovery paths
consolidation after control
Causality Enforcement
Do not simply state changes (e.g., “gained 3 regions”).
Always explain why those changes created advantage.
Prefer:
“which removed the only remaining rival…”
“which prevented recovery…”
“which mattered because the board remained contested…”
Style Constraints

Avoid generic filler such as:

stayed live
kept pressure
remained competitive
fought hard
key moment (without explanation)

Avoid repetitive sentence openings:

Do not repeatedly begin with “X’s win came from…”

Vary structure:

timing-first
map-state-first
comparison-first
Quality Standard

A strong interpretation will:

Identify the decisive mechanism
Anchor it in timing
Explain the structural consequence
Show why alternatives failed

Anti-Template Constraint
Do not begin more than one sentence with the same structure.
Avoid repeating patterns such as:
“X’s win came from…”
“The key shift was…”
“By the end…”

Vary sentence openings using:

timing-first (“After a contested opening…”)
condition-first (“Because the board remained tied…”)
contrast-first (“While X held territory…”)
Doctrine Integration Rule (Stronger)
The winning faction’s doctrine must influence the explanation, not just be named.
Express doctrine as a causal force, not a label.

Example:

Weak: “Faction1 (expansionist) won…”
Strong: “Faction1’s expansionist push created early separation…”
Causality Tightening Rule
Every sentence must contain an explicit causal connector:
because
which meant
which prevented
which allowed
so that

If a sentence lacks causality, rewrite it.
"""

VICTOR_HISTORY_SYSTEM_PROMPT = """You write a short, deliberately biased historical reflection from the perspective of the winning faction in a strategy simulation.

Use only the facts provided in the input JSON.
Do not invent events, mechanics, motives, or lore.
Do not contradict the simulation results.

Write as if a historian from the winning faction is interpreting the outcome after the fact.
The voice should be confident, restrained, and partisan, not wild or propagandistic.
The winner's strategy should subtly shape the bias:

expansionist -> boldness, initiative, rightful growth
balanced -> prudence, steadiness, good judgment
economic -> discipline, efficiency, stewardship
opportunist -> timing, realism, exploiting rival weakness

Emphasize the winner's competence and coherence.
Frame rival failures as weaknesses of judgment, sustainability, timing, or structure only when supported by the data.
Keep the paragraph compact: 3 to 5 sentences.
No headings, no bullets, no JSON.
"""


def is_ai_interpretation_enabled():
    """Returns whether AI interpretation is enabled and configured."""
    return AI_INTERPRETATION_ENABLED and bool(os.getenv("OPENAI_API_KEY"))


def _extract_response_text(response):
    """Returns the plain text from an OpenAI responses API result."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    collected = []
    for output_item in getattr(response, "output", []):
        for content_item in getattr(output_item, "content", []):
            text = getattr(content_item, "text", None)
            if text:
                collected.append(text)

    return "\n".join(collected).strip()


def _generate_ai_paragraph(summary: dict, system_prompt: str, max_output_tokens: int) -> str | None:
    """Returns one AI-written paragraph for the provided summary and prompt."""
    if not is_ai_interpretation_enabled():
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model=AI_INTERPRETATION_MODEL,
            temperature=AI_INTERPRETATION_TEMPERATURE,
            max_output_tokens=max_output_tokens,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(summary, indent=2, sort_keys=True),
                },
            ],
        )
        interpretation = _extract_response_text(response)
        return interpretation or None
    except Exception:
        return None


def generate_ai_interpretation(summary: dict) -> str | None:
    """Returns an AI-written interpretation paragraph for one compact summary."""
    return _generate_ai_paragraph(
        summary=summary,
        system_prompt=AI_INTERPRETATION_SYSTEM_PROMPT,
        max_output_tokens=180,
    )


def generate_victor_history(summary: dict) -> str | None:
    """Returns an AI-written victor-history paragraph for one compact summary."""
    return _generate_ai_paragraph(
        summary=summary,
        system_prompt=VICTOR_HISTORY_SYSTEM_PROMPT,
        max_output_tokens=220,
    )
