from src.faction_naming import (
    generate_faction_identities,
    get_configured_faction_internal_ids,
    get_faction_internal_id,
)
from src.maps import MAPS
from src.models import Faction


DEFAULT_STARTING_TREASURY = 1


def get_faction_name(index):
    return get_faction_internal_id(index)


def get_configured_faction_names(num_factions):
    return get_configured_faction_internal_ids(num_factions)


def create_factions(
    num_factions=4,
    starting_treasury=DEFAULT_STARTING_TREASURY,
    naming_seed="default",
):
    identities = generate_faction_identities(num_factions, naming_seed=naming_seed)

    factions = {}
    for index, identity in enumerate(identities, start=1):
        factions[identity.display_name] = Faction(
            name=identity.display_name,
            treasury=starting_treasury,
            identity=identity,
            starting_treasury=starting_treasury,
        )
    return factions


def get_map_starting_region_counts(map_name):
    counts = {}

    for region_data in MAPS[map_name]["regions"].values():
        owner = region_data["owner"]
        if owner is None:
            continue
        counts[owner] = counts.get(owner, 0) + 1

    return counts


def validate_map_factions(map_name, num_factions):
    configured_factions = set(get_configured_faction_internal_ids(num_factions))
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
