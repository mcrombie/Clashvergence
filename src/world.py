from src.diplomacy import initialize_relationships
from src.doctrine import initialize_faction_doctrines
from src.factions import create_factions, validate_map_factions
from src.heartland import (
    estimate_region_population,
    estimate_region_population_from_resource_profile,
    initialize_dynastic_politics,
    initialize_heartlands,
    initialize_religious_legitimacy,
    initialize_region_history,
    refresh_administrative_state,
    register_ethnicity,
    seed_region_ethnicity,
    update_region_settlement_levels,
)
from src.models import Region, WorldState
from src.maps import MAPS
from src.map_generator import build_generated_map_definition, is_generated_map_name
from src.region_naming import assign_region_founding_name
from src.resource_economy import (
    initialize_region_resources,
    update_faction_resource_economy,
)
from src.visibility import initialize_faction_visibility


def create_world(
    map_name="seven_region_ring",
    num_factions=4,
    map_generation_config=None,
) -> WorldState:
    if is_generated_map_name(map_name):
        MAPS[map_name] = build_generated_map_definition(
            map_name,
            num_factions,
            config=map_generation_config,
        )
    validate_map_factions(map_name, num_factions)
    map_definition = MAPS[map_name]
    factions = create_factions(
        num_factions=num_factions,
        naming_seed=map_name,
    )
    owner_name_map = {
        faction.internal_id: faction_name
        for faction_name, faction in factions.items()
    }
    for faction_name, faction in factions.items():
        faction.primary_ethnicity = faction.culture_name

    regions = {}
    for region_name, region_data in map_definition["regions"].items():
        regions[region_name] = Region(
            name=region_name,
            neighbors=region_data["neighbors"],
            owner=owner_name_map.get(region_data["owner"], region_data["owner"]),
            resources=region_data["resources"],
            population=0,
            terrain_tags=region_data.get("terrain_tags", ["plains"]),
            climate=region_data.get("climate", "temperate"),
        )

    world = WorldState(
        regions=regions,
        factions=factions,
        map_name=map_name,
        sea_links=[
            tuple(link)
            for link in map_definition.get("sea_links", [])
            if len(link) == 2
        ],
        river_links=[
            tuple(link)
            for link in map_definition.get("river_links", [])
            if len(link) == 2
        ],
    )
    for faction_name, faction in factions.items():
        register_ethnicity(
            world,
            faction.primary_ethnicity or faction.culture_name,
            language_family=faction.culture_name,
            origin_faction=faction_name,
            language_profile=faction.identity.language_profile if faction.identity is not None else None,
        )
    initialize_heartlands(world)
    initialize_region_resources(world)
    initialize_faction_doctrines(world)
    initialize_dynastic_politics(world)

    homeland_assigned: dict[str, int] = {}
    for region_name, region in world.regions.items():
        if region.owner is None:
            continue
        region.population = estimate_region_population_from_resource_profile(
            region,
            owner=region.owner,
        )

        owned_count = homeland_assigned.get(region.owner, 0)
        assign_region_founding_name(
            world,
            region_name,
            region.owner,
            is_homeland=(owned_count == 0),
        )
        primary_ethnicity = world.factions[region.owner].primary_ethnicity
        if primary_ethnicity is not None:
            seed_region_ethnicity(region, primary_ethnicity)
        homeland_assigned[region.owner] = owned_count + 1

    update_faction_resource_economy(world)
    for region in world.regions.values():
        if region.owner is None:
            continue
        region.population = estimate_region_population(
            region.resources,
            len(region.neighbors),
            owner=region.owner,
        )
        primary_ethnicity = world.factions[region.owner].primary_ethnicity
        if primary_ethnicity is not None:
            seed_region_ethnicity(region, primary_ethnicity)
    initialize_religious_legitimacy(world)
    update_region_settlement_levels(world)
    update_faction_resource_economy(world)
    refresh_administrative_state(world)
    initialize_faction_visibility(world)
    initialize_relationships(world)
    initialize_region_history(world)

    return world
