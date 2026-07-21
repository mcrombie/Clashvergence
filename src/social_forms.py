from __future__ import annotations

from collections import deque
from copy import deepcopy
import re

from src.config import BAND_TRIBALIZATION_MIN_POPULATION
from src.heartland import (
    CONQUEST_INTEGRATION_SCORE,
    CORE_INTEGRATION_SCORE,
    HOMELAND_INTEGRATION_SCORE,
    POLITY_ADVANCEMENT_UNREST_REDUCTION,
    evolve_faction_religion_politics,
    evolve_faction_succession_politics,
    get_region_surplus,
    handle_region_owner_change,
    set_region_integration,
    set_region_unrest,
)
from src.models import Event, Faction, FactionIdentity, LanguageProfile, Region, WorldState
from src.polity_naming import (
    choose_unique_culture_name,
    ensure_unique_faction_display_name,
    refresh_culture_roots,
    register_culture_name,
)
from src.population import transfer_region_population
from src.region_naming import assign_region_founding_name, format_region_reference
from src.region_state import get_region_core_status


BAND_MIGRATION_COST = 1
BAND_MIGRATION_POPULATION_SHARE = 1.0
BAND_MIGRATION_MIN_REMAINDER = 0
BAND_TRIBALIZATION_THRESHOLD = 1.0
BAND_TRIBALIZATION_MIN_SETTLED_TURNS = 3
BAND_HOMELAND_MIN_ROAMING_TURNS = 3
BAND_NOMADIC_TRIBE_MIN_ROAMING_TURNS = 5
BAND_HOMELAND_APPEAL_THRESHOLD = 11.5
BAND_NOMADIC_TRIBE_APPEAL_CEILING = 10.0
NOMADIC_TRIBE_FRAGMENTATION_THRESHOLD = 0.62
NOMADIC_TRIBE_FRAGMENTATION_COOLDOWN = 3
NOMADIC_SPLINTER_BAND_EPITHETS = (
    "Wayfarer",
    "Trail",
    "Wind",
    "Dawn",
    "River",
    "Stone",
    "Reed",
    "Ash",
    "Hearth",
    "Moon",
    "Sun",
    "Vale",
)
NOMADIC_SPLINTER_BAND_SECONDARIES = (
    "Path",
    "Road",
    "Ridge",
    "Steppe",
    "Hollow",
    "Spring",
    "Cairn",
    "Crossing",
)

REGION_FEATURE_WORDS = {
    "basin",
    "bay",
    "coast",
    "coasts",
    "desert",
    "downs",
    "field",
    "fields",
    "flat",
    "flats",
    "forest",
    "forests",
    "gate",
    "heath",
    "heights",
    "hill",
    "hills",
    "island",
    "islands",
    "isle",
    "isles",
    "lake",
    "lakes",
    "lowlands",
    "marsh",
    "marshes",
    "moor",
    "moors",
    "mount",
    "mountain",
    "mountains",
    "pass",
    "plain",
    "plains",
    "plateau",
    "range",
    "river",
    "rivers",
    "shore",
    "shores",
    "steppe",
    "stones",
    "valley",
    "woods",
}
DIRECTION_WORDS = {
    "central",
    "east",
    "eastern",
    "far",
    "great",
    "inner",
    "lower",
    "north",
    "northern",
    "outer",
    "south",
    "southern",
    "upper",
    "west",
    "western",
}


def is_band_faction(faction: Faction | None) -> bool:
    return faction is not None and faction.polity_tier == "band"


