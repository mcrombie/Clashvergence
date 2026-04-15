from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import asdict
from difflib import SequenceMatcher

from src.ai_interpretation import _extract_response_text, load_local_env_file
from src.models import FactionIdentity


load_local_env_file()


AI_FACTION_NAMING_MODEL = os.getenv("CLASHVERGENCE_FACTION_NAME_MODEL", "gpt-5.4-mini")
AI_FACTION_NAMING_TEMPERATURE = float(
    os.getenv("CLASHVERGENCE_FACTION_NAME_TEMPERATURE", "0.5")
)
AI_FACTION_NAMING_MAX_ATTEMPTS = max(
    1,
    int(os.getenv("CLASHVERGENCE_FACTION_NAME_MAX_ATTEMPTS", "3")),
)
AI_FACTION_NAMING_ENABLED = os.getenv(
    "CLASHVERGENCE_ENABLE_AI_FACTION_NAMING",
    "0",
).lower() in {"1", "true", "yes", "on"}

DEFAULT_GOVERNMENT_TYPE = "Tribe"

SOURCE_TRADITIONS = {
    "roman": {
        "label": "Roman and Gallic ethnonyms",
        "primary_sources": [
            "Julius Caesar, De Bello Gallico",
            "Tacitus, Germania",
            "Livy, Ab Urbe Condita",
        ],
        "seed_names": [
            "Arverni",
            "Aedui",
            "Sequani",
            "Helvetii",
            "Veneti",
            "Carnutes",
            "Lingones",
            "Remi",
            "Senones",
            "Batavi",
        ],
        "onsets": ["al", "ar", "bel", "car", "dur", "hel", "ling", "mar", "nor", "sev", "tal", "ver"],
        "middles": ["ae", "an", "er", "ev", "il", "on", "or", "ut", "av", "en", "ur", "ed"],
        "suffixes": ["and", "ar", "en", "ent", "ern", "ev", "on", "or", "os", "um", "un", "yn"],
    },
    "persian": {
        "label": "Achaemenid and Iranian ethnonyms",
        "primary_sources": [
            "Herodotus, Histories",
            "Behistun Inscription",
            "Xenophon, Cyropaedia",
        ],
        "seed_names": [
            "Persa",
            "Mada",
            "Parthava",
            "Bakhtri",
            "Saka",
            "Dahae",
            "Arachosia",
            "Drangiana",
            "Hyrcania",
            "Carmania",
        ],
        "onsets": ["akh", "ara", "ard", "bakh", "car", "dar", "far", "hyr", "par", "sak", "var", "zar"],
        "middles": ["a", "ae", "ar", "ax", "eh", "ir", "or", "th", "ush", "ava", "ian", "yra"],
        "suffixes": ["ad", "ae", "akh", "an", "and", "ar", "ash", "ava", "ax", "ir", "or", "ush"],
    },
    "chinese": {
        "label": "Classical Chinese state and people names",
        "primary_sources": [
            "Sima Qian, Shiji",
            "Zuo Zhuan",
            "Guoyu",
        ],
        "seed_names": [
            "Qin",
            "Chu",
            "Qi",
            "Wei",
            "Han",
            "Zhao",
            "Yan",
            "Yue",
            "Liang",
            "Jin",
        ],
        "onsets": ["an", "chu", "han", "jin", "lan", "lin", "qin", "shan", "wei", "yan", "yue", "zhao"],
        "middles": ["a", "ai", "en", "i", "ia", "in", "iu", "o", "ua", "ui", "un", "y"],
        "suffixes": ["an", "en", "ei", "ian", "in", "ing", "iu", "ong", "uan", "un", "uo", "yn"],
    },
}

REAL_NAME_BLOCKLIST = sorted({
    normalized
    for tradition in SOURCE_TRADITIONS.values()
    for normalized in tradition["seed_names"]
})

