from __future__ import annotations

from src.heartland import (
    POLITY_ADVANCEMENT_UNREST_REDUCTION,
    evolve_faction_religion_politics,
    evolve_faction_succession_politics,
    get_region_surplus,
    handle_region_owner_change,
    set_region_unrest,
)
from src.models import Event, Faction, Region, WorldState
from src.region_naming import format_region_reference
from src.region_state import get_region_core_status


BAND_MIGRATION_COST = 1
BAND_MIGRATION_POPULATION_SHARE = 0.86
BAND_MIGRATION_MIN_REMAINDER = 18
BAND_TRIBALIZATION_THRESHOLD = 1.0
BAND_TRIBALIZATION_MIN_SETTLED_TURNS = 3
BAND_TRIBALIZATION_MIN_POPULATION = 120


def is_band_faction(faction: Faction | None) -> bool:
    return faction is not None and faction.polity_tier == "band"


def get_band_camp_region_name(world: WorldState, faction_name: str) -> str | None:
    owned_regions = _get_owned_regions(world, faction_name)
    if not owned_regions:
        return None
    return max(owned_regions, key=lambda region: _score_band_camp_region(world, region)).name


def enforce_band_region_limit(
    world: WorldState,
    faction_name: str,
    *,
    preferred_region_name: str | None = None,
    reason: str = "region_limit",
    emit_event: bool = True,
) -> list[str]:
    faction = world.factions.get(faction_name)
    if not is_band_faction(faction):
        return []

    owned_regions = _get_owned_regions(world, faction_name)
    if len(owned_regions) <= 1:
        return []

    if preferred_region_name in world.regions and world.regions[preferred_region_name].owner == faction_name:
        camp_region = world.regions[preferred_region_name]
    else:
        camp_region = max(owned_regions, key=lambda region: _score_band_camp_region(world, region))

    abandoned_regions: list[str] = []
    for region in owned_regions:
        if region.name == camp_region.name:
            continue
        abandoned_regions.append(region.name)
        handle_region_owner_change(region, None)

    faction.last_migration_reason = reason
    if abandoned_regions and emit_event:
        world.events.append(
            Event(
                turn=world.turn,
                type="band_region_limit",
                faction=faction_name,
                region=camp_region.name,
                details={
                    "camp_region": camp_region.name,
                    "abandoned_regions": abandoned_regions,
                    "reason": reason,
                    "region_reference": format_region_reference(camp_region, include_code=True),
                },
                tags=["band", "migration", "region_limit"],
                significance=0.35,
            )
        )
    return abandoned_regions


def update_nomadic_social_forms(world: WorldState) -> list[Event]:
    events: list[Event] = []
    for faction_name, faction in world.factions.items():
        if not is_band_faction(faction):
            continue
        if faction_name in set(getattr(world, "inactive_factions", [])):
            continue

        abandoned_regions = enforce_band_region_limit(
            world,
            faction_name,
            reason="year_end_region_limit",
            emit_event=True,
        )
        if abandoned_regions and world.events:
            events.append(world.events[-1])

        camp_region_name = get_band_camp_region_name(world, faction_name)
        if camp_region_name is None:
            faction.migration_pressure = 1.0
            faction.tribalization_progress = 0.0
            faction.band_settled_turns = 0
            continue

        camp_region = world.regions[camp_region_name]
        pressure = calculate_band_migration_pressure(world, faction_name, camp_region)
        faction.migration_pressure = pressure
        faction.migration_cooldown_turns = max(0, int(faction.migration_cooldown_turns or 0) - 1)
        faction.band_settled_turns += 1
        faction.tribalization_progress = min(
            BAND_TRIBALIZATION_THRESHOLD,
            round(
                float(faction.tribalization_progress or 0.0)
                + _calculate_tribalization_gain(world, faction, camp_region, pressure),
                3,
            ),
        )

        if _band_is_ready_to_tribalize(faction, camp_region):
            events.append(_promote_band_to_tribe(world, faction_name, camp_region))

    return events


def record_band_migration(
    world: WorldState,
    faction_name: str,
    *,
    target_region_name: str,
    previous_region_name: str | None,
    abandoned_regions: list[str],
) -> None:
    faction = world.factions[faction_name]
    faction.band_settled_turns = 0
    faction.migration_cooldown_turns = max(1, int(faction.migration_cooldown_turns or 0))
    faction.last_migration_reason = "frontier_migration"
    faction.last_migration_turn = world.turn
    faction.migration_pressure = calculate_band_migration_pressure(
        world,
        faction_name,
        world.regions[target_region_name],
    )
    if previous_region_name and previous_region_name != target_region_name:
        faction.tribalization_progress = max(
            0.0,
            round(float(faction.tribalization_progress or 0.0) - 0.08, 3),
        )
    if abandoned_regions:
        faction.last_migration_reason = "camp_relocation"