def is_nomadic_tribe(faction: Faction | None) -> bool:
    return faction is not None and faction.polity_tier == "tribe" and faction.social_form == "nomadic_tribe"


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
        handle_region_owner_change(region, None, world)

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
    inactive_factions = set(getattr(world, "inactive_factions", []))
    for faction_name, faction in list(world.factions.items()):
        if faction_name in inactive_factions:
            continue
        if _is_current_turn_arrival(world, faction_name):
            continue

        if is_nomadic_tribe(faction):
            fragmentation_event = _update_nomadic_tribe(world, faction_name, faction)
            if fragmentation_event is not None:
                events.append(fragmentation_event)
            continue

        if not is_band_faction(faction):
            continue

        _initialize_band_social_state(world, faction_name, faction)
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
        _remember_band_region(world, faction, camp_region)
        if faction.social_form == "nomadic_band" and faction.chosen_homeland_region is None:
            roaming_event = _maybe_roam_exploratory_band(world, faction_name, faction, camp_region)
            if roaming_event is not None:
                events.append(roaming_event)
                camp_region_name = get_band_camp_region_name(world, faction_name)
                if camp_region_name is None:
                    continue
                camp_region = world.regions[camp_region_name]
                _remember_band_region(world, faction, camp_region)

            faction.band_roaming_turns += 1
            if _band_should_choose_homeland(faction, camp_region):
                events.append(_choose_band_homeland(world, faction_name, camp_region))
            elif _band_should_become_nomadic_tribe(faction):
                events.append(_promote_band_to_nomadic_tribe(world, faction_name, camp_region))
                continue

        pressure = calculate_band_migration_pressure(world, faction_name, camp_region)
        faction.migration_pressure = pressure
        faction.migration_cooldown_turns = max(0, int(faction.migration_cooldown_turns or 0) - 1)

        if faction.social_form == "sedentary_band" and faction.chosen_homeland_region == camp_region.name:
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
    reason: str = "frontier_migration",
) -> None:
    faction = world.factions[faction_name]
    faction.band_settled_turns = 0
    faction.migration_cooldown_turns = max(1, int(faction.migration_cooldown_turns or 0))
    faction.last_migration_reason = reason
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
        faction.last_migration_reason = reason or "camp_relocation"


def migrate_band_to_region(
    world: WorldState,
    faction_name: str,
    target_region_name: str,
    *,
    reason: str = "seasonal_roaming",
) -> Event | None:
    if target_region_name not in world.regions:
        return None
    faction = world.factions.get(faction_name)
    if not is_band_faction(faction):
        return None
    previous_camp_region_name = get_band_camp_region_name(world, faction_name)
    if previous_camp_region_name == target_region_name:
        return None
    if previous_camp_region_name is None:
        return None

    from src.actions import get_expand_event_tags, get_expand_target_score_components

    target_region = world.regions[target_region_name]
    if target_region.owner not in {None, faction_name}:
        return None

    source_region = world.regions[previous_camp_region_name]
    source_population_before = source_region.population
    target_population_before = target_region.population
    score_components = get_expand_target_score_components(
        target_region_name,
        world,
        faction_name=faction_name,
    )
    event_tags = [
        "band",
        "migration",
        reason,
        *[
            tag
            for tag in get_expand_event_tags(score_components)
            if tag not in {"expansion", "territory_gain", "migration", "band"}
        ],
    ]

    handle_region_owner_change(target_region, faction_name, world)
    transferred_population = 0
    if source_region.population > 0:
        mobile_population = int(round(source_region.population * BAND_MIGRATION_POPULATION_SHARE))
        if source_region.population > BAND_MIGRATION_MIN_REMAINDER:
            mobile_population = min(
                mobile_population,
                source_region.population - BAND_MIGRATION_MIN_REMAINDER,
            )
        transferred_population = transfer_region_population(
            source_region,
            target_region,
            max(0, mobile_population),
        )
    region_display_name = assign_region_founding_name(
        world,
        target_region_name,
        faction_name,
        is_homeland=False,
    )
    abandoned_regions = enforce_band_region_limit(
        world,
        faction_name,
        preferred_region_name=target_region_name,
        reason=reason,
        emit_event=False,
    )
    record_band_migration(
        world,
        faction_name,
        target_region_name=target_region_name,
        previous_region_name=previous_camp_region_name,
        abandoned_regions=abandoned_regions,
        reason=reason,
    )
    _remember_band_region(world, faction, target_region)

    event = Event(
        turn=world.turn,
        type="band_migration",
        faction=faction_name,
        region=target_region_name,
        details={
            "cost": 0,
            "migration": True,
            "reason": reason,
            "previous_camp_region": previous_camp_region_name,
            "abandoned_regions": abandoned_regions,
            "tribalization_progress": round(float(faction.tribalization_progress or 0.0), 3),
            "migration_pressure": round(float(faction.migration_pressure or 0.0), 3),
            "roaming_turns": int(faction.band_roaming_turns or 0),
            "homeland_appeal": round(_score_homeland_appeal(world, faction, target_region), 3),
            "best_homeland_candidate": faction.best_homeland_candidate,
            "resources": score_components["resources"],
            "taxable_value": score_components["taxable_value"],
            "neighbors": score_components["neighbors"],
            "unclaimed_neighbors": score_components["unclaimed_neighbors"],
            "score": score_components["score"],
            "terrain_tags": score_components["terrain_tags"],
            "terrain_label": score_components["terrain_label"],
            "terrain_affinity": score_components.get("terrain_affinity", 0.0),
            "climate_affinity": score_components.get("climate_affinity", 0.0),
            "region_display_name": region_display_name,
            "population_source_region": previous_camp_region_name,
            "population_source_before": source_population_before,
            "population_source_after": source_region.population,
            "population_before": target_population_before,
            "population_after": target_region.population,
            "population_transfer": transferred_population,
            "region_reference": format_region_reference(target_region, include_code=True),
        },
        context={
            "treasury_before": faction.treasury,
            "treasury_after": faction.treasury,
            "owner_before": None,
        },
        impact={
            "owner_after": faction_name,
            "treasury_change": 0,
            "regions_gained": 0,
            "population_change": target_region.population - target_population_before,
            "future_expansion_opened": score_components["unclaimed_neighbors"],
            "importance_tier": "exploratory",
            "strategic_role": "nomadic_camp",
            "summary_reason": "the band explored a new camp before choosing a homeland",
            "narrative_tags": event_tags,
        },
        tags=event_tags,
        significance=float(score_components["score"]),
    )
    world.events.append(event)
    return event


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
    crowding_pressure = max(0.0, (camp_region.population - 21000) / 70000.0)
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


