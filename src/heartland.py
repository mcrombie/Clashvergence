from __future__ import annotations

from copy import deepcopy
from math import ceil

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
    FRONTIER_MAINTENANCE_SURCHARGE,
    HOMELAND_INCOME_FACTOR,
    REGION_MAINTENANCE_COST,
    UNREST_ATTACK_PROJECTION_MAX_PENALTY,
    UNREST_CLIMATE_PRESSURE_FACTOR,
    UNREST_CONQUEST_START,
    UNREST_DECAY_PER_TURN,
    UNREST_CRISIS_DURATION,
    UNREST_CRISIS_INCOME_FACTOR,
    UNREST_CRISIS_TREASURY_HIT,
    UNREST_CRITICAL_THRESHOLD,
    UNREST_DISTURBANCE_DURATION,
    UNREST_DISTURBANCE_INCOME_FACTOR,
    UNREST_DISTURBANCE_TREASURY_HIT,
    UNREST_EVENT_ATTACK_PROJECTION_PENALTY,
    UNREST_EXPANSION_START,
    UNREST_FRONTIER_BURDEN_FACTOR,
    UNREST_FRONTIER_PRESSURE,
    UNREST_INCOME_MIN_FACTOR,
    UNREST_INTEGRATION_PRESSURE_FACTOR,
    UNREST_MAINTENANCE_MAX_FACTOR,
    UNREST_MAX,
    UNREST_MODERATE_THRESHOLD,
    UNREST_SECESSION_CRISIS_TURNS,
    UNREST_SECESSION_RESOURCE_LOSS,
    UNREST_SECESSION_THRESHOLD,
)
from src.models import Event, Region, WorldState


HOMELAND_INTEGRATION_SCORE = 10.0
CORE_INTEGRATION_SCORE = 6.0
CONQUEST_INTEGRATION_SCORE = 1.0
PER_TURN_FRONTIER_GAIN = 1.0
PER_TURN_CORE_GAIN = 0.35


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


def get_region_effective_income(region: Region, world: WorldState | None = None) -> int:
    income_factor = get_region_income_factor(region)
    if world is not None:
        income_factor *= get_region_climate_income_factor(region, world)
    income_factor *= get_region_unrest_income_factor(region)
    return int(round(region.resources * income_factor))


def get_region_climate_maintenance_factor(region: Region, world: WorldState) -> float:
    affinity = get_region_climate_affinity(region, world)
    return CLIMATE_MAINTENANCE_MAX_FACTOR - (
        (CLIMATE_MAINTENANCE_MAX_FACTOR - CLIMATE_MAINTENANCE_MIN_FACTOR) * affinity
    )


def get_region_maintenance_cost(region: Region, world: WorldState | None = None) -> int:
    status = get_region_core_status(region)
    if status == "frontier":
        base_cost = REGION_MAINTENANCE_COST + FRONTIER_MAINTENANCE_SURCHARGE
    else:
        base_cost = REGION_MAINTENANCE_COST
    if world is None:
        unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
        unrest_factor = 1.0 + ((UNREST_MAINTENANCE_MAX_FACTOR - 1.0) * unrest_ratio)
        return int(ceil(base_cost * unrest_factor))
    climate_factor = get_region_climate_maintenance_factor(region, world)
    unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
    unrest_factor = 1.0 + ((UNREST_MAINTENANCE_MAX_FACTOR - 1.0) * unrest_ratio)
    return int(ceil(base_cost * climate_factor * unrest_factor))


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

    return modifier


def set_region_integration(
    region: Region,
    *,
    owner: str | None,
    score: float,
    ownership_turns: int,
    core_status: str | None = None,
) -> None:
    region.integrated_owner = owner
    region.integration_score = score
    region.ownership_turns = ownership_turns
    region.core_status = core_status or get_region_core_status(region)


def set_region_unrest(region: Region, unrest: float) -> None:
    region.unrest = round(_clamp(unrest, 0.0, UNREST_MAX), 2)


def clear_region_unrest_event(region: Region) -> None:
    region.unrest_event_level = "none"
    region.unrest_event_turns_remaining = 0


def set_region_unrest_event(region: Region, *, level: str, duration: int) -> None:
    region.unrest_event_level = level
    region.unrest_event_turns_remaining = duration


