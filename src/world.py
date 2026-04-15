from src.factions import create_factions, validate_map_factions
from src.models import Region, WorldState
from src.maps import MAPS
from src.region_naming import assign_region_founding_name


def create_world(map_name="seven_region_ring", num_factions=4) -> WorldState:
    validate_map_factions(map_name, num_factions)
    map_definition = MAPS[map_name]
    factions = create_factions(num_factions=num_factions, naming_seed=map_name)
    owner_name_map = {
        faction.internal_id: faction_name
        for faction_name, faction in factions.items()
    }

    regions = {}
    for region_name, region_data in map_definition["regions"].items():
        regions[region_name] = Region(
            name=region_name,
            neighbors=region_data["neighbors"],
            owner=owner_name_map.get(region_data["owner"], region_data["owner"]),
            resources=region_data["resources"],
            terrain_tags=region_data.get("terrain_tags", ["plains"]),
        )

    world = WorldState(regions=regions, factions=factions, map_name=map_name)

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
        homeland_assigned[region.owner] = owned_count + 1

    return world