def _initialize_band_social_state(world: WorldState, faction_name: str, faction: Faction) -> None:
    if faction.social_form not in {"nomadic_band", "sedentary_band"}:
        legacy_settled_state = (
            bool(faction.chosen_homeland_region)
            or int(faction.band_settled_turns or 0) > 0
            or float(faction.tribalization_progress or 0.0) > 0.0
        )
        faction.social_form = "sedentary_band" if legacy_settled_state else "nomadic_band"
        if legacy_settled_state and faction.chosen_homeland_region is None:
            camp_region_name = get_band_camp_region_name(world, faction_name)
            if camp_region_name is not None:
                faction.chosen_homeland_region = camp_region_name
                world.regions[camp_region_name].homeland_faction_id = faction_name
                set_region_integration(
                    world.regions[camp_region_name],
                    owner=faction_name,
                    score=max(HOMELAND_INTEGRATION_SCORE, float(world.regions[camp_region_name].integration_score or 0.0)),
                    ownership_turns=max(1, int(world.regions[camp_region_name].ownership_turns or 0)),
                    core_status="homeland",
                )
    if faction.social_form == "nomadic_band" and faction.chosen_homeland_region is None:
        _clear_unsettled_band_homelands(world, faction_name)


def _is_current_turn_arrival(world: WorldState, faction_name: str) -> bool:
    arrival = (getattr(world, "faction_arrivals", {}) or {}).get(faction_name)
    if not arrival:
        return False
    return int(arrival.get("arrival_turn", -1) or -1) == int(world.turn or 0)


def _clear_unsettled_band_homelands(world: WorldState, faction_name: str) -> None:
    for region in world.regions.values():
        if region.homeland_faction_id != faction_name:
            continue
        region.homeland_faction_id = None
        if region.owner == faction_name and get_region_core_status(region) == "homeland":
            set_region_integration(
                region,
                owner=faction_name,
                score=min(region.integration_score, CONQUEST_INTEGRATION_SCORE),
                ownership_turns=max(0, int(region.ownership_turns or 0)),
                core_status="frontier",
            )


def _score_band_camp_region(world: WorldState, region: Region) -> tuple[float, int, str]:
    status_bonus = 4500 if get_region_core_status(region) == "homeland" else 1500 if get_region_core_status(region) == "core" else 0
    return (
        region.population + (get_region_surplus(region, world) * 1750.0) + status_bonus,
        len(region.neighbors),
        region.name,
    )


