from __future__ import annotations

from src.config import (
    CLIMATE_ATTACK_PROJECTION_MAX_PENALTY,
    CLIMATE_CORE_INTEGRATION_CLIMATE_FACTOR,
    CLIMATE_FRONTIER_INTEGRATION_CLIMATE_FACTOR,
    CLIMATE_INCOME_MAX_FACTOR,
    CLIMATE_INCOME_MIN_FACTOR,
    CLIMATE_MAINTENANCE_MAX_FACTOR,
    CLIMATE_MAINTENANCE_MIN_FACTOR,
    CORE_INCOME_FACTOR,
    FRONTIER_ATTACK_PROJECTION_PENALTY,
    FRONTIER_INCOME_FACTOR,
    HOMELAND_INCOME_FACTOR,
    UNREST_ATTACK_PROJECTION_MAX_PENALTY,
    UNREST_CRISIS_INCOME_FACTOR,
    UNREST_DISTURBANCE_INCOME_FACTOR,
    UNREST_EVENT_ATTACK_PROJECTION_PENALTY,
    UNREST_INCOME_MIN_FACTOR,
    UNREST_MAX,
)
from src.calendar import get_turn_season_name
from src.models import Region, WorldState
from src.terrain import get_seasonal_terrain_attack_projection_modifier


HOMELAND_INTEGRATION_SCORE = 10.0
CORE_INTEGRATION_SCORE = 6.0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def get_region_core_status(region: Region) -> str:
    if region.owner is None:
        return "frontier"
    if region.homeland_faction_id == region.owner:
        return "homeland"
    if region.integration_score >= CORE_INTEGRATION_SCORE:
        return "core"
    return "frontier"


def get_region_core_defense_bonus(region: Region) -> int:
    status = get_region_core_status(region)
    if status == "homeland":
        return 2
    if status == "core":
        return 1
    return 0


def get_region_climate_affinity(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.5
    from src.doctrine import get_faction_climate_affinity

    return get_faction_climate_affinity(world.factions[region.owner], region.climate)


def get_region_income_factor(region: Region) -> float:
    status = get_region_core_status(region)
    if status == "homeland":
        return HOMELAND_INCOME_FACTOR
    if status == "core":
        return CORE_INCOME_FACTOR
    return FRONTIER_INCOME_FACTOR


def get_faction_frontier_burden(world: WorldState, faction_name: str) -> float:
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]
    if not owned_regions:
        return 0.0

    frontier_regions = sum(
        1
        for region in owned_regions
        if get_region_core_status(region) == "frontier"
    )
    return frontier_regions / len(owned_regions)


def get_region_unrest_income_factor(region: Region) -> float:
    unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
    income_factor = 1.0 - ((1.0 - UNREST_INCOME_MIN_FACTOR) * unrest_ratio)
    if region.unrest_event_level == "disturbance":
        income_factor *= UNREST_DISTURBANCE_INCOME_FACTOR
    elif region.unrest_event_level == "crisis":
        income_factor *= UNREST_CRISIS_INCOME_FACTOR
    return income_factor


def get_region_climate_income_factor(region: Region, world: WorldState) -> float:
    affinity = get_region_climate_affinity(region, world)
    return CLIMATE_INCOME_MIN_FACTOR + (
        (CLIMATE_INCOME_MAX_FACTOR - CLIMATE_INCOME_MIN_FACTOR) * affinity
    )


def get_region_climate_maintenance_factor(region: Region, world: WorldState) -> float:
    affinity = get_region_climate_affinity(region, world)
    return CLIMATE_MAINTENANCE_MAX_FACTOR - (
        (CLIMATE_MAINTENANCE_MAX_FACTOR - CLIMATE_MAINTENANCE_MIN_FACTOR) * affinity
    )


def get_region_climate_integration_modifier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.0
    if region.homeland_faction_id == region.owner:
        return 0.0

    affinity = get_region_climate_affinity(region, world)
    status = get_region_core_status(region)
    centered_affinity = (affinity - 0.5) * 2

    if status == "frontier":
        return centered_affinity * CLIMATE_FRONTIER_INTEGRATION_CLIMATE_FACTOR

    return centered_affinity * CLIMATE_CORE_INTEGRATION_CLIMATE_FACTOR


def get_region_attack_projection_modifier(
    region: Region,
    *,
    world: WorldState | None = None,
    faction_name: str | None = None,
) -> int:
    modifier = 0
    if get_region_core_status(region) == "frontier":
        modifier -= FRONTIER_ATTACK_PROJECTION_PENALTY

    unrest_penalty = int(
        round(_clamp(region.unrest / UNREST_MAX, 0.0, 1.0) * UNREST_ATTACK_PROJECTION_MAX_PENALTY)
    )
    modifier -= unrest_penalty
    if region.unrest_event_level in {"disturbance", "crisis"}:
        modifier -= UNREST_EVENT_ATTACK_PROJECTION_PENALTY

    if world is not None and faction_name is not None and faction_name in world.factions:
        from src.doctrine import get_faction_climate_affinity

        climate_affinity = get_faction_climate_affinity(world.factions[faction_name], region.climate)
        climate_penalty = int(round((1.0 - climate_affinity) * CLIMATE_ATTACK_PROJECTION_MAX_PENALTY))
        modifier -= climate_penalty
        season_name = get_turn_season_name(world.turn)
        modifier += get_seasonal_terrain_attack_projection_modifier(region, season_name)

    return modifier
