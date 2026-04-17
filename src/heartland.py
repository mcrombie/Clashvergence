from __future__ import annotations

from copy import deepcopy
from math import ceil
import re

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
    POPULATION_BASE,
    POPULATION_GROWTH_PER_TURN,
    POPULATION_MINIMUM,
    POPULATION_PER_CONNECTION,
    POPULATION_PER_RESOURCE,
    POPULATION_SECESSION_LOSS,
    POPULATION_STARTING_OWNER_BONUS,
    POPULATION_UNOWNED_GROWTH_FACTOR,
    POPULATION_UNREST_CRISIS_LOSS,
    POPULATION_UNREST_GROWTH_PENALTY,
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
    REBEL_FULL_INDEPENDENCE_THRESHOLD,
    REBEL_INDEPENDENCE_TREASURY_BONUS,
    REBEL_INDEPENDENCE_PER_EXTRA_REGION,
    REBEL_INDEPENDENCE_PER_TURN,
    REBEL_MATURE_GOVERNMENT_TYPE,
    REBEL_PARENT_RECLAIM_MAX_BONUS,
    REBEL_RECURSIVE_UNREST_REDUCTION,
    REBEL_SECESSION_COOLDOWN_TURNS,
    REBEL_STARTING_TREASURY,
    REBEL_STARTING_UNREST,
    UNREST_SECESSION_CRISIS_TURNS,
    UNREST_SECESSION_RESOURCE_LOSS,
    UNREST_SECESSION_THRESHOLD,
)
from src.diplomacy import seed_rebel_origin_relationship
from src.models import Event, Faction, FactionIdentity, Region, WorldState


HOMELAND_INTEGRATION_SCORE = 10.0
CORE_INTEGRATION_SCORE = 6.0
CONQUEST_INTEGRATION_SCORE = 1.0
PER_TURN_FRONTIER_GAIN = 1.0
PER_TURN_CORE_GAIN = 0.35


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def change_region_population(region: Region, amount: int) -> int:
    previous_population = region.population
    if previous_population <= 0 and amount <= 0:
        return 0
    region.population = max(0, region.population + amount)
    return region.population - previous_population


def apply_region_population_loss(region: Region, ratio: float, *, minimum_loss: int = 1) -> int:
    if region.population <= 0:
        return 0
    loss = max(minimum_loss, int(round(region.population * max(0.0, ratio))))
    return -change_region_population(region, -loss)


def estimate_region_population(
    resources: int,
    neighbor_count: int,
    owner: str | None = None,
) -> int:
    if owner is None:
        return 0
    estimate = (
        POPULATION_BASE
        + (resources * POPULATION_PER_RESOURCE)
        + (neighbor_count * POPULATION_PER_CONNECTION)
    )
    estimate += POPULATION_STARTING_OWNER_BONUS
    return max(POPULATION_MINIMUM, estimate)


def update_region_populations(world: WorldState) -> None:
    for region in world.regions.values():
        if region.population <= 0:
            continue
        growth_factor = POPULATION_GROWTH_PER_TURN
        if region.owner is None:
            growth_factor *= POPULATION_UNOWNED_GROWTH_FACTOR
        unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
        growth_factor -= unrest_ratio * POPULATION_UNREST_GROWTH_PENALTY * POPULATION_GROWTH_PER_TURN

        change = int(round(region.population * growth_factor))
        if change == 0 and growth_factor > 0:
            change = 1
        if change != 0:
            change_region_population(region, change)


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


def set_region_secession_cooldown(region: Region, turns: int) -> None:
    region.secession_cooldown_turns = max(0, turns)