def _score_homeland_appeal(world: WorldState, faction: Faction, region: Region) -> float:
    from src.actions import get_expand_target_score_components

    components = get_expand_target_score_components(
        region.name,
        world,
        faction_name=faction.name,
    )
    surplus = get_region_surplus(region, world)
    stability = max(0.0, 6.0 - float(region.unrest or 0.0)) * 0.18
    food_security = max(0.0, surplus) * 0.42
    population_anchor = min(1.6, region.population / 18000.0)
    open_frontier = min(1.5, components["unclaimed_neighbors"] * 0.35)
    appeal = (
        float(components["score"])
        + food_security
        + stability
        + population_anchor
        + open_frontier
    )
    # Strongly prefer agenda target regions so they always win the best_homeland_candidate race,
    # even if they're desert/low-resource (e.g. Pyrosi targeting West/East Pyros).
    if faction.agenda is not None:
        if (
            faction.agenda.agenda_type == "settle_region"
            and region.name == faction.agenda.params.get("target_region")
        ):
            appeal += 8.0
        elif (
            faction.agenda.agenda_type == "hold_regions"
            and region.name in (faction.agenda.params.get("regions") or [])
        ):
            appeal += 8.0
    return round(appeal, 3)


def _remember_band_region(world: WorldState, faction: Faction, region: Region) -> None:
    if region.name not in faction.band_explored_regions:
        faction.band_explored_regions.append(region.name)
    if region.name not in faction.nomadic_identity_regions:
        faction.nomadic_identity_regions.append(region.name)

    appeal = _score_homeland_appeal(world, faction, region)
    if (
        not faction.best_homeland_candidate
        or appeal > float(faction.best_homeland_appeal or 0.0)
        or (
            appeal == float(faction.best_homeland_appeal or 0.0)
            and region.name < str(faction.best_homeland_candidate)
        )
    ):
        faction.best_homeland_candidate = region.name
        faction.best_homeland_appeal = appeal


def _maybe_roam_exploratory_band(
    world: WorldState,
    faction_name: str,
    faction: Faction,
    camp_region: Region,
) -> Event | None:
    from src.actions import get_expandable_regions

    # Agenda-driven steering: path toward the settlement target(s) if not there yet.
    agenda = faction.agenda
    if agenda is not None:
        agenda_targets: list[str] = []
        if agenda.agenda_type == "settle_region" and agenda.params.get("target_region"):
            agenda_targets = [agenda.params["target_region"]]
        elif agenda.agenda_type == "hold_regions" and agenda.params.get("regions"):
            agenda_targets = list(agenda.params["regions"])
        reachable_targets = [t for t in agenda_targets if t in world.regions]
        if reachable_targets and camp_region.name not in reachable_targets:
            for target in reachable_targets:
                next_step = _find_roaming_path_step(
                    world,
                    faction_name,
                    start_region_name=camp_region.name,
                    target_region_name=target,
                )
                if next_step is not None:
                    return migrate_band_to_region(
                        world,
                        faction_name,
                        next_step,
                        reason="agenda_migration",
                    )

    if (
        int(faction.band_roaming_turns or 0) >= BAND_HOMELAND_MIN_ROAMING_TURNS
        and faction.best_homeland_candidate
        and faction.best_homeland_candidate != camp_region.name
    ):
        next_step = _find_roaming_path_step(
            world,
            faction_name,
            start_region_name=camp_region.name,
            target_region_name=faction.best_homeland_candidate,
        )
        if next_step is not None:
            return migrate_band_to_region(
                world,
                faction_name,
                next_step,
                reason="return_to_best_camp",
            )

    expandable_regions = get_expandable_regions(faction_name, world)
    if not expandable_regions:
        return None

    candidates = [world.regions[region_name] for region_name in expandable_regions]
    unvisited_candidates = [
        region
        for region in candidates
        if region.name not in set(faction.band_explored_regions or [])
    ]
    is_explorer = faction.agenda is not None and faction.agenda.agenda_type == "explore"
    unvisited_bonus = 6.0 if is_explorer else 2.4
    current_appeal = _score_homeland_appeal(world, faction, camp_region)
    best_candidate = max(
        unvisited_candidates or candidates,
        key=lambda region: (
            _score_homeland_appeal(world, faction, region)
            + (unvisited_bonus if region.name not in set(faction.band_explored_regions or []) else 0.0),
            len(region.neighbors),
            region.name,
        ),
    )
    best_appeal = _score_homeland_appeal(world, faction, best_candidate)
    should_move = int(faction.band_roaming_turns or 0) < BAND_HOMELAND_MIN_ROAMING_TURNS
    should_move = should_move or best_candidate.name == faction.best_homeland_candidate
    should_move = should_move or best_appeal >= current_appeal - 0.75
    if not should_move:
        return None
    return migrate_band_to_region(
        world,
        faction_name,
        best_candidate.name,
        reason="seasonal_roaming",
    )


