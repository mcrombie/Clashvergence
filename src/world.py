from src.models import Region, Faction, WorldState
from src.maps import MAPS


def create_factions():
    return {
        "Faction1": Faction("Faction1", "expansionist", treasury=1),
        "Faction2": Faction("Faction2", "balanced", treasury=1),
        "Faction3": Faction("Faction3", "economic", treasury=1),
        "Faction4": Faction("Faction4", "opportunist", treasury=1),
    }


def create_world(map_name="seven_region_ring") -> WorldState:
    map_definition = MAPS[map_name]

    regions = {}
    for region_name, region_data in map_definition["regions"].items():
        regions[region_name] = Region(
            name=region_name,
            neighbors=region_data["neighbors"],
            owner=region_data["owner"],
            resources=region_data["resources"],
        )

    factions = create_factions()

    return WorldState(regions=regions, factions=factions)