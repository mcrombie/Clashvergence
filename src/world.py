from src.factions import create_factions, validate_map_factions
from src.models import Region, WorldState
from src.maps import MAPS


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
        )

    return WorldState(regions=regions, factions=factions, map_name=map_name)