def _find_roaming_path_step(
    world: WorldState,
    faction_name: str,
    *,
    start_region_name: str,
    target_region_name: str,
) -> str | None:
    if start_region_name == target_region_name:
        return None
    if start_region_name not in world.regions or target_region_name not in world.regions:
        return None
    if world.regions[target_region_name].owner not in {None, faction_name}:
        return None

    queue: deque[tuple[str, list[str]]] = deque([(start_region_name, [])])
    visited = {start_region_name}
    while queue:
        region_name, path = queue.popleft()
        for neighbor_name in _get_roaming_neighbors(world, region_name):
            if neighbor_name in visited or neighbor_name not in world.regions:
                continue
            neighbor = world.regions[neighbor_name]
            if neighbor.owner not in {None, faction_name}:
                continue
            next_path = [*path, neighbor_name]
            if neighbor_name == target_region_name:
                return next_path[0] if next_path else None
            visited.add(neighbor_name)
            queue.append((neighbor_name, next_path))
    return None


def _get_roaming_neighbors(world: WorldState, region_name: str) -> list[str]:
    neighbors = set(world.regions[region_name].neighbors)
    for link in getattr(world, "sea_links", []) or []:
        if len(link) != 2:
            continue
        left, right = link
        if left == region_name:
            neighbors.add(right)
        elif right == region_name:
            neighbors.add(left)
    return sorted(neighbors)


def _band_should_choose_homeland(faction: Faction, camp_region: Region) -> bool:
    min_roaming = BAND_HOMELAND_MIN_ROAMING_TURNS
    if faction.agenda is not None and faction.agenda.agenda_type == "explore":
        min_roaming = 15
    if int(faction.band_roaming_turns or 0) < min_roaming:
        return False
    if faction.best_homeland_candidate != camp_region.name:
        return False
    if faction.agenda is not None:
        if (
            faction.agenda.agenda_type == "settle_region"
            and faction.agenda.params.get("target_region")
            and camp_region.name != faction.agenda.params["target_region"]
        ):
            return False
        if (
            faction.agenda.agenda_type == "hold_regions"
            and faction.agenda.params.get("regions")
            and camp_region.name not in faction.agenda.params["regions"]
        ):
            return False
        if faction.agenda.agenda_type == "expand_territory":
            return False
    return float(faction.best_homeland_appeal or 0.0) >= BAND_HOMELAND_APPEAL_THRESHOLD


def _band_should_become_nomadic_tribe(faction: Faction) -> bool:
    if int(faction.band_roaming_turns or 0) < BAND_NOMADIC_TRIBE_MIN_ROAMING_TURNS:
        return False
    if faction.agenda is not None and faction.agenda.agenda_type == "expand_territory":
        return True
    return float(faction.best_homeland_appeal or 0.0) < BAND_NOMADIC_TRIBE_APPEAL_CEILING


def _region_identity_root(region: Region) -> str:
    name = (region.display_name or region.founding_name or region.name or "").strip()
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    name = re.sub(r"[_-]+", " ", name)
    words = [word for word in re.split(r"\s+", name) if word]
    while len(words) > 1 and words[-1].lower().strip(".,") in REGION_FEATURE_WORDS:
        words.pop()
    while len(words) > 1 and words[0].lower().strip(".,") in DIRECTION_WORDS:
        words.pop(0)
    root = " ".join(words).strip()
    if not root:
        root = region.name or "Homeland"
    return root


def _set_identity_culture_name(
    world: WorldState,
    faction_name: str,
    culture_name: str,
    *,
    region: Region | None = None,
) -> None:
    faction = world.factions[faction_name]
    if faction.identity is None:
        return
    faction.identity.culture_name = choose_unique_culture_name(
        world,
        culture_name,
        region=region,
        faction_name=faction_name,
        language_profile=faction.identity.language_profile,
        display_name_builder=lambda candidate: (
            f"{candidate} {faction.government_type}".strip()
        ),
    )
    faction.identity.display_name = faction.identity.default_display_name()
    refresh_culture_roots(world)


