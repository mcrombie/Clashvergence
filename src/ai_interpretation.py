from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re

from src.calendar import get_snapshot_season_name, get_snapshot_year
from src.metrics import analyze_competition_metrics
from src.narrative import (
    summarize_faction_epilogues,
    summarize_final_standings,
    summarize_phases,
    summarize_strategic_interpretation,
    summarize_structural_drivers,
    summarize_turning_points,
    summarize_victor_history,
)
from src.region_naming import format_region_reference


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
    os.getenv("CLASHVERGENCE_AI_TEMPERATURE", "0.45")
)
AI_INTERPRETATION_MAX_OUTPUT_TOKENS = int(
    os.getenv("CLASHVERGENCE_AI_MAX_OUTPUT_TOKENS", "4200")
)
VICTOR_HISTORY_MAX_OUTPUT_TOKENS = int(
    os.getenv("CLASHVERGENCE_VICTOR_HISTORY_MAX_OUTPUT_TOKENS", "220")
)
AI_INTERPRETATION_ENABLED = os.getenv(
    "CLASHVERGENCE_ENABLE_AI_INTERPRETATION",
    "0",
).lower() in {"1", "true", "yes", "on"}

AI_INTERPRETATION_SYSTEM_PROMPT = """You are an eccentric historian from a different world, writing a long chronicle of a simulated age.

You are given structured simulation data. Your task is to turn it into a vivid, specific, historically flavored narrative that feels like a real world remembered by later generations.

Non-negotiable grounding rules
- Use only the named factions, regions, turns, relationships, outcomes, and event patterns present in the data.
- Do not invent facts that contradict the data.
- Do not create wars, rulers, cities, religions, betrayals, or treaties unless the data supports them.
- You may add atmospheric texture, emotional color, and interpretive language so long as the factual spine remains grounded in the input.
- If the data says a faction had only one region, do not write as though it ruled a continent.
- Prefer region display names over coordinate codes. Use raw coordinate codes only sparingly and usually parenthetically, if at all.
- Prefer the supplied world name and calendrical system over raw turn counts. Raw turns may appear occasionally in parentheses, but the main chronology should feel like an in-world annal.

What to write
- Write a long-form narrative history, around 1800 to 3200 words.
- Use 10 to 18 paragraphs.
- No headings, no bullets, no JSON.
- Make it pleasurable to read: elegant, concrete, observant, and dramatic in a restrained way.

Narrative architecture
- Give the history a shape:
  opening world
  3 to 5 centerpiece episodes
  late settlement, exhaustion, or transformation
- Use the phase event digest and centerpiece episodes as anchors.
- Use the world identity, chronology, religion digest, succession digest, and vignette cues as primary raw material rather than treating them as optional flavor.
- Linger on a few decisive scenes instead of summarizing every fact at the same altitude.
- If many similar events occur, identify the pattern but then dramatize 2 or 3 representative cases with concrete names, turns, and stakes.
- Include 2 to 4 short vignettes embedded naturally in the prose: a court scene, a shrine reform, a refugee road, a tributary submission, a contested succession, a frontier town, or similar moments grounded in the supplied data.

Narrative priorities
1. Build a real arc from opening, to middle struggle, to late settlement or collapse.
2. Zero in on key events rather than speaking only in abstractions.
3. Follow named factions across time. Show who rose, who fragmented, who endured, and who vanished.
4. Use the event digest and elimination data heavily. Those are your best raw materials.
5. Explain why the world changed, not just that it changed.
6. Make religion and dynastic succession feel like lived political forces, not afterthoughts.

Specificity requirements
- Mention at least 10 concrete details from the data, such as named factions, turns, regions, rivalries, tributary settlements, secessions, migrations, reforms, eliminations, or faction epilogues.
- Mention at least 8 specific events from the event digests.
- Mention calendar years regularly. You may mention turns when useful, especially for decisive breaks or late reversals, but the dominant chronology should be the supplied reckoning.
- If migration pressure is high, make population movement feel historically consequential rather than statistical wallpaper.
- If rebellions and successor states dominate the run, make the world feel politically splintered and genealogically tangled.
- Use the successor lineages when they exist. Make parent polities and their breakaways feel historically connected.
- Use the rivalry digest when it exists. Make repeated rivalries feel like long feuds rather than isolated datapoints.
- If an elimination cascade appears, narrate it as a sequence with texture and consequence.
- If religion data is present, describe cults, reforms, sacred geographies, clergy backing, or legitimacy struggles in concrete terms.
- If succession data is present, describe dynasties, heirs, rival claimants, regencies, prestige, and court tension in concrete terms.
- If a faction or doctrine has a narrative alias or gloss, prefer that phrasing over the most mechanical label.

Style requirements
- Write like a historian with taste, not a game log.
- Vary sentence rhythm.
- Prefer concrete imagery tied to the supplied facts: roads, riverlands, courts, frontier marches, tribute chains, exhausted cores, refugee roads, fortified junctions, emptied homelands.
- Avoid generic filler like "things changed rapidly" or "many challenges emerged."
- Do not simply restate the provided summary lines in order.
- Do not spend too many sentences repeating treasury numbers alone. Translate economic dominance into visible consequences.
- When development dominates the age, describe what that development meant on the ground: granaries, roads, markets, storehouses, irrigated valleys, tax capacity, military endurance, or administrative reach.
- Let the world feel named and inhabited. Use the supplied world name, era name, faith names, dynastic houses, and region display names until the reader feels oriented inside a real place.
- End with a complete final paragraph that closes the age. Do not stop mid-sentence or end abruptly.

Interpretive stance
- Treat the simulation as a real historical record.
- Use creative detail to make the world feel inhabited, but keep every major claim anchored in the data.
- When you infer meaning, make the inference feel historically plausible and tied to the evidence provided.
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


def is_ai_interpretation_enabled(*, enabled_override: bool | None = None):
    """Returns whether AI interpretation is enabled and configured."""
    enabled = AI_INTERPRETATION_ENABLED if enabled_override is None else enabled_override
    return enabled and bool(os.getenv("OPENAI_API_KEY"))


def _display_name(world, faction_name: str | None) -> str | None:
    if faction_name is None:
        return None
    faction = world.factions.get(faction_name)
    if faction is None:
        return faction_name
    return faction.display_name


def _stable_int(seed_text: str) -> int:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _choose_stable(options: list[str], seed_text: str) -> str:
    if not options:
        raise ValueError("Expected at least one option.")
    return options[_stable_int(seed_text) % len(options)]


def _clean_root_name(value: str | None) -> str:
    text = re.sub(
        r"\b(Band|Tribe|Chiefdom|State|Kingdom|Republic|Oligarchy|League|Realm|Crown|Rebels?)\b",
        "",
        value or "",
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\b\d+\b", "", text)
    text = re.sub(r"[^A-Za-z\s]", " ", text)
    tokens = [token for token in text.split() if token]
    if not tokens:
        return "Convergence"
    return max(tokens, key=len)


def _region_reference(world, region_name: str | None, *, include_code: bool = False) -> str | None:
    if not region_name:
        return None
    region = world.regions.get(region_name)
    if region is None:
        return region_name
    return format_region_reference(region, include_code=include_code)


def _ordinal(value: int) -> str:
    suffix = "th"
    if value % 100 not in {11, 12, 13}:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _map_feature_label(map_name: str) -> str:
    lowered = (map_name or "").lower()
    if "ring" in lowered:
        return "Ring"
    if "basin" in lowered:
        return "Basin"
    if "frontier" in lowered:
        return "Marches"
    if "archipelago" in lowered:
        return "Isles"
    if "highland" in lowered:
        return "Highlands"
    if "continent" in lowered:
        return "Continent"
    return "World"


def _build_world_identity(world) -> dict:
    roots = []
    for faction in sorted(world.factions.values(), key=lambda item: item.display_name):
        roots.extend(
            [
                _clean_root_name(faction.primary_ethnicity),
                _clean_root_name(faction.culture_name),
                _clean_root_name(faction.display_name),
            ]
        )
        religion_name = getattr(faction.religion, "official_religion", "")
        if religion_name:
            roots.append(_clean_root_name(religion_name))
    roots = [root for root in roots if root]
    if not roots:
        roots = ["Convergence", "Amber", "Stone"]

    seed = f"{world.map_name}|{len(world.regions)}|{len(world.factions)}"
    primary_root = _choose_stable(roots, seed)
    secondary_root = _choose_stable(roots, f"{seed}|secondary")
    tertiary_root = _choose_stable(roots, f"{seed}|tertiary")
    feature_label = _map_feature_label(getattr(world, "map_name", ""))

    world_name_patterns = [
        f"The {primary_root} {feature_label}",
        f"The {primary_root} Circuit",
        f"The {primary_root} Reach",
        f"The {primary_root} Crownlands",
    ]
    world_name = _choose_stable(world_name_patterns, f"{seed}|world_name")

    calendar_suffixes = ["Reckoning", "Annals", "Count", "Calendar", "Measure"]
    calendar_name = f"{secondary_root} {_choose_stable(calendar_suffixes, f'{seed}|calendar')}"

    era_titles = [
        f"Age of {primary_root} and {secondary_root}",
        f"Age of {secondary_root} and {tertiary_root}",
        f"Age of Splintered Crowns",
        f"Age of Roads and Tributaries",
        f"Age of Houses and Altars",
        f"Age of Many Banners",
    ]
    counts = Counter(event.type for event in world.events)
    if counts["religious_reform"] >= 3:
        preferred_era = "Age of Houses and Altars"
    elif counts["unrest_secession"] + counts["rebel_independence"] >= 6:
        preferred_era = "Age of Splintered Crowns"
    elif counts["migration_wave"] + counts["refugee_wave"] >= 12:
        preferred_era = "Age of Roads and Tributaries"
    else:
        preferred_era = None
    era_name = preferred_era or _choose_stable(era_titles, f"{seed}|era")

    return {
        "world_name": world_name,
        "calendar_name": calendar_name,
        "era_name": era_name,
        "feature_label": feature_label,
    }


def _year_label(world_identity: dict, turn_one_based: int) -> str:
    year = get_snapshot_year(turn_one_based)
    season = get_snapshot_season_name(turn_one_based)
    return f"{season} of Year {year} in the {world_identity['calendar_name']}"


def _faction_narrative_name(world, faction_name: str | None) -> str | None:
    if faction_name is None:
        return None
    faction = world.factions.get(faction_name)
    if faction is None:
        return faction_name
    display_name = faction.display_name
    if not faction.is_rebel:
        return display_name

    match = re.match(r"^(.*?)(?:\s+Rebels?)(?:\s+(\d+))?$", display_name)
    base_name = display_name
    ordinal_text = ""
    if match:
        base_name = match.group(1).strip() or display_name
        if match.group(2):
            ordinal_text = f"{_ordinal(int(match.group(2)))} "
    conflict_type = (faction.rebel_conflict_type or "revolt").replace("_", " ")
    if conflict_type == "civil war":
        role = "claimant rising"
    elif conflict_type == "restoration":
        role = "restoration rising"
    else:
        role = "rising"
    return f"the {ordinal_text}{base_name} {role}".strip()


def _doctrine_gloss(faction) -> str:
    terrain = (faction.doctrine_profile.terrain_identity or "mixed country").lower()
    dominant_behavior = (faction.doctrine_profile.dominant_behavior or "adaptive").lower()
    behavior_gloss = {
        "frontier": "a frontier-marching doctrine built for expansion at the edges",
        "insular": "an inward-looking doctrine built around defensible cores",
        "developmental": "a granary-and-market doctrine built on patient development",
        "martial": "a hard-driving war doctrine that prizes decisive force",
        "defensive": "a guarded border doctrine of patient resistance",
        "expansionary": "an outward-driving conquest doctrine",
        "adaptive": "a flexible mixed doctrine that changes with circumstance",
    }.get(dominant_behavior, "a mixed doctrine")
    return f"{behavior_gloss} in {terrain}"


def _phase_label_for_turn(turn_one_based: int, total_turns: int) -> str:
    if total_turns <= 0:
        return "mid"
    early_end = max(1, total_turns // 3)
    mid_end = max(early_end + 1, (2 * total_turns) // 3)
    if turn_one_based <= early_end:
        return "early"
    if turn_one_based <= mid_end:
        return "mid"
    return "late"


def _event_family(event_type: str) -> str:
    if event_type in {"war_declared", "war_peace", "attack"}:
        return "war"
    if event_type in {"unrest_secession", "rebel_independence", "succession", "succession_crisis", "regime_agitation"}:
        return "fracture"
    if event_type in {"diplomacy_tributary", "diplomacy_alliance", "diplomacy_rivalry"}:
        return "diplomacy"
    if event_type in {"migration_wave", "refugee_wave"}:
        return "migration"
    if event_type in {"develop", "invest", "polity_advance", "religious_reform"}:
        return "statecraft"
    if event_type == "expand":
        return "expansion"
    return "other"


def _event_score(event) -> float:
    base_weights = {
        "war_peace": 7.0,
        "unrest_secession": 7.0,
        "rebel_independence": 6.5,
        "succession_crisis": 6.0,
        "war_declared": 5.5,
        "diplomacy_tributary": 5.2,
        "religious_reform": 5.0,
        "polity_advance": 4.8,
        "diplomacy_rivalry": 4.6,
        "attack": 4.5,
        "regime_agitation": 4.2,
        "refugee_wave": 4.0,
        "migration_wave": 3.8,
        "expand": 3.4,
        "succession": 3.3,
        "diplomacy_alliance": 3.2,
        "unrest_crisis": 2.8,
        "develop": 1.6,
        "invest": 1.6,
        "unrest_disturbance": 1.2,
    }
    score = float(event.get("importance_score", 0.0) or 0.0)
    if score <= 0.0:
        score = float(event.significance or 0.0)
    score += base_weights.get(event.type, 0.0)

    if event.type in {"migration_wave", "refugee_wave"}:
        score += min(6.0, float(event.get("population_moved", 0) or 0) / 80.0)
    if event.type == "unrest_secession":
        score += float(event.get("joined_region_count", 0) or 0) * 0.75
    if event.type == "war_peace":
        peace_term = str(event.get("peace_term", ""))
        if peace_term and peace_term != "white_peace":
            score += 1.4
    if event.type == "attack" and event.get("success", False):
        score += 1.5
    if "collapse" in set(event.tags or []):
        score += 1.5
    if "civil_war" in set(event.tags or []):
        score += 1.8

    return round(score, 3)


def _build_event_brief(world, event) -> str:
    world_identity = _build_world_identity(world)
    actor = _faction_narrative_name(world, event.faction) or _display_name(world, event.faction) or "Unknown polity"
    counterpart = _faction_narrative_name(
        world,
        event.get("counterpart")
        or event.get("defender")
        or event.get("loser")
        or event.get("winner")
        or event.get("subordinate")
        or event.get("origin_faction")
        or event.get("rebel_faction")
        or event.get("claimant_faction"),
    ) or _display_name(
        world,
        event.get("counterpart")
        or event.get("defender")
        or event.get("loser")
        or event.get("winner")
        or event.get("subordinate")
        or event.get("origin_faction")
        or event.get("rebel_faction")
        or event.get("claimant_faction"),
    )
    region_name = (
        event.get("region_display_name")
        or _region_reference(world, event.region)
        or _region_reference(world, event.get("claimant_region"))
        or _region_reference(world, event.get("war_target_region"))
    )
    turn_text = _year_label(world_identity, event.turn + 1)

    if event.type == "diplomacy_tributary":
        subordination = str(event.get("subordination_type", "tributary")).replace("_", " ")
        return f"On {turn_text}, {actor} forced {counterpart} into a {subordination} relationship."
    if event.type == "unrest_secession":
        rebel_name = _faction_narrative_name(world, event.get("rebel_faction")) or _display_name(world, event.get("rebel_faction"))
        if rebel_name:
            return f"On {turn_text}, {region_name or 'a province'} broke away from {actor}, beginning {rebel_name}."
        return f"On {turn_text}, {region_name or 'a province'} broke away from {actor}, opening a secession."
    if event.type == "rebel_independence":
        return f"On {turn_text}, {actor} secured independence from {counterpart}."
    if event.type == "diplomacy_rivalry":
        return f"On {turn_text}, {actor} and {counterpart} hardened into rivalry."
    if event.type == "war_declared":
        return f"On {turn_text}, {actor} declared war on {counterpart}."
    if event.type == "war_peace":
        return f"On {turn_text}, the war between {actor} and {counterpart} ended in settlement."
    if event.type == "succession_crisis":
        claimant = _faction_narrative_name(world, event.get("claimant_faction")) or _display_name(world, event.get("claimant_faction"))
        claimant_region = _region_reference(world, event.get("claimant_region"))
        if claimant:
            claimant_region_text = f" from {claimant_region}" if claimant_region else ""
            return f"On {turn_text}, {actor} entered a succession crisis as support gathered behind {claimant}{claimant_region_text}."
        return f"On {turn_text}, {actor} entered a succession crisis."
    if event.type == "succession":
        new_ruler = event.get("new_ruler")
        dynasty = event.get("dynasty_name")
        succession_type = str(event.get("succession_type", "transition")).replace("_", " ")
        ruler_text = f" under {new_ruler}" if new_ruler else ""
        dynasty_text = f" of {dynasty}" if dynasty else ""
        return f"On {turn_text}, {actor} passed through a {succession_type} succession{ruler_text}{dynasty_text}."
    if event.type == "religious_reform":
        old_religion = event.get("old_religion") or "an older rite"
        new_religion = event.get("new_religion") or "a reformed creed"
        return f"On {turn_text}, {actor} broke from {old_religion} and raised {new_religion}."
    if event.type == "polity_advance":
        return f"On {turn_text}, {actor} advanced into a higher polity tier."
    if event.type in {"migration_wave", "refugee_wave"}:
        moved = int(event.get("population_moved", 0) or 0)
        destination = _region_reference(world, event.get("top_destination")) or event.get("top_destination")
        destination_text = f" toward {destination}" if destination else ""
        return f"On {turn_text}, movement from {region_name or 'a troubled province'} sent {moved} people{destination_text}."
    if event.type == "expand":
        return f"On {turn_text}, {actor} claimed {region_name or 'new territory'}."
    if event.type == "attack":
        outcome = "captured" if event.get("success", False) else "assaulted"
        return f"On {turn_text}, {actor} {outcome} {region_name or 'a contested region'}."
    if event.type in {"develop", "invest"}:
        taxable_change = float(event.get("taxable_change", 0.0) or 0.0)
        project_type = str(event.get("project_type", "development")).replace("_", " ")
        return f"On {turn_text}, {actor} improved {region_name or 'its core'} through {project_type}, shifting taxable value by {taxable_change:.2f}."
    return f"On {turn_text}, {actor} experienced a {event.type.replace('_', ' ')} event."


def _build_key_event_digest(world, *, limit: int = 24) -> list[dict]:
    world_identity = _build_world_identity(world)
    selected_types = {
        "expand",
        "attack",
        "develop",
        "invest",
        "war_declared",
        "war_peace",
        "unrest_secession",
        "rebel_independence",
        "succession",
        "succession_crisis",
        "religious_reform",
        "polity_advance",
        "regime_agitation",
        "migration_wave",
        "refugee_wave",
        "diplomacy_tributary",
        "diplomacy_alliance",
        "diplomacy_rivalry",
    }
    event_rows = []
    for event in world.events:
        if event.type not in selected_types:
            continue
        actor_name = _display_name(world, event.faction)
        region_name = event.region or event.get("claimant_region") or event.get("war_target_region")
        row = {
            "turn": event.turn + 1,
            "year_label": _year_label(world_identity, event.turn + 1),
            "type": event.type,
            "actor": actor_name,
            "actor_narrative": _faction_narrative_name(world, event.faction) or actor_name,
            "region": region_name,
            "region_display_name": event.get("region_display_name") or _region_reference(world, region_name),
            "region_reference": _region_reference(world, region_name, include_code=True),
            "counterpart": _display_name(
                world,
                event.get("counterpart")
                or event.get("defender")
                or event.get("loser")
                or event.get("winner")
                or event.get("subordinate")
                or event.get("origin_faction")
                or event.get("rebel_faction")
                or event.get("claimant_faction"),
            ),
            "counterpart_narrative": _faction_narrative_name(
                world,
                event.get("counterpart")
                or event.get("defender")
                or event.get("loser")
                or event.get("winner")
                or event.get("subordinate")
                or event.get("origin_faction")
                or event.get("rebel_faction")
                or event.get("claimant_faction"),
            ),
            "score": _event_score(event),
            "tags": list(event.tags or []),
            "brief": _build_event_brief(world, event),
            "details": {},
        }

        detail_keys = (
            "peace_term",
            "war_objective_label",
            "war_objective",
            "joined_region_count",
            "conflict_type",
            "successor_ethnicity",
            "old_religion",
            "new_religion",
            "old_polity_tier",
            "new_polity_tier",
            "new_government_type",
            "project_type",
            "resource_focus",
            "taxable_change",
            "population_moved",
            "top_destination",
            "new_ruler",
            "old_ruler",
            "dynasty_name",
            "old_dynasty",
            "succession_type",
            "legitimacy",
            "claimant_pressure",
            "claimant_region",
            "claimant_faction",
            "parent_religion",
        )
        for key in detail_keys:
            value = event.get(key)
            if value not in (None, "", [], {}):
                if key in {"top_destination", "claimant_region"}:
                    row["details"][key] = _region_reference(world, value) or value
                elif key == "claimant_faction":
                    row["details"][key] = _faction_narrative_name(world, value) or _display_name(world, value) or value
                else:
                    row["details"][key] = value

        event_rows.append(row)

    event_rows.sort(
        key=lambda item: (
            item["score"],
            -item["turn"],
        ),
        reverse=True,
    )
    selected = []
    family_counts = Counter()
    actor_counts = Counter()
    for row in event_rows:
        family = _event_family(row["type"])
        family_limit = {
            "diplomacy": 5,
            "migration": 4,
            "statecraft": 5,
            "fracture": 5,
            "war": 4,
            "expansion": 4,
        }.get(family, 3)
        if family_counts[family] >= family_limit:
            continue
        if actor_counts[row["actor"]] >= 4:
            continue
        selected.append(row)
        family_counts[family] += 1
        actor_counts[row["actor"]] += 1
        if len(selected) >= limit:
            break
    return selected


def _build_phase_event_digest(world, *, per_phase_limit: int = 5) -> dict[str, list[dict]]:
    total_turns = max(int(world.turn), 1)
    grouped: dict[str, list[dict]] = {"early": [], "mid": [], "late": []}
    for row in _build_key_event_digest(world, limit=48):
        phase = _phase_label_for_turn(int(row["turn"]), total_turns)
        grouped[phase].append(row)

    trimmed = {}
    for phase, rows in grouped.items():
        family_counts = Counter()
        chosen = []
        for row in rows:
            family = _event_family(row["type"])
            if family_counts[family] >= 2:
                continue
            chosen.append(row)
            family_counts[family] += 1
            if len(chosen) >= per_phase_limit:
                break
        trimmed[phase] = chosen
    return trimmed


def _build_elimination_digest(world, competition: dict, world_identity: dict) -> list[dict]:
    eliminations = []
    for faction_name, data in competition.get("eliminations", {}).items():
        if not data.get("eliminated"):
            continue
        eliminations.append(
            {
                "faction": _display_name(world, faction_name) or faction_name,
                "faction_narrative": _faction_narrative_name(world, faction_name) or _display_name(world, faction_name) or faction_name,
                "turn": data.get("turn"),
                "year_label": _year_label(world_identity, data.get("turn")),
            }
        )
    eliminations.sort(key=lambda item: item["turn"] or 10**9)
    return eliminations


def _build_religion_digest(world, world_identity: dict, factions: list[dict]) -> dict:
    adherent_counts: Counter[str] = Counter()
    dominant_region_counts: Counter[str] = Counter()
    sacred_region_counts: Counter[str] = Counter()
    official_factions: dict[str, list[str]] = {}

    for region in world.regions.values():
        for religion_name, count in (region.religious_composition or {}).items():
            adherent_counts[religion_name] += int(count or 0)
        if region.religious_composition:
            dominant = max(
                region.religious_composition.items(),
                key=lambda item: (item[1], item[0]),
            )[0]
            dominant_region_counts[dominant] += 1
        if region.sacred_religion:
            sacred_region_counts[region.sacred_religion] += 1

    for faction in factions:
        religion_name = faction.get("official_religion")
        if religion_name:
            official_factions.setdefault(religion_name, []).append(faction["display_name"])

    religions = []
    for religion_name, religion in world.religions.items():
        religions.append(
            {
                "name": religion_name,
                "adherents": adherent_counts.get(religion_name, 0),
                "dominant_regions": dominant_region_counts.get(religion_name, 0),
                "sacred_regions": sacred_region_counts.get(religion_name, 0),
                "official_factions": sorted(official_factions.get(religion_name, [])),
                "founding_faction": _display_name(world, religion.founding_faction),
                "parent_religion": religion.parent_religion,
                "doctrine": religion.doctrine,
                "sacred_terrain": list(religion.sacred_terrain_tags or []),
                "sacred_climate": religion.sacred_climate,
                "reform_origin_year": _year_label(world_identity, religion.reform_origin_turn + 1)
                if religion.reform_origin_turn is not None
                else None,
            }
        )

    religions.sort(
        key=lambda item: (
            item["adherents"],
            item["dominant_regions"],
            len(item["official_factions"]),
            item["name"],
        ),
        reverse=True,
    )

    reforms = []
    for event in world.events:
        if event.type != "religious_reform":
            continue
        reforms.append(
            {
                "year_label": _year_label(world_identity, event.turn + 1),
                "turn": event.turn + 1,
                "faction": _display_name(world, event.faction),
                "region": event.get("region_display_name") or _region_reference(world, event.region),
                "old_religion": event.get("old_religion"),
                "new_religion": event.get("new_religion"),
                "brief": _build_event_brief(world, event),
            }
        )

    faction_religion_state = []
    for faction in factions[:10]:
        faction_obj = world.factions[faction["name"]]
        religion_state = faction_obj.religion
        faction_religion_state.append(
            {
                "faction": faction["display_name"],
                "official_religion": religion_state.official_religion,
                "religious_legitimacy": round(float(religion_state.religious_legitimacy or 0.0), 3),
                "clergy_support": round(float(religion_state.clergy_support or 0.0), 3),
                "religious_tolerance": round(float(religion_state.religious_tolerance or 0.0), 3),
                "religious_zeal": round(float(religion_state.religious_zeal or 0.0), 3),
                "state_cult_strength": round(float(religion_state.state_cult_strength or 0.0), 3),
                "reform_pressure": round(float(religion_state.reform_pressure or 0.0), 3),
                "sacred_sites_controlled": int(religion_state.sacred_sites_controlled or 0),
                "total_sacred_sites": int(religion_state.total_sacred_sites or 0),
            }
        )

    return {
        "religions": religions[:10],
        "reforms": reforms[:12],
        "faction_religion_state": faction_religion_state,
    }


def _build_succession_digest(world, world_identity: dict, factions: list[dict]) -> dict:
    current_houses = []
    for faction in factions[:10]:
        faction_obj = world.factions[faction["name"]]
        succession = faction_obj.succession
        current_houses.append(
            {
                "faction": faction["display_name"],
                "narrative_name": faction.get("narrative_name") or faction["display_name"],
                "dynasty_name": succession.dynasty_name,
                "ruler_name": succession.ruler_name,
                "ruler_age": int(succession.ruler_age or 0),
                "ruler_reign_turns": int(succession.ruler_reign_turns or 0),
                "heir_name": succession.heir_name,
                "heir_age": int(succession.heir_age or 0),
                "heir_preparedness": round(float(succession.heir_preparedness or 0.0), 3),
                "legitimacy": round(float(succession.legitimacy or 0.0), 3),
                "dynasty_prestige": round(float(succession.dynasty_prestige or 0.0), 3),
                "regency_turns": int(succession.regency_turns or 0),
                "succession_crisis_turns": int(succession.succession_crisis_turns or 0),
                "claimant_pressure": round(float(succession.claimant_pressure or 0.0), 3),
                "last_succession_year": _year_label(world_identity, succession.last_succession_turn + 1)
                if succession.last_succession_turn is not None
                else None,
                "last_succession_type": succession.last_succession_type,
            }
        )

    succession_events = []
    for event in world.events:
        if event.type not in {"succession", "succession_crisis"}:
            continue
        succession_events.append(
            {
                "turn": event.turn + 1,
                "year_label": _year_label(world_identity, event.turn + 1),
                "type": event.type,
                "faction": _display_name(world, event.faction),
                "faction_narrative": _faction_narrative_name(world, event.faction) or _display_name(world, event.faction),
                "dynasty_name": event.get("dynasty_name"),
                "old_dynasty": event.get("old_dynasty"),
                "old_ruler": event.get("old_ruler"),
                "new_ruler": event.get("new_ruler"),
                "succession_type": event.get("succession_type"),
                "regency": bool(event.get("regency", False)),
                "claimant_faction": _faction_narrative_name(world, event.get("claimant_faction"))
                or _display_name(world, event.get("claimant_faction")),
                "claimant_region": _region_reference(world, event.get("claimant_region")),
                "legitimacy": event.get("legitimacy"),
                "claimant_pressure": event.get("claimant_pressure"),
                "brief": _build_event_brief(world, event),
            }
        )

    succession_events.sort(key=lambda item: (item["turn"], item["faction"]))
    return {
        "current_houses": current_houses,
        "succession_events": succession_events[:20],
    }


def _build_vignette_prompts(world, world_identity: dict) -> list[dict]:
    prompts = []
    sensory_cues = {
        "migration": ["crowded roads", "river ferries", "overloaded carts", "shrine courtyards"],
        "fracture": ["closed gates", "whispering courtiers", "raised banners", "hurried oaths"],
        "diplomacy": ["tribute wagons", "kneeling envoys", "sealed oaths", "hostage exchanges"],
        "statecraft": ["granaries", "market stalls", "new shrines", "scribes and ledgers"],
        "war": ["fortified crossings", "burned fields", "breached palisades", "muster drums"],
        "expansion": ["frontier watchposts", "survey markers", "new tax rolls", "claimed roads"],
    }
    for row in _build_key_event_digest(world, limit=16):
        family = _event_family(row["type"])
        cues = sensory_cues.get(family, ["dust", "stone courts", "riverbanks"])
        prompts.append(
            {
                "year_label": row["year_label"],
                "event_type": row["type"],
                "location": row.get("region_display_name"),
                "actors": [value for value in [row.get("actor_narrative") or row.get("actor"), row.get("counterpart_narrative") or row.get("counterpart")] if value],
                "brief": row["brief"],
                "scene_cues": cues[:3],
                "scene_purpose": {
                    "migration": "show how ordinary movement altered politics",
                    "fracture": "show how legitimacy broke in public view",
                    "diplomacy": "show hierarchy and humiliation",
                    "statecraft": "show institutions becoming tangible",
                    "war": "show what the contest cost on the ground",
                    "expansion": "show how a frontier became governed space",
                }.get(family, "show how a structural shift was felt locally"),
            }
        )
        if len(prompts) >= 8:
            break
    return prompts


def _build_successor_lineages(world, factions: list[dict]) -> list[dict]:
    standings_by_name = {entry["name"]: index + 1 for index, entry in enumerate(factions)}
    lineages: dict[str, list[dict]] = {}
    for entry in factions:
        origin = entry.get("origin_faction")
        if not origin:
            continue
        parent_name = _display_name(world, origin) or origin
        lineages.setdefault(parent_name, []).append(
            {
                "state": entry["display_name"],
                "rank": standings_by_name.get(entry["name"]),
                "treasury": entry["treasury"],
                "regions": entry["regions"],
                "conflict_type": entry.get("conflict_type") or "secession",
                "ethnicity": entry.get("ethnicity"),
            }
        )

    summarized = []
    for parent_name, descendants in lineages.items():
        descendants.sort(
            key=lambda item: (
                item["rank"] if item["rank"] is not None else 999,
                -item["treasury"],
                item["state"],
            )
        )
        summarized.append(
            {
                "parent": parent_name,
                "descendant_count": len(descendants),
                "descendants": descendants[:6],
            }
        )
    summarized.sort(key=lambda item: (-item["descendant_count"], item["parent"]))
    return summarized


def _build_rivalry_digest(world) -> list[dict]:
    pair_counts: Counter[tuple[str, str]] = Counter()
    pair_turns: dict[tuple[str, str], list[int]] = {}
    for event in world.events:
        if event.type != "diplomacy_rivalry":
            continue
        a = _display_name(world, event.faction) or event.faction
        b = _display_name(world, event.get("counterpart")) or event.get("counterpart")
        if not a or not b:
            continue
        pair = tuple(sorted((a, b)))
        pair_counts[pair] += 1
        pair_turns.setdefault(pair, []).append(event.turn + 1)

    rows = []
    for pair, count in pair_counts.items():
        turns = sorted(pair_turns.get(pair, []))
        rows.append(
            {
                "pair": list(pair),
                "count": count,
                "first_turn": turns[0] if turns else None,
                "last_turn": turns[-1] if turns else None,
                "turns": turns[:8],
            }
        )
    rows.sort(key=lambda item: (-item["count"], item["first_turn"] or 10**9, item["pair"]))
    return rows[:8]


def _build_centerpiece_episodes(world, *, limit: int = 6) -> list[dict]:
    phase_digest = _build_phase_event_digest(world, per_phase_limit=6)
    combined = []
    for phase_name in ("early", "mid", "late"):
        for row in phase_digest.get(phase_name, []):
            enriched = dict(row)
            enriched["phase"] = phase_name
            combined.append(enriched)

    combined.sort(key=lambda item: (item["score"], -item["turn"]), reverse=True)
    selected = []
    family_counts = Counter()
    for row in combined:
        family = _event_family(row["type"])
        if family_counts[family] >= 2:
            continue
        selected.append(row)
        family_counts[family] += 1
        if len(selected) >= limit:
            break
    return selected


def build_ai_interpretation_summary(world, *, map_name: str | None = None, num_turns: int | None = None) -> dict:
    """Builds a compact structured summary for AI-written narrative generation."""
    _phase_analyses, phase_summaries = summarize_phases(world)
    competition = analyze_competition_metrics(world)
    event_type_counts = Counter(event.type for event in world.events)
    world_identity = _build_world_identity(world)

    factions = []
    for faction_name, faction in world.factions.items():
        owned_regions = sum(
            1
            for region in world.regions.values()
            if region.owner == faction_name
        )
        homeland_region = _region_reference(world, faction.doctrine_state.homeland_region)
        factions.append(
            {
                "name": faction_name,
                "display_name": faction.display_name,
                "narrative_name": _faction_narrative_name(world, faction_name) or faction.display_name,
                "treasury": int(faction.treasury),
                "regions": owned_regions,
                "government": faction.government_type,
                "doctrine": faction.doctrine_label,
                "doctrine_gloss": _doctrine_gloss(faction),
                "ethnicity": faction.primary_ethnicity,
                "is_rebel": bool(faction.is_rebel),
                "origin_faction": faction.origin_faction,
                "conflict_type": faction.rebel_conflict_type,
                "official_religion": faction.religion.official_religion,
                "dynasty_name": faction.succession.dynasty_name,
                "ruler_name": faction.succession.ruler_name,
                "heir_name": faction.succession.heir_name,
                "legitimacy": round(float(faction.succession.legitimacy or 0.0), 3),
                "dynasty_prestige": round(float(faction.succession.dynasty_prestige or 0.0), 3),
                "claimant_pressure": round(float(faction.succession.claimant_pressure or 0.0), 3),
                "religious_legitimacy": round(float(faction.religion.religious_legitimacy or 0.0), 3),
                "religious_zeal": round(float(faction.religion.religious_zeal or 0.0), 3),
                "religious_tolerance": round(float(faction.religion.religious_tolerance or 0.0), 3),
                "homeland_region": homeland_region,
            }
        )

    factions.sort(
        key=lambda entry: (
            entry["treasury"],
            entry["regions"],
            entry["display_name"],
        ),
        reverse=True,
    )

    religion_digest = _build_religion_digest(world, world_identity, factions)
    succession_digest = _build_succession_digest(world, world_identity, factions)

    chronology = {
        "calendar_name": world_identity["calendar_name"],
        "current_year_label": _year_label(world_identity, int(num_turns or world.turn)),
        "early_phase_years": f"{_year_label(world_identity, 1)} to {_year_label(world_identity, max(1, int((num_turns or world.turn) // 3)))}",
        "mid_phase_years": f"{_year_label(world_identity, max(1, int((num_turns or world.turn) // 3) + 1))} to {_year_label(world_identity, max(1, int((2 * (num_turns or world.turn)) // 3)))}",
        "late_phase_years": f"{_year_label(world_identity, max(1, int((2 * (num_turns or world.turn)) // 3) + 1))} to {_year_label(world_identity, max(1, int(num_turns or world.turn)))}",
        "turn_to_year_note": "Treat each simulation turn as one season in the supplied reckoning: Spring, Summer, Autumn, then Winter. Four turns make one year.",
    }

    return {
        "simulation": {
            "map_name": map_name or getattr(world, "map_name", ""),
            "turns": int(num_turns or world.turn),
            "regions": len(world.regions),
            "factions": len(world.factions),
        },
        "world_identity": world_identity,
        "chronology": chronology,
        "outcome_explanation": summarize_strategic_interpretation(world),
        "phase_summaries": phase_summaries,
        "turning_points": summarize_turning_points(world),
        "structural_drivers": summarize_structural_drivers(world),
        "faction_epilogues": summarize_faction_epilogues(world),
        "final_standings": summarize_final_standings(world),
        "victor_history": summarize_victor_history(world),
        "competition_metrics": competition,
        "event_type_counts": dict(event_type_counts),
        "eliminations": _build_elimination_digest(world, competition, world_identity),
        "key_event_digest": _build_key_event_digest(world, limit=28),
        "phase_event_digest": _build_phase_event_digest(world, per_phase_limit=5),
        "centerpiece_episodes": _build_centerpiece_episodes(world, limit=7),
        "successor_lineages": _build_successor_lineages(world, factions),
        "rivalry_digest": _build_rivalry_digest(world),
        "religion_digest": religion_digest,
        "succession_digest": succession_digest,
        "vignette_prompts": _build_vignette_prompts(world, world_identity),
        "factions": factions,
    }


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


def _generate_ai_paragraph(
    summary: dict,
    system_prompt: str,
    max_output_tokens: int,
    *,
    strict: bool = False,
    enabled_override: bool | None = None,
) -> str | None:
    """Returns one AI-written paragraph for the provided summary and prompt."""
    if not is_ai_interpretation_enabled(enabled_override=enabled_override):
        if strict:
            raise RuntimeError(
                "AI interpretation is not enabled. Set CLASHVERGENCE_ENABLE_AI_INTERPRETATION=1 and provide OPENAI_API_KEY."
            )
        return None

    try:
        from openai import OpenAI
    except ImportError as exc:
        if strict:
            raise RuntimeError("The openai package is not installed.") from exc
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
        if strict and not interpretation:
            raise RuntimeError("The AI interpretation API returned an empty response.")
        return interpretation or None
    except Exception as exc:
        if strict:
            raise RuntimeError(f"AI interpretation request failed: {exc}") from exc
        return None


def generate_ai_interpretation(
    summary: dict,
    *,
    strict: bool = False,
    enabled_override: bool | None = None,
) -> str | None:
    """Returns an AI-written interpretation paragraph for one compact summary."""
    return _generate_ai_paragraph(
        summary=summary,
        system_prompt=AI_INTERPRETATION_SYSTEM_PROMPT,
        max_output_tokens=AI_INTERPRETATION_MAX_OUTPUT_TOKENS,
        strict=strict,
        enabled_override=enabled_override,
    )


def generate_victor_history(summary: dict, *, strict: bool = False) -> str | None:
    """Returns an AI-written victor-history paragraph for one compact summary."""
    return _generate_ai_paragraph(
        summary=summary,
        system_prompt=VICTOR_HISTORY_SYSTEM_PROMPT,
        max_output_tokens=VICTOR_HISTORY_MAX_OUTPUT_TOKENS,
        strict=strict,
    )
