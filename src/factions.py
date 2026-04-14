from src.maps import MAPS
from src.models import Faction


DEFAULT_STARTING_TREASURY = 1
FACTION_STRATEGY_CYCLE = [
    "expansionist",
    "balanced",
    "economic",
    "opportunist",
]


def get_faction_name(index):
    return f"Faction{index}"


def get_configured_faction_names(num_factions):
    if num_factions < 1:
        raise ValueError("num_factions must be at least 1.")

    return [get_faction_name(index) for index in range(1, num_factions + 1)]


def create_factions(num_factions=4, starting_treasury=DEFAULT_STARTING_TREASURY):
    faction_names = get_configured_faction_names(num_factions)

    return {
        faction_name: Faction(
            faction_name,
            FACTION_STRATEGY_CYCLE[(index - 1) % len(FACTION_STRATEGY_CYCLE)],
            treasury=starting_treasury,
        )
        for index, faction_name in enumerate(faction_names, start=1)
    }


def get_map_starting_region_counts(map_name):
    counts = {}

    for region_data in MAPS[map_name]["regions"].values():
        owner = region_data["owner"]
        if owner is None:
            continue
        counts[owner] = counts.get(owner, 0) + 1

    return counts


def validate_map_factions(map_name, num_factions):
    configured_factions = set(get_configured_faction_names(num_factions))
    starting_region_counts = get_map_starting_region_counts(map_name)
    map_factions = set(starting_region_counts)

    unsupported_map_factions = sorted(map_factions - configured_factions)
    missing_configured_factions = sorted(
        faction_name
        for faction_name in configured_factions
        if starting_region_counts.get(faction_name, 0) == 0
    )

    problems = []
    if unsupported_map_factions:
        problems.append(
            "map assigns starting regions to unconfigured factions: "
            + ", ".join(unsupported_map_factions)
        )
    if missing_configured_factions:
        problems.append(
            "configured factions without starting regions: "
            + ", ".join(missing_configured_factions)
        )

    if problems:
        raise ValueError(
            f"Map '{map_name}' is invalid for num_factions={num_factions}: "
            + "; ".join(problems)
            + "."
        )