def calculate_band_migration_pressure(
    world: WorldState,
    faction_name: str,
    camp_region: Region | None = None,
) -> float:
    faction = world.factions[faction_name]
    camp_region_name = get_band_camp_region_name(world, faction_name)
    camp_region = camp_region or (
        world.regions[camp_region_name]
        if camp_region_name is not None
        else None
    )
    if camp_region is None:
        return 1.0

    food_consumption = max(1.0, float(camp_region.food_consumption or faction.food_consumption or 1.0))
    food_deficit_pressure = max(0.0, float(camp_region.food_deficit or 0.0)) / food_consumption
    surplus_pressure = max(0.0, -get_region_surplus(camp_region, world)) * 0.16
    unrest_pressure = min(0.42, float(camp_region.unrest or 0.0) / 18.0)
    shock_pressure = min(0.25, float(camp_region.shock_exposure or 0.0) * 0.35)
    crowding_pressure = max(0.0, (camp_region.population - 420) / 1400.0)
    return round(
        max(0.0, min(1.0, food_deficit_pressure + surplus_pressure + unrest_pressure + shock_pressure + crowding_pressure)),
        3,
    )


def _get_owned_regions(world: WorldState, faction_name: str) -> list[Region]:
    return [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]


def _score_band_camp_region(world: WorldState, region: Region) -> tuple[float, int, str]:
    status_bonus = 90 if get_region_core_status(region) == "homeland" else 30 if get_region_core_status(region) == "core" else 0
    return (
        region.population + (get_region_surplus(region, world) * 35.0) + status_bonus,
        len(region.neighbors),
        region.name,
    )


def _calculate_tribalization_gain(
    world: WorldState,
    faction: Faction,
    camp_region: Region,
    pressure: float,
) -> float:
    surplus = get_region_surplus(camp_region, world)
    settlement_bonus = {
        "wild": 0.0,
        "rural": 0.06,
        "town": 0.11,
        "city": 0.14,
    }.get(camp_region.settlement_level, 0.0)
    population_bonus = min(0.1, camp_region.population / 2400.0)
    surplus_bonus = min(0.08, max(0.0, surplus) * 0.025)
    stability_bonus = max(0.0, 0.16 - pressure * 0.18)
    continuity_bonus = min(0.06, max(0, faction.band_settled_turns - 1) * 0.015)
    return round(0.08 + settlement_bonus + population_bonus + surplus_bonus + stability_bonus + continuity_bonus, 3)


def _band_is_ready_to_tribalize(faction: Faction, camp_region: Region) -> bool:
    return (
        float(faction.tribalization_progress or 0.0) >= BAND_TRIBALIZATION_THRESHOLD
        and int(faction.band_settled_turns or 0) >= BAND_TRIBALIZATION_MIN_SETTLED_TURNS
        and camp_region.population >= BAND_TRIBALIZATION_MIN_POPULATION
        and camp_region.settlement_level in {"rural", "town", "city"}
    )


def _promote_band_to_tribe(
    world: WorldState,
    faction_name: str,
    camp_region: Region,
) -> Event:
    faction = world.factions[faction_name]
    previous_tier = faction.polity_tier
    previous_form = faction.government_form
    old_government_type = faction.government_type
    refresh_display_name = (
        faction.identity is not None
        and faction.identity.display_name == faction.identity.default_display_name()
    )
    if faction.identity is not None:
        faction.identity.set_government_structure(
            "tribe",
            "council",
            update_display_name=refresh_display_name,
        )
    evolve_faction_succession_politics(
        faction,
        previous_tier=previous_tier,
        previous_form=previous_form,
    )
    evolve_faction_religion_politics(
        faction,
        previous_tier=previous_tier,
        previous_form=previous_form,
    )
    faction.tribalization_progress = BAND_TRIBALIZATION_THRESHOLD
    faction.migration_pressure = calculate_band_migration_pressure(world, faction_name, camp_region)
    for region in world.regions.values():
        if region.owner == faction_name:
            set_region_unrest(
                region,
                max(0.0, region.unrest - POLITY_ADVANCEMENT_UNREST_REDUCTION),
            )

    event = Event(
        turn=world.turn,
        type="social_form_transition",
        faction=faction_name,
        region=camp_region.name,
        details={
            "from": previous_tier,
            "to": "tribe",
            "old_government_type": old_government_type,
            "new_government_type": faction.government_type,
            "tribalization_progress": faction.tribalization_progress,
            "settled_turns": faction.band_settled_turns,
            "population": camp_region.population,
            "migration_pressure": faction.migration_pressure,
            "region_reference": format_region_reference(camp_region, include_code=True),
        },
        tags=["social_form", "band", "tribe", "advancement"],
        significance=1.0,
    )
    world.events.append(event)
    return event
