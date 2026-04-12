from collections import Counter


def score_region_importance(region_name, world):
    """Returns a simple map-agnostic importance score for a region."""
    region = world.regions[region_name]

    resource_score = region.resources * 2
    neighbor_score = len(region.neighbors)

    unclaimed_neighbor_score = 0
    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None:
            unclaimed_neighbor_score += 2

    return resource_score + neighbor_score + unclaimed_neighbor_score


def get_event_log(world):
    """Returns the raw event log."""
    return world.events


def get_events_by_faction(world):
    """Groups events by faction."""
    events_by_faction = {}

    for faction_name in world.factions:
        events_by_faction[faction_name] = []

    for event in world.events:
        faction_name = event["faction"]
        if faction_name in events_by_faction:
            events_by_faction[faction_name].append(event)

    return events_by_faction


def get_first_expansions(world):
    """Returns the first expansion event for each faction."""
    first_expansions = {}

    for event in world.events:
        if event["type"] == "expand":
            faction_name = event["faction"]
            if faction_name not in first_expansions:
                first_expansions[faction_name] = event

    return first_expansions


def get_high_value_expansions(world, minimum_score=10):
    """Returns expansion events into strategically important regions."""
    important_expansions = []

    for event in world.events:
        if event["type"] == "expand":
            region_name = event["region"]
            importance_score = score_region_importance(region_name, world)

            if importance_score >= minimum_score:
                important_expansions.append({
                    "turn": event["turn"],
                    "faction": event["faction"],
                    "region": region_name,
                    "importance_score": importance_score,
                })

    return important_expansions


def get_faction_event_counts(world):
    """Returns counts of expand and invest actions by faction."""
    faction_event_counts = {}

    for faction_name in world.factions:
        faction_event_counts[faction_name] = {
            "expand": 0,
            "invest": 0,
        }

    for event in world.events:
        faction_name = event["faction"]
        event_type = event["type"]

        if faction_name in faction_event_counts and event_type in faction_event_counts[faction_name]:
            faction_event_counts[faction_name][event_type] += 1

    return faction_event_counts


def get_final_standings(world):
    """Returns sorted faction standings by treasury."""
    standings = []

    for faction_name, faction in world.factions.items():
        owned_regions = 0
        for region in world.regions.values():
            if region.owner == faction_name:
                owned_regions += 1

        standings.append({
            "faction": faction_name,
            "treasury": faction.treasury,
            "owned_regions": owned_regions,
        })

    standings.sort(key=lambda entry: entry["treasury"], reverse=True)
    return standings


def get_key_events(world):
    """Returns a curated set of important events for summary purposes."""
    key_events = []

    first_expansions = get_first_expansions(world)
    for event in first_expansions.values():
        key_events.append({
            "kind": "first_expansion",
            "turn": event["turn"],
            "faction": event["faction"],
            "region": event["region"],
        })

    for event in get_high_value_expansions(world):
        key_events.append({
            "kind": "high_value_expansion",
            "turn": event["turn"],
            "faction": event["faction"],
            "region": event["region"],
            "importance_score": event["importance_score"],
        })

    key_events.sort(key=lambda event: event["turn"])
    return key_events