AI_FACTION_NAMING_SYSTEM_PROMPT = """You create one original alternative-history culture name inspired by ancient primary-source naming traditions.

Rules:
- Output exactly one culture base name and nothing else.
- The name must be a single word in Title Case.
- It should sound plausible beside ancient Roman, Persian, and Chinese ethnonyms without copying any one directly.
- Do not output a real historical ethnonym, kingdom, tribe, dynasty, or state name.
- Avoid spaces, punctuation, numbers, articles, and government words like Tribe, League, Kingdom, Empire, Republic.
- Keep it pronounceable in English.
- Prefer 6 to 11 letters.
- Make it feel like the name of a people or culture, not a person.
- Avoid overly jagged spellings with too many rare letters like q, x, z, or j unless the result still sounds smooth aloud.
- Prefer names that look natural in English transliteration.
"""


def is_ai_faction_naming_enabled():
    return AI_FACTION_NAMING_ENABLED and bool(os.getenv("OPENAI_API_KEY"))


def get_faction_internal_id(index: int) -> str:
    return f"Faction{index}"


def get_configured_faction_internal_ids(num_factions: int) -> list[str]:
    if num_factions < 1:
        raise ValueError("num_factions must be at least 1.")
    return [get_faction_internal_id(index) for index in range(1, num_factions + 1)]


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())