def _choose_band_homeland(
    world: WorldState,
    faction_name: str,
    camp_region: Region,
) -> Event:
    from src.climate import normalize_climate
    from src.doctrine import compute_faction_doctrine_profile
    from src.terrain import normalize_terrain_tags

    faction = world.factions[faction_name]
    root_name = _region_identity_root(camp_region)
    faction.social_form = "sedentary_band"
    faction.chosen_homeland_region = camp_region.name
    # Sync doctrine homeland to the actual settled region so climate/terrain affinity
    # in future expansion scoring reflects this homeland, not the arrival entry point.
    faction.doctrine_state.homeland_region = camp_region.name
    faction.doctrine_state.homeland_climate = normalize_climate(camp_region.climate)
    faction.doctrine_state.homeland_terrain_tags = normalize_terrain_tags(
        camp_region.terrain_tags or ["plains"]
    )
    faction.doctrine_profile = compute_faction_doctrine_profile(
        faction, total_regions=len(world.regions)
    )
    faction.homeland_appeal = float(faction.best_homeland_appeal or _score_homeland_appeal(world, faction, camp_region))
    faction.homeland_claim_source = "settled_band"
    faction.band_settled_turns = 0
    faction.last_migration_reason = "settled_homeland"
    camp_region.homeland_faction_id = faction_name
    set_region_integration(
        camp_region,
        owner=faction_name,
        score=max(HOMELAND_INTEGRATION_SCORE, float(camp_region.integration_score or 0.0)),
        ownership_turns=max(1, int(camp_region.ownership_turns or 0)),
        core_status="homeland",
    )
    set_region_unrest(camp_region, max(0.0, camp_region.unrest - 2.0))
    region_display_name = assign_region_founding_name(
        world,
        camp_region.name,
        faction_name,
        is_homeland=True,
    )
    _set_identity_culture_name(
        world,
        faction_name,
        root_name,
        region=camp_region,
    )

    event = Event(
        turn=world.turn,
        type="homeland_chosen",
        faction=faction_name,
        region=camp_region.name,
        details={
            "homeland_region": camp_region.name,
            "homeland_name_root": root_name,
            "homeland_appeal": round(float(faction.homeland_appeal or 0.0), 3),
            "explored_regions": list(faction.band_explored_regions or []),
            "region_display_name": region_display_name,
            "region_reference": format_region_reference(camp_region, include_code=True),
        },
        tags=["band", "homeland", "settlement"],
        significance=0.85,
    )
    world.events.append(event)
    return event


def _derive_nomadic_identity_name(faction: Faction) -> str:
    base_name = (faction.culture_name or faction.display_name or faction.name or "Nomadic").strip()
    base_name = re.sub(r"\b(Band|Tribe|Chiefdom|Kingdom|Republic|State|Council Realm|Commonwealth)\b", "", base_name).strip()
    if not base_name:
        base_name = faction.name
    return base_name if base_name.lower().endswith(" kin") else f"{base_name} Kin"


def _promote_band_to_nomadic_tribe(
    world: WorldState,
    faction_name: str,
    camp_region: Region,
) -> Event:
    faction = world.factions[faction_name]
    previous_tier = faction.polity_tier
    previous_form = faction.government_form
    old_government_type = faction.government_type
    identity_name = _derive_nomadic_identity_name(faction)
    if faction.identity is not None:
        faction.identity.set_government_structure(
            "tribe",
            "council",
            update_display_name=False,
        )
        faction.identity.culture_name = choose_unique_culture_name(
            world,
            identity_name,
            region=camp_region,
            faction_name=faction_name,
            language_profile=faction.identity.language_profile,
            display_name_builder=lambda candidate: (
                f"{candidate} {faction.government_type}".strip()
            ),
        )
        faction.identity.display_name = faction.identity.default_display_name()
        refresh_culture_roots(world)
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
    faction.social_form = "nomadic_tribe"
    faction.chosen_homeland_region = None
    faction.homeland_appeal = 0.0
    faction.homeland_claim_source = "shared_nomadic_identity"
    faction.tribalization_progress = BAND_TRIBALIZATION_THRESHOLD
    faction.band_settled_turns = 0
    faction.migration_pressure = calculate_band_migration_pressure(world, faction_name, camp_region)
    _clear_unsettled_band_homelands(world, faction_name)
    set_region_integration(
        camp_region,
        owner=faction_name,
        score=max(CORE_INTEGRATION_SCORE, float(camp_region.integration_score or 0.0)),
        ownership_turns=max(1, int(camp_region.ownership_turns or 0)),
        core_status="core",
    )

    event = Event(
        turn=world.turn,
        type="social_form_transition",
        faction=faction_name,
        region=camp_region.name,
        details={
            "from": previous_tier,
            "to": "tribe",
            "social_form": "nomadic_tribe",
            "old_government_type": old_government_type,
            "new_government_type": faction.government_type,
            "homeland_region": None,
            "identity_regions": list(faction.nomadic_identity_regions or []),
            "best_homeland_appeal": round(float(faction.best_homeland_appeal or 0.0), 3),
            "migration_pressure": faction.migration_pressure,
            "region_reference": format_region_reference(camp_region, include_code=True),
        },
        tags=["social_form", "band", "tribe", "nomadic_tribe", "advancement"],
        significance=0.95,
    )
    world.events.append(event)
    return event


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
    population_bonus = min(0.1, camp_region.population / 120000.0)
    surplus_bonus = min(0.08, max(0.0, surplus) * 0.025)
    stability_bonus = max(0.0, 0.16 - pressure * 0.18)
    continuity_bonus = min(0.06, max(0, faction.band_settled_turns - 1) * 0.015)
    return round(0.08 + settlement_bonus + population_bonus + surplus_bonus + stability_bonus + continuity_bonus, 3)


