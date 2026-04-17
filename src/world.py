from src.diplomacy import initialize_relationships
from src.doctrine import initialize_faction_doctrines
from src.factions import create_factions, validate_map_factions
from src.heartland import (
    estimate_region_population,
    initialize_heartlands,
    initialize_region_history,
    register_ethnicity,
    seed_region_ethnicity,
)
from src.models import Region, WorldState
from src.maps import MAPS
from src.region_naming import assign_region_founding_name


def create_world(
    map_name="seven_region_ring",
    num_factions=4,
) -> WorldState:
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
            population=estimate_region_population(
                region_data["resources"],
                len(region_data["neighbors"]),
                owner=owner_name_map.get(region_data["owner"], region_data["owner"]),
            ),
            terrain_tags=region_data.get("terrain_tags", ["plains"]),
            climate=region_data.get("climate", "temperate"),
        )

    world = WorldState(regions=regions, factions=factions, map_name=map_name)
    for faction_name, faction in factions.items():
        register_ethnicity(
            world,
            faction.primary_ethnicity or faction.culture_name,
            language_family=faction.culture_name,
            origin_faction=faction_name,
        )
    initialize_heartlands(world)

    homeland_assigned: dict[str, int] = {}
    for region_name, region in world.regions.items():
        if region.owner is None:
            continue

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

    initialize_faction_doctrines(world)
    initialize_relationships(world)
    initialize_region_history(world)

    return world