def _stable_random(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _blend_fragments(rng: random.Random, first: str, second: str) -> str:
    blend_size = min(len(first), max(2, len(first) // 2 + rng.randint(0, 1)))
    tail_start = min(len(second), max(1, len(second) // 2 - rng.randint(0, 1)))
    return first[:blend_size] + second[tail_start:]


def _extract_seed_fragments(seed_name: str) -> list[str]:
    normalized = _normalize_name(seed_name)
    if len(normalized) < 4:
        return [normalized]

    fragments = [
        normalized[:3],
        normalized[:4],
        normalized[-3:],
        normalized[-4:],
        normalized[1:4],
        normalized[max(0, len(normalized) // 2 - 2): max(3, len(normalized) // 2 + 2)],
    ]

    unique_fragments: list[str] = []
    for fragment in fragments:
        if len(fragment) >= 2 and fragment not in unique_fragments:
            unique_fragments.append(fragment)
    return unique_fragments


def _collapse_repeated_letters(value: str) -> str:
    return re.sub(r"(.)\1{2,}", r"\1\1", value)


def _clean_letter_transitions(value: str) -> str:
    value = value.lower()

    for pattern, replacement in (
        ("qj", "qu"),
        ("jq", "qu"),
        ("yy", "y"),
        ("ww", "w"),
        ("iii", "ii"),
        ("uuu", "uu"),
        ("aeo", "ae"),
        ("eoa", "ea"),
        ("iua", "ia"),
    ):
        value = value.replace(pattern, replacement)

    value = re.sub(r"([bcdfghjklmnpqrstvwxyz]{4,})", lambda match: match.group(0)[:3], value)
    value = re.sub(r"([aeiouy]{3,})", lambda match: match.group(0)[:2], value)
    return _collapse_repeated_letters(value)


def _tidy_candidate(candidate: str) -> str:
    candidate = re.sub(r"[^a-z]", "", candidate.lower())
    candidate = _clean_letter_transitions(candidate)
    if len(candidate) < 5:
        candidate += "an"
    if len(candidate) > 11:
        candidate = candidate[:11]
    return candidate.capitalize()


def _is_too_similar(candidate: str, blocked_names: list[str], threshold: float = 0.8) -> bool:
    normalized = _normalize_name(candidate)
    if not normalized:
        return True

    for blocked in blocked_names:
        blocked_normalized = _normalize_name(blocked)
        if normalized == blocked_normalized:
            return True
        if abs(len(normalized) - len(blocked_normalized)) <= 2:
            ratio = SequenceMatcher(None, normalized, blocked_normalized).ratio()
            if ratio >= threshold:
                return True
    return False


def _generate_source_fused_candidate(index: int, naming_seed: str, attempt: int = 0) -> tuple[str, list[str], list[str]]:
    tradition_keys = sorted(SOURCE_TRADITIONS)
    rng = _stable_random(f"{naming_seed}:{index}:{attempt}")

    first_key = tradition_keys[(index + attempt) % len(tradition_keys)]
    second_key = tradition_keys[(index + attempt + 1 + rng.randint(0, len(tradition_keys) - 1)) % len(tradition_keys)]
    if first_key == second_key:
        second_key = tradition_keys[(tradition_keys.index(first_key) + 1) % len(tradition_keys)]

    first = SOURCE_TRADITIONS[first_key]
    second = SOURCE_TRADITIONS[second_key]

    onset = rng.choice(first["onsets"])
    middle = rng.choice(second["middles"])
    suffix = rng.choice(first["suffixes"] + second["suffixes"])
    seed_a = rng.choice(first["seed_names"])
    seed_b = rng.choice(second["seed_names"])
    seed_a_fragments = _extract_seed_fragments(seed_a)
    seed_b_fragments = _extract_seed_fragments(seed_b)

    fused = _blend_fragments(rng, _normalize_name(seed_a), _normalize_name(seed_b))
    fragment_a = rng.choice(seed_a_fragments)
    fragment_b = rng.choice(seed_b_fragments)
    pattern = rng.choice(("onset_fused_suffix", "seed_blend", "hybrid_compound", "softened_seed"))

    if pattern == "onset_fused_suffix":
        candidate = onset + middle + fused[-max(2, len(fused) // 2):] + suffix[: rng.randint(1, len(suffix))]
    elif pattern == "seed_blend":
        candidate = fragment_a + middle + fragment_b[-max(2, len(fragment_b) - 1):]
    elif pattern == "hybrid_compound":
        candidate = onset + fragment_b[: rng.randint(2, len(fragment_b))] + suffix
    else:
        candidate = fragment_a[: rng.randint(2, len(fragment_a))] + fused[max(1, len(fused) // 3):] + suffix[:2]

    if rng.random() < 0.45:
        candidate += rng.choice(["a", "e", "i", "o", "u", "an", "en", "ar"])

    return _tidy_candidate(candidate), [first_key, second_key], [seed_a, seed_b]


def _count_vowels(value: str) -> int:
    return sum(1 for character in value.lower() if character in "aeiouy")


def _score_candidate_quality(candidate: str) -> float:
    normalized = _normalize_name(candidate)
    if not normalized:
        return -999.0

    vowel_count = _count_vowels(normalized)
    consonant_count = len(normalized) - vowel_count
    vowel_ratio = vowel_count / max(1, len(normalized))

    score = 0.0
    score -= abs(len(normalized) - 8) * 0.25
    score -= abs(vowel_ratio - 0.42) * 2.5

    if normalized.endswith(("a", "an", "ar", "and", "en", "ia", "ian", "in", "ion", "on", "or", "os", "thi", "un")):
        score += 0.8
    if re.search(r"[aeiouy]{2}", normalized):
        score += 0.35
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{3}", normalized):
        score -= 0.35
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{4}", normalized):
        score -= 1.0

    awkward_clusters = (
        "akhm",
        "hmg",
        "rrtn",
        "tnet",
        "xn",
        "qz",
        "zx",
        "jq",
        "qj",
        "vvr",
        "yy",
    )
    for cluster in awkward_clusters:
        if cluster in normalized:
            score -= 1.4

    rare_letter_count = sum(normalized.count(letter) for letter in "qxzj")
    score -= rare_letter_count * 0.2
    if rare_letter_count >= 3:
        score -= 0.8
    score -= len(re.findall(r"q(?!u)", normalized)) * 0.9

    repeated_pairs = len(re.findall(r"(..).*\1", normalized))
    score += min(0.7, repeated_pairs * 0.15)

    if consonant_count > vowel_count + 3:
        score -= 0.9

    return score


def _generate_deterministic_culture_name(index: int, naming_seed: str, existing_names: list[str]) -> tuple[str, list[str], list[str], list[str]]:
    blocked = REAL_NAME_BLOCKLIST + existing_names
    candidates: list[tuple[float, str, list[str], list[str]]] = []

    for attempt in range(48):
        candidate, traditions, inspirations = _generate_source_fused_candidate(index, naming_seed, attempt=attempt)
        if _is_too_similar(candidate, blocked):
            continue
        candidates.append((
            _score_candidate_quality(candidate),
            candidate,
            traditions,
            inspirations,
        ))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, best_candidate, traditions, inspirations = candidates[0]
        candidate_pool = [candidate for _score, candidate, _traditions, _inspirations in candidates[:8]]
        return best_candidate, traditions, inspirations, candidate_pool

    fallback_base, fallback_traditions, fallback_inspirations = _generate_source_fused_candidate(
        index,
        naming_seed,
        attempt=99,
    )
    fallback = f"{fallback_base}{chr(65 + (index - 1) % 26)}"
    return fallback, fallback_traditions, fallback_inspirations, [fallback]


def _validate_ai_candidate(candidate: str, blocked_names: list[str]) -> str | None:
    cleaned = re.sub(r"[^A-Za-z]", "", candidate or "")
    if not cleaned:
        return None
    if len(cleaned) < 5 or len(cleaned) > 11:
        return None
    cleaned = cleaned.capitalize()
    if _is_too_similar(cleaned, blocked_names):
        return None
    return cleaned


def _passes_ai_quality_gate(candidate: str, fallback_candidate: str) -> bool:
    ai_score = _score_candidate_quality(candidate)
    fallback_score = _score_candidate_quality(fallback_candidate)

    minimum_ai_score = -0.15
    relative_floor = fallback_score - 1.3
    return ai_score >= minimum_ai_score and ai_score >= relative_floor


def _generate_ai_culture_name(index: int, naming_seed: str, blocked_names: list[str], candidate_pool: list[str], traditions: list[str], fallback_candidate: str) -> str | None:
    if not is_ai_faction_naming_enabled():
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        rejected_candidates: list[str] = []

        for attempt in range(AI_FACTION_NAMING_MAX_ATTEMPTS):
            prompt_payload = {
                "faction_index": index,
                "naming_seed": naming_seed,
                "attempt": attempt + 1,
                "traditions": [SOURCE_TRADITIONS[key]["label"] for key in traditions],
                "candidate_pool": candidate_pool[:6],
                "fallback_candidate": fallback_candidate,
                "blocked_names": blocked_names[:30],
                "rejected_candidates": rejected_candidates,
                "source_examples": {
                    key: SOURCE_TRADITIONS[key]["seed_names"][:6]
                    for key in traditions
                },
            }

            response = client.responses.create(
                model=AI_FACTION_NAMING_MODEL,
                temperature=AI_FACTION_NAMING_TEMPERATURE,
                max_output_tokens=30,
                input=[
                    {"role": "system", "content": AI_FACTION_NAMING_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(prompt_payload, sort_keys=True)},
                ],
            )
            proposed = _extract_response_text(response)
            validated = _validate_ai_candidate(proposed, blocked_names + rejected_candidates)
            if validated is None:
                if proposed:
                    rejected_candidates.append(proposed)
                continue
            if _passes_ai_quality_gate(validated, fallback_candidate):
                return validated
            rejected_candidates.append(validated)
    except Exception:
        return None

    return None


def generate_faction_identity(index: int, naming_seed: str = "default", existing_culture_names: list[str] | None = None) -> FactionIdentity:
    existing_culture_names = existing_culture_names or []
    culture_name, traditions, inspirations, candidate_pool = _generate_deterministic_culture_name(
        index=index,
        naming_seed=naming_seed,
        existing_names=existing_culture_names,
    )
    blocked = REAL_NAME_BLOCKLIST + existing_culture_names
    ai_candidate = _generate_ai_culture_name(
        index=index,
        naming_seed=naming_seed,
        blocked_names=blocked,
        candidate_pool=candidate_pool,
        traditions=traditions,
        fallback_candidate=culture_name,
    )
    final_culture_name = ai_candidate or culture_name
    return FactionIdentity(
        internal_id=get_faction_internal_id(index),
        culture_name=final_culture_name,
        government_type=DEFAULT_GOVERNMENT_TYPE,
        source_traditions=traditions,
        generation_method="ai_fused_sources" if ai_candidate else "curated_source_fusion",
        ai_generated=bool(ai_candidate),
        inspirations=inspirations,
        candidate_pool=candidate_pool[:8],
    )


def generate_faction_identities(num_factions: int, naming_seed: str = "default") -> list[FactionIdentity]:
    identities = []
    existing_culture_names: list[str] = []

    for index in range(1, num_factions + 1):
        identity = generate_faction_identity(
            index=index,
            naming_seed=naming_seed,
            existing_culture_names=existing_culture_names,
        )
        identities.append(identity)
        existing_culture_names.append(identity.culture_name)

    return identities


def serialize_faction_identity(identity: FactionIdentity) -> dict:
    return asdict(identity)