def _band_is_ready_to_tribalize(faction: Faction, camp_region: Region) -> bool:
    return (
        faction.social_form == "sedentary_band"
        and faction.chosen_homeland_region == camp_region.name
        and float(faction.tribalization_progress or 0.0) >= BAND_TRIBALIZATION_THRESHOLD
        and int(faction.band_settled_turns or 0) >= BAND_TRIBALIZATION_MIN_SETTLED_TURNS
        and camp_region.population >= BAND_TRIBALIZATION_MIN_POPULATION
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
            update_display_name=refresh_display_name or faction.social_form == "sedentary_band",
        )
        if refresh_display_name or faction.social_form == "sedentary_band":
            ensure_unique_faction_display_name(
                world,
                faction_name,
                region=camp_region,
            )
        else:
            refresh_culture_roots(world)
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
    faction.social_form = "sedentary_tribe"
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
            "social_form": faction.social_form,
            "homeland_region": faction.chosen_homeland_region,
            "homeland_appeal": round(float(faction.homeland_appeal or 0.0), 3),
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


def _update_nomadic_tribe(
    world: WorldState,
    faction_name: str,
    faction: Faction,
) -> Event | None:
    owned_regions = _get_owned_regions(world, faction_name)
    faction.nomadic_fragmentation_cooldown_turns = max(
        0,
        int(faction.nomadic_fragmentation_cooldown_turns or 0) - 1,
    )
    if not owned_regions:
        faction.nomadic_fragmentation_pressure = 1.0
        faction.nomadic_fragmentation_turns += 1
        return None

    for region in owned_regions:
        if region.name not in faction.nomadic_identity_regions:
            faction.nomadic_identity_regions.append(region.name)

    average_unrest = sum(float(region.unrest or 0.0) for region in owned_regions) / max(1, len(owned_regions))
    pressure = (
        0.18
        + max(0, len(owned_regions) - 1) * 0.13
        + min(0.26, average_unrest / 24.0)
        + min(0.22, float(faction.administrative_overextension_penalty or 0.0) * 0.32)
    )
    if "chaos_pioneers" in faction.faction_traits:
        pressure += 0.16
    faction.nomadic_fragmentation_pressure = round(min(1.0, pressure), 3)
    if faction.nomadic_fragmentation_pressure >= 0.45:
        faction.nomadic_fragmentation_turns += 1
    else:
        faction.nomadic_fragmentation_turns = max(0, int(faction.nomadic_fragmentation_turns or 0) - 1)

    if len(owned_regions) < 2:
        return None
    if int(faction.nomadic_fragmentation_cooldown_turns or 0) > 0:
        return None
    if faction.nomadic_fragmentation_pressure < NOMADIC_TRIBE_FRAGMENTATION_THRESHOLD:
        return None
    return _split_nomadic_tribe(world, faction_name, faction, owned_regions)


