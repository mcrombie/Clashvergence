from __future__ import annotations

from src.climate import format_climate_label, normalize_climate
from src.heartland import get_region_core_status
from src.models import Faction, FactionDoctrineProfile, WorldState
from src.terrain import format_terrain_label, normalize_terrain_tags


HOMELAND_IMPRINT_WEIGHT = 12.0
CORE_REGION_EXPERIENCE = 0.8
FRONTIER_REGION_EXPERIENCE = 0.35
CLIMATE_EXPERIENCE_MULTIPLIER = 1.8

OPEN_TERRAIN_TAGS = {"plains", "riverland", "steppe", "coast"}
ROUGH_TERRAIN_TAGS = {"forest", "hills", "highland", "marsh"}

def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _round_posture(value: float) -> float:
    return round(_clamp(value, 0.05, 0.95), 3)

def get_owned_region_counts(world: WorldState) -> dict[str, int]:
    counts = {faction_name: 0 for faction_name in world.factions}
    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1
    return counts


def _sorted_terrain_experience(experience: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(
        experience.items(),
        key=lambda item: (-item[1], item[0]),
    )


def _get_primary_terrain_identity(experience: dict[str, float]) -> tuple[str, list[str]]:
    ranked = _sorted_terrain_experience(experience)
    if not ranked:
        return ("Plains", ["plains"])

    top_tag, top_score = ranked[0]
    identity_tags = [top_tag]

    if len(ranked) > 1:
        second_tag, second_score = ranked[1]
        if second_score >= top_score * 0.62:
            identity_tags.append(second_tag)

    normalized = normalize_terrain_tags(identity_tags)
    return (format_terrain_label(normalized), normalized)


def _get_terrain_mix_scores(experience: dict[str, float]) -> tuple[float, float]:
    if not experience:
        return (0.5, 0.5)

    open_score = 0.0
    rough_score = 0.0
    for tag, value in experience.items():
        if tag in OPEN_TERRAIN_TAGS:
            open_score += value
        if tag in ROUGH_TERRAIN_TAGS:
            rough_score += value

    total = open_score + rough_score
    if total <= 0:
        return (0.5, 0.5)
    return (open_score / total, rough_score / total)


def _get_primary_climate_identity(experience: dict[str, float]) -> str:
    if not experience:
        return "Temperate"
    ranked = sorted(
        experience.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return format_climate_label(ranked[0][0])


def _get_behavior_label(
    expansion_posture: float,
    war_posture: float,
    development_posture: float,
    insularity: float,
) -> str:
    if expansion_posture >= 0.7 and war_posture >= 0.58:
        return "Frontier"
    if insularity >= 0.7 and development_posture >= 0.62:
        return "Insular"
    if development_posture >= 0.72:
        return "Developmental"
    if war_posture >= 0.68:
        return "Martial"
    if insularity >= 0.68:
        return "Defensive"
    if expansion_posture >= 0.65:
        return "Expansionary"
    return "Adaptive"


def _build_doctrine_summary(
    faction: Faction,
    homeland_identity: str,
    terrain_identity: str,
    homeland_climate: str,
    climate_identity: str,
    expansion_posture: float,
    war_posture: float,
    development_posture: float,
    insularity: float,
) -> str:
    behavior_label = _get_behavior_label(
        expansion_posture,
        war_posture,
        development_posture,
        insularity,
    ).lower()
    homeland_phrase = f"Homeland in {homeland_identity.lower()} under a {homeland_climate.lower()} climate"
    if terrain_identity == homeland_identity:
        terrain_phrase = f"has kept it rooted in {terrain_identity.lower()} habits"
    else:
        terrain_phrase = (
            f"has broadened it into a {terrain_identity.lower()} doctrine"
        )
    if climate_identity == homeland_climate:
        climate_phrase = "while its climate instincts remain close to home"
    else:
        climate_phrase = f"while experience has pushed it toward a {climate_identity.lower()} climate outlook"

    if development_posture >= max(expansion_posture, war_posture) and insularity >= 0.58:
        posture_phrase = "that favors consolidation and patient development"
    elif expansion_posture >= max(development_posture, war_posture):
        posture_phrase = "that pushes outward when terrain opens a path"
    elif war_posture >= max(expansion_posture, development_posture):
        posture_phrase = "that accepts conflict when the ground is favorable"
    else:
        posture_phrase = "that adapts between growth and consolidation"

    return (
        f"{homeland_phrase} {terrain_phrase}, {climate_phrase}, producing a {behavior_label} polity {posture_phrase}."
    )


def compute_faction_doctrine_profile(
    faction: Faction,
    *,
    total_regions: int,
) -> FactionDoctrineProfile:
    state = faction.doctrine_state
    homeland_tags = normalize_terrain_tags(state.homeland_terrain_tags)
    homeland_identity = format_terrain_label(homeland_tags)
    homeland_climate = format_climate_label(state.homeland_climate)
    terrain_identity, preferred_terrains = _get_primary_terrain_identity(state.terrain_experience)
    climate_identity = _get_primary_climate_identity(state.climate_experience)
    open_ratio, rough_ratio = _get_terrain_mix_scores(state.terrain_experience)

    turns = max(1, state.turns_observed)
    growth_ratio = state.turns_with_growth / turns
    conflict_ratio = state.turns_with_conflict / turns
    investment_ratio = state.turns_with_investment / turns
    conquest_ratio = state.successful_attacks / max(1, state.attacks)
    territorial_reach = state.peak_regions / max(1, total_regions)
    average_regions = state.cumulative_regions_held / turns
    consolidation_ratio = average_regions / max(1, state.peak_regions)

    expansion_posture = _round_posture(
        0.18
        + (growth_ratio * 0.34)
        + (territorial_reach * 0.24)
        + (open_ratio * 0.16)
        + ((state.regions_gained_by_expansion / turns) * 0.10)
    )
    war_posture = _round_posture(
        0.12
        + (conflict_ratio * 0.38)
        + (conquest_ratio * 0.20)
        + (territorial_reach * 0.08)
        + (open_ratio * 0.07)
    )
    development_posture = _round_posture(
        0.18
        + (investment_ratio * 0.36)
        + (rough_ratio * 0.16)
        + (consolidation_ratio * 0.18)
        + (max(0.0, 1.0 - conflict_ratio) * 0.07)
    )
    insularity = _round_posture(
        0.16
        + (rough_ratio * 0.28)
        + (investment_ratio * 0.12)
        + (max(0.0, 0.55 - growth_ratio) * 0.28)
        + (max(0.0, 0.45 - open_ratio) * 0.08)
    )

    behavior_label = _get_behavior_label(
        expansion_posture,
        war_posture,
        development_posture,
        insularity,
    )
    doctrine_label = f"{behavior_label} {terrain_identity}"
    summary = _build_doctrine_summary(
        faction,
        homeland_identity,
        terrain_identity,
        homeland_climate,
        climate_identity,
        expansion_posture,
        war_posture,
        development_posture,
        insularity,
    )

    return FactionDoctrineProfile(
        homeland_identity=homeland_identity,
        terrain_identity=terrain_identity,
        climate_identity=climate_identity,
        preferred_terrains=preferred_terrains,
        expansion_posture=expansion_posture,
        war_posture=war_posture,
        development_posture=development_posture,
        insularity=insularity,
        doctrine_label=doctrine_label,
        summary=summary,
        dominant_behavior=behavior_label.lower(),
    )


def initialize_faction_doctrines(world: WorldState) -> None:
    owned_counts = get_owned_region_counts(world)
    homeland_regions: dict[str, str] = {}

    for region_name, region in sorted(world.regions.items()):
        if region.owner is None or region.owner in homeland_regions:
            continue
        homeland_regions[region.owner] = region_name

    for faction_name, faction in world.factions.items():
        homeland_region = homeland_regions.get(faction_name)
        homeland_tags = normalize_terrain_tags(
            world.regions[homeland_region].terrain_tags if homeland_region is not None else ["plains"]
        )
        homeland_climate = normalize_climate(
            world.regions[homeland_region].climate if homeland_region is not None else "temperate"
        )
        faction.doctrine_state.homeland_region = homeland_region
        faction.doctrine_state.homeland_terrain_tags = homeland_tags
        faction.doctrine_state.homeland_climate = homeland_climate
        faction.doctrine_state.terrain_experience = {
            tag: HOMELAND_IMPRINT_WEIGHT
            for tag in homeland_tags
        }
        faction.doctrine_state.climate_experience = {
            homeland_climate: HOMELAND_IMPRINT_WEIGHT
        }
        faction.doctrine_state.starting_regions = owned_counts.get(faction_name, 0)
        faction.doctrine_state.last_region_count = owned_counts.get(faction_name, 0)
        faction.doctrine_state.peak_regions = owned_counts.get(faction_name, 0)
        faction.doctrine_profile = compute_faction_doctrine_profile(
            faction,
            total_regions=len(world.regions),
        )


def update_faction_doctrines(world: WorldState) -> None:
    owned_counts = get_owned_region_counts(world)
    turn_events = [event for event in world.events if event.turn == world.turn]
    events_by_faction = {faction_name: [] for faction_name in world.factions}
    for event in turn_events:
        if event.faction in events_by_faction:
            events_by_faction[event.faction].append(event)

    for faction_name, faction in world.factions.items():
        state = faction.doctrine_state
        current_regions = owned_counts.get(faction_name, 0)
        state.turns_observed += 1
        state.cumulative_regions_held += current_regions
        state.peak_regions = max(state.peak_regions, current_regions)

        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            status = get_region_core_status(region)
            if status == "homeland":
                experience_gain = HOMELAND_IMPRINT_WEIGHT / 10
            elif status == "core":
                experience_gain = CORE_REGION_EXPERIENCE
            else:
                experience_gain = FRONTIER_REGION_EXPERIENCE
            for tag in normalize_terrain_tags(region.terrain_tags):
                state.terrain_experience[tag] = state.terrain_experience.get(tag, 0.0) + experience_gain
            normalized_climate = normalize_climate(region.climate)
            state.climate_experience[normalized_climate] = (
                state.climate_experience.get(normalized_climate, 0.0)
                + (experience_gain * CLIMATE_EXPERIENCE_MULTIPLIER)
            )

        faction_events = events_by_faction[faction_name]
        if any(event.type in {"expand", "attack"} for event in faction_events):
            state.turns_with_conflict += 1
        if any(event.type == "invest" for event in faction_events):
            state.turns_with_investment += 1
        if current_regions > state.last_region_count:
            state.turns_with_growth += 1

        for event in faction_events:
            if event.type == "expand":
                state.expansions += 1
                state.regions_gained_by_expansion += 1
            elif event.type == "attack":
                state.attacks += 1
                if event.get("success", False):
                    state.successful_attacks += 1
                    state.regions_gained_by_conquest += 1
            elif event.type == "invest":
                state.investments += 1

        state.last_region_count = current_regions
        faction.doctrine_profile = compute_faction_doctrine_profile(
            faction,
            total_regions=len(world.regions),
        )


def get_faction_terrain_affinity(faction: Faction, terrain_tag: str) -> float:
    experience = faction.doctrine_state.terrain_experience
    if not experience:
        return 0.0

    top_score = max(experience.values())
    smoothing = HOMELAND_IMPRINT_WEIGHT * 0.25
    base = experience.get(terrain_tag, 0.0)
    if terrain_tag in faction.doctrine_state.homeland_terrain_tags:
        base += smoothing
    return _clamp(base / (top_score + smoothing), 0.0, 1.0)


def get_faction_climate_affinity(faction: Faction, climate: str | None) -> float:
    normalized = normalize_climate(climate)
    experience = faction.doctrine_state.climate_experience
    if not experience:
        return 0.0

    top_score = max(experience.values())
    smoothing = HOMELAND_IMPRINT_WEIGHT * 0.25
    base = experience.get(normalized, 0.0)
    if normalized == faction.doctrine_state.homeland_climate:
        base += smoothing
    return _clamp(base / (top_score + smoothing), 0.0, 1.0)


def get_faction_region_alignment(
    faction: Faction,
    terrain_tags: list[str] | None,
    climate: str | None = None,
) -> dict[str, float | list[str] | str | bool]:
    normalized = normalize_terrain_tags(terrain_tags)
    normalized_climate = normalize_climate(climate)
    terrain_affinities = [
        get_faction_terrain_affinity(faction, tag)
        for tag in normalized
    ]
    average_terrain_affinity = (
        sum(terrain_affinities) / len(terrain_affinities) if terrain_affinities else 0.0
    )
    climate_affinity = get_faction_climate_affinity(faction, normalized_climate)
    average_affinity = ((average_terrain_affinity * 0.7) + (climate_affinity * 0.3))
    homeland_matches = sum(
        1
        for tag in normalized
        if tag in faction.doctrine_state.homeland_terrain_tags
    )
    climate_match = normalized_climate == faction.doctrine_state.homeland_climate

    expansion_modifier = int(
        round(
            ((average_affinity - 0.35) * 4)
            + (homeland_matches * 0.5)
            + (0.6 if climate_match else 0.0)
        )
    )
    combat_modifier = int(
        round(
            (average_affinity * 2.0)
            + (homeland_matches * 0.6)
            + (0.5 if climate_match else 0.0)
        )
    )
    economic_modifier = int(
        round(
            ((average_affinity - 0.4) * 2)
            + (0.35 if climate_match else 0.0)
        )
    )

    return {
        "terrain_tags": normalized,
        "climate": normalized_climate,
        "terrain_affinity": round(average_terrain_affinity, 3),
        "climate_affinity": round(climate_affinity, 3),
        "average_affinity": round(average_affinity, 3),
        "homeland_matches": homeland_matches,
        "climate_match": climate_match,
        "expansion_modifier": max(-1, min(3, expansion_modifier)),
        "combat_modifier": max(0, min(3, combat_modifier)),
        "economic_modifier": max(-1, min(2, economic_modifier)),
    }