def get_region_unrest_event_cost(region: Region) -> int:
    if region.unrest_event_level == "crisis":
        return UNREST_CRISIS_TREASURY_HIT
    if region.unrest_event_level == "disturbance":
        return UNREST_DISTURBANCE_TREASURY_HIT
    return 0


def reset_region_crisis_streak(region: Region) -> None:
    region.unrest_crisis_streak = 0


def initialize_heartlands(world: WorldState) -> None:
    owned_counts: dict[str, int] = {}

    for region_name, region in sorted(world.regions.items()):
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.unrest = 0.0
            clear_region_unrest_event(region)
            reset_region_crisis_streak(region)
            region.ownership_turns = 0
            continue

        owned_count = owned_counts.get(region.owner, 0)
        if owned_count == 0:
            region.homeland_faction_id = region.owner
            set_region_integration(
                region,
                owner=region.owner,
                score=HOMELAND_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="homeland",
            )
        else:
            set_region_integration(
                region,
                owner=region.owner,
                score=CORE_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="core",
            )
        owned_counts[region.owner] = owned_count + 1
        region.unrest = 0.0
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)


def handle_region_owner_change(region: Region, new_owner: str | None) -> None:
    previous_owner = region.owner
    if previous_owner == new_owner:
        return

    region.owner = new_owner
    if previous_owner is not None and new_owner is not None:
        region.conquest_count += 1

    if new_owner is None:
        set_region_integration(
            region,
            owner=None,
            score=0.0,
            ownership_turns=0,
            core_status="frontier",
        )
        set_region_unrest(region, 0.0)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        return

    base_score = HOMELAND_INTEGRATION_SCORE if region.homeland_faction_id == new_owner else CONQUEST_INTEGRATION_SCORE
    base_status = "homeland" if region.homeland_faction_id == new_owner else "frontier"
    set_region_integration(
        region,
        owner=new_owner,
        score=base_score,
        ownership_turns=1,
        core_status=base_status,
    )
    if region.homeland_faction_id == new_owner:
        set_region_unrest(region, 0.0)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
    elif previous_owner is None:
        set_region_unrest(region, UNREST_EXPANSION_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
    else:
        set_region_unrest(region, UNREST_CONQUEST_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)


def get_region_unrest_pressure(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.0
    if region.homeland_faction_id == region.owner:
        return -UNREST_DECAY_PER_TURN

    climate_affinity = get_region_climate_affinity(region, world)
    climate_pressure = (1.0 - climate_affinity) * UNREST_CLIMATE_PRESSURE_FACTOR
    integration_gap = max(0.0, CORE_INTEGRATION_SCORE - region.integration_score) / CORE_INTEGRATION_SCORE
    integration_pressure = integration_gap * UNREST_INTEGRATION_PRESSURE_FACTOR
    frontier_pressure = (
        UNREST_FRONTIER_PRESSURE
        if get_region_core_status(region) == "frontier"
        else 0.0
    )
    frontier_burden = get_faction_frontier_burden(world, region.owner) * UNREST_FRONTIER_BURDEN_FACTOR
    return climate_pressure + integration_pressure + frontier_pressure + frontier_burden - UNREST_DECAY_PER_TURN


def resolve_unrest_events(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            clear_region_unrest_event(region)
            continue
        if region.unrest_event_turns_remaining > 0:
            continue

        if region.unrest >= UNREST_CRITICAL_THRESHOLD:
            set_region_unrest_event(region, level="crisis", duration=UNREST_CRISIS_DURATION)
        elif region.unrest >= UNREST_MODERATE_THRESHOLD:
            set_region_unrest_event(region, level="disturbance", duration=UNREST_DISTURBANCE_DURATION)
        else:
            continue

        faction = world.factions[region.owner]
        treasury_hit = min(get_region_unrest_event_cost(region), faction.treasury)
        faction.treasury -= treasury_hit
        world.events.append(Event(
            turn=world.turn,
            type=f"unrest_{region.unrest_event_level}",
            faction=region.owner,
            region=region.name,
            details={
                "unrest": round(region.unrest, 2),
                "event_level": region.unrest_event_level,
                "duration": region.unrest_event_turns_remaining,
            },
            impact={
                "treasury_change": -treasury_hit,
                "treasury_after": faction.treasury,
                "integration_stalled": region.unrest_event_level == "crisis",
            },
            tags=["unrest", region.unrest_event_level],
            significance=region.unrest,
        ))


def apply_unrest_secession(world: WorldState, region: Region) -> None:
    if region.owner is None:
        return

    former_owner = region.owner
    resources_before = region.resources
    unrest_before = region.unrest
    region.resources = max(1, region.resources - UNREST_SECESSION_RESOURCE_LOSS)
    handle_region_owner_change(region, None)
    reset_region_crisis_streak(region)

    world.events.append(Event(
        turn=world.turn,
        type="unrest_secession",
        faction=former_owner,
        region=region.name,
        details={
            "former_owner": former_owner,
            "unrest": round(unrest_before, 2),
        },
        impact={
            "owner_after": None,
            "resource_change": region.resources - resources_before,
            "new_resources": region.resources,
        },
        tags=["unrest", "secession", "collapse"],
        significance=UNREST_SECESSION_THRESHOLD,
    ))


def update_region_integration(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.unrest = 0.0
            clear_region_unrest_event(region)
            region.ownership_turns = 0
            reset_region_crisis_streak(region)
            continue

        if region.integrated_owner != region.owner:
            handle_region_owner_change(region, region.owner)
            continue

        if region.homeland_faction_id == region.owner:
            region.integration_score = max(region.integration_score, HOMELAND_INTEGRATION_SCORE)
            region.ownership_turns += 1
            region.core_status = "homeland"
            set_region_unrest(region, region.unrest - UNREST_DECAY_PER_TURN)
            reset_region_crisis_streak(region)
            if region.unrest_event_turns_remaining > 0:
                region.unrest_event_turns_remaining -= 1
                if region.unrest_event_turns_remaining <= 0:
                    clear_region_unrest_event(region)
            continue

        region.ownership_turns += 1
        if region.unrest_event_level == "crisis":
            region.unrest_crisis_streak += 1
        else:
            reset_region_crisis_streak(region)

        if region.unrest_event_level != "crisis":
            climate_modifier = get_region_climate_integration_modifier(region, world)
            if region.integration_score < CORE_INTEGRATION_SCORE:
                region.integration_score += PER_TURN_FRONTIER_GAIN + climate_modifier
            else:
                region.integration_score += PER_TURN_CORE_GAIN + climate_modifier
        region.core_status = get_region_core_status(region)
        set_region_unrest(region, region.unrest + get_region_unrest_pressure(region, world))
        if (
            region.unrest_event_level == "crisis"
            and region.unrest_crisis_streak >= UNREST_SECESSION_CRISIS_TURNS
            and region.unrest >= UNREST_SECESSION_THRESHOLD
        ):
            apply_unrest_secession(world, region)
            continue
        if region.unrest_event_turns_remaining > 0:
            region.unrest_event_turns_remaining -= 1
            if region.unrest_event_turns_remaining <= 0:
                clear_region_unrest_event(region)


def build_region_snapshot(world: WorldState) -> dict[str, dict]:
    return {
        region_name: {
            "owner": region.owner,
            "resources": region.resources,
            "display_name": region.display_name,
            "founding_name": region.founding_name,
            "original_namer_faction_id": region.original_namer_faction_id,
            "terrain_tags": list(region.terrain_tags),
            "climate": region.climate,
            "homeland_faction_id": region.homeland_faction_id,
            "integrated_owner": region.integrated_owner,
            "integration_score": round(region.integration_score, 2),
            "core_status": region.core_status,
            "unrest": round(region.unrest, 2),
            "unrest_event_level": region.unrest_event_level,
            "unrest_event_turns_remaining": region.unrest_event_turns_remaining,
            "unrest_crisis_streak": region.unrest_crisis_streak,
        }
        for region_name, region in world.regions.items()
    }


def initialize_region_history(world: WorldState) -> None:
    world.region_history = [deepcopy(build_region_snapshot(world))]


def record_region_history(world: WorldState) -> None:
    world.region_history.append(deepcopy(build_region_snapshot(world)))
