from __future__ import annotations

from src.climate import normalize_climate
from src.doctrine import (
    CLIMATE_EXPERIENCE_MULTIPLIER,
    HOMELAND_IMPRINT_WEIGHT,
    compute_faction_doctrine_profile,
)
from src.ethnicity import seed_region_ethnicity
from src.integration import handle_region_owner_change
from src.models import Event, WorldState
from src.population import estimate_region_population_from_resource_profile
from src.region_naming import assign_region_founding_name
from src.religion import seed_region_religion
from src.terrain import normalize_terrain_tags


def is_faction_inactive(world: WorldState, faction_name: str) -> bool:
    return faction_name in set(getattr(world, "inactive_factions", []))


def get_active_faction_names(world: WorldState) -> list[str]:
    inactive = set(getattr(world, "inactive_factions", []))
    return [
        faction_name
        for faction_name in world.factions
        if faction_name not in inactive
    ]


def apply_due_faction_arrivals(world: WorldState) -> list[Event]:
    arrivals = getattr(world, "faction_arrivals", {}) or {}
    if not arrivals or not getattr(world, "inactive_factions", []):
        return []

    arrival_events: list[Event] = []
    for faction_name in list(world.inactive_factions):
        arrival = arrivals.get(faction_name)
        if not arrival:
            world.inactive_factions.remove(faction_name)
            continue
        arrival_turn = int(arrival.get("arrival_turn", 0) or 0)
        if arrival_turn > world.turn:
            continue
        arrival_events.append(_activate_faction_arrival(world, faction_name, arrival))
    return arrival_events


def _apply_arrival_technologies(faction, initial_technologies: dict) -> None:
    if not initial_technologies:
        return
    for tech_key, value in initial_technologies.items():
        clamped = max(0.0, min(1.0, float(value)))
        current_known = faction.known_technologies.get(tech_key, 0.0)
        current_institutional = faction.institutional_technologies.get(tech_key, 0.0)
        faction.known_technologies[tech_key] = max(current_known, clamped)
        faction.institutional_technologies[tech_key] = max(current_institutional, clamped)


def _activate_faction_arrival(
    world: WorldState,
    faction_name: str,
    arrival: dict,
) -> Event:
    from src.civilization_cycle import initialize_established_civilization_cycle

    if faction_name not in world.factions:
        raise ValueError(f"Arrival references unknown faction: {faction_name}")

    region_name = str(arrival.get("entry_region") or "").strip()
    if region_name not in world.regions:
        raise ValueError(f"Arrival references unknown region: {region_name}")

    region = world.regions[region_name]
    faction = world.factions[faction_name]
    previous_owner = region.owner
    settler_population = _add_colonial_population(world, faction_name, region_name)

    handle_region_owner_change(region, faction_name)
    if not region.founding_name:
        assign_region_founding_name(
            world,
            region_name,
            faction_name,
            is_homeland=False,
        )
    _initialize_arrival_doctrine(world, faction_name, region_name)
    _apply_arrival_technologies(faction, arrival.get("initial_technologies") or {})
    initialize_established_civilization_cycle(faction)

    if faction_name in world.inactive_factions:
        world.inactive_factions.remove(faction_name)

    event = Event(
        turn=world.turn,
        type="colonial_arrival",
        faction=faction_name,
        region=region_name,
        details={
            "arrival_type": arrival.get("arrival_type", "colonial_landing"),
            "status": arrival.get("status", "foreign_colony"),
            "origin": arrival.get("origin", "foreign land"),
            "owner_before": previous_owner,
            "owner_after": faction_name,
            "settler_population": settler_population,
            "culture": faction.culture_name,
            "disruptive": True,
        },
        tags=["arrival", "colonial", "disruptive"],
        significance=0.9,
    )
    world.events.append(event)
    return event


def _add_colonial_population(
    world: WorldState,
    faction_name: str,
    region_name: str,
) -> int:
    region = world.regions[region_name]
    faction = world.factions[faction_name]
    ethnicity_name = faction.primary_ethnicity or faction.culture_name
    religion_name = faction.religion.official_religion

    if region.population <= 0:
        region.population = estimate_region_population_from_resource_profile(
            region,
            owner=faction_name,
        )
        settler_population = region.population
        if ethnicity_name:
            seed_region_ethnicity(region, ethnicity_name)
        if religion_name:
            seed_region_religion(region, religion_name)
        return settler_population

    settler_population = max(20, int(round(region.population * 0.25)))
    region.population += settler_population
    if ethnicity_name:
        region.ethnic_composition[ethnicity_name] = (
            region.ethnic_composition.get(ethnicity_name, 0)
            + settler_population
        )
    if religion_name:
        region.religious_composition[religion_name] = (
            region.religious_composition.get(religion_name, 0)
            + settler_population
        )
    return settler_population


def _initialize_arrival_doctrine(
    world: WorldState,
    faction_name: str,
    region_name: str,
) -> None:
    faction = world.factions[faction_name]
    region = world.regions[region_name]
    terrain_tags = normalize_terrain_tags(region.terrain_tags or ["plains"])
    climate = normalize_climate(region.climate)
    state = faction.doctrine_state

    state.homeland_region = region_name
    state.homeland_terrain_tags = terrain_tags
    state.homeland_climate = climate
    state.terrain_experience = {
        tag: max(state.terrain_experience.get(tag, 0.0), HOMELAND_IMPRINT_WEIGHT)
        for tag in terrain_tags
    }
    state.climate_experience = {
        climate: max(
            state.climate_experience.get(climate, 0.0),
            HOMELAND_IMPRINT_WEIGHT * CLIMATE_EXPERIENCE_MULTIPLIER,
        )
    }
    state.starting_regions = max(1, int(state.starting_regions or 0))
    state.last_region_count = 1
    state.peak_regions = max(1, int(state.peak_regions or 0))
    state.cumulative_regions_held = max(1, int(state.cumulative_regions_held or 0))
    faction.doctrine_profile = compute_faction_doctrine_profile(
        faction,
        total_regions=len(world.regions),
    )