def _split_nomadic_tribe(
    world: WorldState,
    faction_name: str,
    faction: Faction,
    owned_regions: list[Region],
) -> Event | None:
    split_region = max(
        owned_regions,
        key=lambda region: (
            get_region_core_status(region) == "frontier",
            float(region.unrest or 0.0),
            -region.population,
            region.name,
        ),
    )
    root_name = _region_identity_root(split_region)
    internal_id = f"{faction.internal_id}_split_{world.turn}_{len(world.factions) + 1}"
    language_profile = (
        deepcopy(faction.identity.language_profile)
        if faction.identity is not None
        else None
    )
    culture_name = choose_unique_culture_name(
        world,
        root_name,
        region=split_region,
        language_profile=language_profile,
        naming_seed=f"{faction_name}:{world.turn}:{split_region.name}:nomadic-splinter",
    )
    display_name = _unique_nomadic_splinter_band_name(world, culture_name)
    identity = FactionIdentity(
        internal_id=internal_id,
        culture_name=culture_name,
        polity_tier="band",
        government_form="leader",
        display_name=display_name,
        language_profile=language_profile if language_profile is not None else LanguageProfile(),
        generation_method="nomadic_splinter",
        inspirations=[faction_name],
    )
    splinter = Faction(
        name=display_name,
        treasury=max(1, int(round(faction.treasury * 0.12))),
        identity=identity,
        starting_treasury=max(1, int(round(faction.treasury * 0.12))),
        primary_ethnicity=faction.primary_ethnicity,
        faction_traits=["nomadic_splinter"],
        origin_faction=faction_name,
        social_form="nomadic_band",
        band_explored_regions=[split_region.name],
        nomadic_identity_regions=[split_region.name],
        best_homeland_candidate=split_region.name,
        best_homeland_appeal=_score_homeland_appeal(world, faction, split_region),
    )
    world.factions[display_name] = splinter
    register_culture_name(world, culture_name)
    faction.treasury = max(0, faction.treasury - splinter.treasury)
    handle_region_owner_change(split_region, display_name, world)
    refresh_culture_roots(world)
    splinter.known_regions = [split_region.name, *split_region.neighbors]
    splinter.visible_regions = [split_region.name, *split_region.neighbors]
    faction.nomadic_fragmentation_cooldown_turns = NOMADIC_TRIBE_FRAGMENTATION_COOLDOWN
    faction.nomadic_fragmentation_turns = 0

    event = Event(
        turn=world.turn,
        type="nomadic_tribe_fragmentation",
        faction=faction_name,
        region=split_region.name,
        details={
            "splinter_faction": display_name,
            "social_form": "nomadic_tribe",
            "fragmentation_pressure": faction.nomadic_fragmentation_pressure,
            "identity_regions": list(faction.nomadic_identity_regions or []),
            "region_reference": format_region_reference(split_region, include_code=True),
        },
        impact={
            "owner_after": display_name,
            "parent_treasury_after": faction.treasury,
            "splinter_treasury": splinter.treasury,
        },
        tags=["nomadic_tribe", "fragmentation", "splinter"],
        significance=0.9,
    )
    world.events.append(event)
    return event


def _unique_nomadic_splinter_band_name(world: WorldState, root_name: str) -> str:
    root = (root_name or "Nomadic").strip() or "Nomadic"
    for epithet in NOMADIC_SPLINTER_BAND_EPITHETS:
        candidate = f"{root} {epithet} Band"
        if candidate not in world.factions:
            return candidate

    for first in NOMADIC_SPLINTER_BAND_EPITHETS:
        for second in NOMADIC_SPLINTER_BAND_SECONDARIES:
            candidate = f"{root} {first}{second} Band"
            if candidate not in world.factions:
                return candidate

    index = 0
    while True:
        suffix = _alphabetic_suffix(index)
        candidate = f"{root} Far-Road {suffix} Band"
        if candidate not in world.factions:
            return candidate
        index += 1


def _alphabetic_suffix(index: int) -> str:
    letters = []
    value = max(0, index)
    while True:
        value, remainder = divmod(value, 26)
        letters.append(chr(ord("A") + remainder))
        if value == 0:
            break
        value -= 1
    return "".join(reversed(letters))


def _unique_faction_name(world: WorldState, base_name: str) -> str:
    if base_name not in world.factions:
        return base_name
    index = 2
    while f"{base_name} {index}" in world.factions:
        index += 1
    return f"{base_name} {index}"
