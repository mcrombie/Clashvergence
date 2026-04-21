from __future__ import annotations

from src.models import WorldState


def _normalize_faction_name_list(faction_names: list[str] | set[str] | tuple[str, ...], world: WorldState) -> list[str]:
    return sorted(
        {
            faction_name
            for faction_name in faction_names
            if faction_name in world.factions
        }
    )


def _normalize_region_name_list(region_names: list[str] | set[str] | tuple[str, ...], world: WorldState) -> list[str]:
    return sorted(
        {
            region_name
            for region_name in region_names
            if region_name in world.regions
        }
    )


def faction_knows_region(world: WorldState, faction_name: str, region_name: str) -> bool:
    faction = world.factions.get(faction_name)
    if faction is None:
        return False
    if (
        not faction.known_regions
        and not faction.visible_regions
        and not faction.known_factions
    ):
        return True
    return region_name in set(faction.known_regions or [])


def get_faction_known_regions(world: WorldState, faction_name: str) -> set[str]:
    faction = world.factions.get(faction_name)
    if faction is None:
        return set()
    return set(faction.known_regions or [])


def get_faction_visible_regions(world: WorldState, faction_name: str) -> set[str]:
    faction = world.factions.get(faction_name)
    if faction is None:
        return set()
    return set(faction.visible_regions or [])


def faction_knows_faction(world: WorldState, faction_name: str, other_faction_name: str) -> bool:
    if faction_name == other_faction_name:
        return True
    faction = world.factions.get(faction_name)
    if faction is None:
        return False
    if (
        not faction.known_regions
        and not faction.visible_regions
        and not faction.known_factions
    ):
        return True
    return other_faction_name in set(faction.known_factions or [])


def get_faction_known_factions(world: WorldState, faction_name: str) -> set[str]:
    faction = world.factions.get(faction_name)
    if faction is None:
        return set()
    known_factions = set(faction.known_factions or [])
    known_factions.add(faction_name)
    return known_factions


def reveal_factions_for_faction(
    world: WorldState,
    faction_name: str,
    faction_names: list[str] | set[str] | tuple[str, ...],
) -> list[str]:
    faction = world.factions.get(faction_name)
    if faction is None:
        return []
    known_factions = get_faction_known_factions(world, faction_name)
    known_factions.update(
        other_faction_name
        for other_faction_name in faction_names
        if other_faction_name in world.factions
    )
    faction.known_factions = _normalize_faction_name_list(known_factions, world)
    return faction.known_factions


def establish_faction_contact(world: WorldState, faction_a: str, faction_b: str) -> None:
    if faction_a not in world.factions or faction_b not in world.factions:
        return
    reveal_factions_for_faction(world, faction_a, [faction_a, faction_b])
    reveal_factions_for_faction(world, faction_b, [faction_a, faction_b])


def get_faction_owned_regions(world: WorldState, faction_name: str) -> set[str]:
    return {
        region.name
        for region in world.regions.values()
        if region.owner == faction_name
    }


def reveal_regions_for_faction(
    world: WorldState,
    faction_name: str,
    region_names: list[str] | set[str] | tuple[str, ...],
) -> list[str]:
    faction = world.factions.get(faction_name)
    if faction is None:
        return []
    known_regions = get_faction_known_regions(world, faction_name)
    known_regions.update(region_name for region_name in region_names if region_name in world.regions)
    faction.known_regions = _normalize_region_name_list(known_regions, world)
    return faction.known_regions


def refresh_faction_visibility(world: WorldState, faction_name: str) -> list[str]:
    faction = world.factions.get(faction_name)
    if faction is None:
        return []

    visible_regions = get_faction_owned_regions(world, faction_name)
    for region_name in tuple(visible_regions):
        visible_regions.update(world.regions[region_name].neighbors)

    faction.visible_regions = _normalize_region_name_list(visible_regions, world)
    reveal_regions_for_faction(world, faction_name, faction.visible_regions)
    reveal_factions_for_faction(world, faction_name, [faction_name])
    for region_name in faction.visible_regions:
        owner_name = world.regions[region_name].owner
        if owner_name is None:
            continue
        establish_faction_contact(world, faction_name, owner_name)
    return faction.visible_regions


def refresh_all_faction_visibility(world: WorldState) -> None:
    for faction_name in world.factions:
        refresh_faction_visibility(world, faction_name)


def initialize_faction_visibility(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        homeland_region_name = faction.doctrine_state.homeland_region
        if homeland_region_name is None or homeland_region_name not in world.regions:
            owned_regions = get_faction_owned_regions(world, faction_name)
            faction.visible_regions = _normalize_region_name_list(owned_regions, world)
            faction.known_regions = list(faction.visible_regions)
            faction.known_factions = _normalize_faction_name_list([faction_name], world)
            continue

        initial_regions = {homeland_region_name}
        initial_regions.update(world.regions[homeland_region_name].neighbors)
        faction.visible_regions = _normalize_region_name_list(initial_regions, world)
        faction.known_regions = list(faction.visible_regions)
        faction.known_factions = _normalize_faction_name_list([faction_name], world)

    for faction_name in world.factions:
        refresh_faction_visibility(world, faction_name)


def inherit_parent_visibility(
    world: WorldState,
    faction_name: str,
    parent_faction_name: str,
    *,
    extra_region_names: list[str] | set[str] | tuple[str, ...] = (),
) -> None:
    faction = world.factions.get(faction_name)
    parent_faction = world.factions.get(parent_faction_name)
    if faction is None:
        return

    inherited_regions: set[str] = set(extra_region_names)
    if parent_faction is not None:
        inherited_regions.update(parent_faction.known_regions or [])

    faction.known_regions = _normalize_region_name_list(inherited_regions, world)
    inherited_factions = {faction_name}
    if parent_faction is not None:
        inherited_factions.update(parent_faction.known_factions or [])
        inherited_factions.add(parent_faction_name)
    faction.known_factions = _normalize_faction_name_list(inherited_factions, world)
    refresh_faction_visibility(world, faction_name)