def _normalize_rebel_name_seed(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _build_rebel_faction_name(world: WorldState, region: Region) -> str:
    base_name = _normalize_rebel_name_seed(f"{region.ui_name} Rebels")
    candidate = base_name
    suffix = 2
    while candidate in world.factions:
        candidate = f"{base_name} {suffix}"
        suffix += 1
    return candidate


def _next_dynamic_internal_id(world: WorldState) -> str:
    existing_ids = {
        faction.internal_id
        for faction in world.factions.values()
    }
    next_index = 1
    while f"Faction{next_index}" in existing_ids:
        next_index += 1
    return f"Faction{next_index}"


def create_rebel_faction(world: WorldState, region: Region, former_owner: str) -> str:
    from src.doctrine import initialize_rebel_faction_doctrine

    rebel_name = _build_rebel_faction_name(world, region)
    rebel_identity = FactionIdentity(
        internal_id=_next_dynamic_internal_id(world),
        culture_name=_normalize_rebel_name_seed(region.ui_name),
        government_type="Rebels",
        display_name=rebel_name,
        generation_method="rebel_secession",
        inspirations=[former_owner],
    )
    world.factions[rebel_name] = Faction(
        name=rebel_name,
        treasury=REBEL_STARTING_TREASURY,
        identity=rebel_identity,
        starting_treasury=REBEL_STARTING_TREASURY,
        is_rebel=True,
        origin_faction=former_owner,
        rebel_age=0,
        independence_score=0.0,
        proto_state=True,
    )
    initialize_rebel_faction_doctrine(
        world,
        rebel_name,
        former_owner,
        region.name,
    )
    seed_rebel_origin_relationship(world, rebel_name, former_owner)
    return rebel_name


def mature_rebel_faction(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    if not faction.is_rebel or not faction.proto_state:
        return

    faction.proto_state = False
    faction.treasury += REBEL_INDEPENDENCE_TREASURY_BONUS
    if faction.identity is not None:
        faction.identity.government_type = REBEL_MATURE_GOVERNMENT_TYPE
        faction.identity.display_name = (
            f"{faction.identity.culture_name} {REBEL_MATURE_GOVERNMENT_TYPE}"
        )

    world.events.append(Event(
        turn=world.turn,
        type="rebel_independence",
        faction=faction_name,
        details={
            "origin_faction": faction.origin_faction,
            "rebel_age": faction.rebel_age,
            "independence_score": round(faction.independence_score, 2),
            "government_type": faction.government_type,
        },
        impact={
            "treasury_after": faction.treasury,
            "treasury_change": REBEL_INDEPENDENCE_TREASURY_BONUS,
            "proto_state": False,
        },
        tags=["rebel", "independence", "statehood"],
        significance=faction.independence_score,
    ))


def get_rebel_reclaim_bonus(
    attacker_faction_name: str,
    defender_faction_name: str | None,
    world: WorldState,
) -> int:
    if defender_faction_name is None or defender_faction_name not in world.factions:
        return 0

    defender_faction = world.factions[defender_faction_name]
    if (
        not defender_faction.is_rebel
        or defender_faction.origin_faction != attacker_faction_name
        or not defender_faction.proto_state
    ):
        return 0

    independence_ratio = min(
        1.0,
        defender_faction.independence_score / max(0.1, REBEL_FULL_INDEPENDENCE_THRESHOLD),
    )
    bonus = int(round(REBEL_PARENT_RECLAIM_MAX_BONUS * (1.0 - independence_ratio)))
    return max(0, bonus)


def update_rebel_faction_status(world: WorldState) -> None:
    owned_region_counts: dict[str, int] = {
        faction_name: 0
        for faction_name in world.factions
    }
    for region in world.regions.values():
        if region.owner in owned_region_counts:
            owned_region_counts[region.owner] += 1

    for faction_name, faction in world.factions.items():
        if not faction.is_rebel:
            continue

        owned_regions = owned_region_counts.get(faction_name, 0)
        if owned_regions <= 0:
            continue

        faction.rebel_age += 1
        faction.independence_score = round(
            min(
                REBEL_FULL_INDEPENDENCE_THRESHOLD,
                faction.independence_score
                + REBEL_INDEPENDENCE_PER_TURN
                + max(0, owned_regions - 1) * REBEL_INDEPENDENCE_PER_EXTRA_REGION,
            ),
            2,
        )
        if (
            faction.proto_state
            and faction.independence_score >= REBEL_FULL_INDEPENDENCE_THRESHOLD
        ):
            mature_rebel_faction(world, faction_name)


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
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
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
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
    elif previous_owner is None:
        set_region_unrest(region, UNREST_EXPANSION_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
    else:
        set_region_unrest(region, UNREST_CONQUEST_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)


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
    population_before = region.population
    unrest_before = region.unrest
    region.resources = max(1, region.resources - UNREST_SECESSION_RESOURCE_LOSS)
    population_loss = apply_region_population_loss(region, POPULATION_SECESSION_LOSS)
    rebel_faction_name = create_rebel_faction(world, region, former_owner)
    region.owner = rebel_faction_name
    set_region_integration(
        region,
        owner=rebel_faction_name,
        score=CORE_INTEGRATION_SCORE,
        ownership_turns=1,
        core_status="core",
    )
    set_region_unrest(region, REBEL_STARTING_UNREST)
    clear_region_unrest_event(region)
    reset_region_crisis_streak(region)
    set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)

    world.events.append(Event(
        turn=world.turn,
        type="unrest_secession",
        faction=former_owner,
        region=region.name,
        details={
            "former_owner": former_owner,
            "rebel_faction": rebel_faction_name,
            "unrest": round(unrest_before, 2),
            "population_before": population_before,
            "population_after": region.population,
            "population_loss": population_loss,
        },
        impact={
            "owner_after": rebel_faction_name,
            "resource_change": region.resources - resources_before,
            "new_resources": region.resources,
            "population_change": region.population - population_before,
            "population_after": region.population,
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
            set_region_secession_cooldown(region, 0)
            continue

        if region.secession_cooldown_turns > 0:
            region.secession_cooldown_turns -= 1

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
            apply_region_population_loss(
                region,
                POPULATION_UNREST_CRISIS_LOSS,
                minimum_loss=1,
            )
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
        owner_faction = world.factions.get(region.owner)
        if owner_faction is not None and owner_faction.is_rebel:
            if (
                region.unrest_event_level == "crisis"
                and region.unrest_crisis_streak >= UNREST_SECESSION_CRISIS_TURNS
                and region.unrest >= UNREST_SECESSION_THRESHOLD
            ):
                set_region_unrest(
                    region,
                    max(
                        UNREST_CRITICAL_THRESHOLD - 0.5,
                        region.unrest - REBEL_RECURSIVE_UNREST_REDUCTION,
                    ),
                )
                clear_region_unrest_event(region)
                reset_region_crisis_streak(region)
            if region.unrest_event_turns_remaining > 0:
                region.unrest_event_turns_remaining -= 1
                if region.unrest_event_turns_remaining <= 0:
                    clear_region_unrest_event(region)
            continue
        if (
            region.unrest_event_level == "crisis"
            and region.secession_cooldown_turns <= 0
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
            "population": region.population,
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
