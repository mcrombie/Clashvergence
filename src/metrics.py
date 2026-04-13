def get_turn_events(world, turn):
    """Returns all events recorded for a specific turn."""
    return [event for event in world.events if event.turn == turn]


def get_owned_region_counts(world):
    """Returns the number of regions currently owned by each faction."""
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def build_turn_metrics(world):
    """Builds a per-faction metrics snapshot for the just-completed turn."""
    turn_events = get_turn_events(world, world.turn)
    owned_region_counts = get_owned_region_counts(world)
    faction_metrics = {}

    for faction_name, faction in world.factions.items():
        expansions = 0
        investments = 0

        for event in turn_events:
            if event.faction != faction_name:
                continue

            if event.type == "expand":
                expansions += 1
            elif event.type == "invest":
                investments += 1

        faction_metrics[faction_name] = {
            "treasury": faction.treasury,
            "regions": owned_region_counts[faction_name],
            "expansions": expansions,
            "investments": investments,
        }

    return {
        "turn": world.turn + 1,
        "factions": faction_metrics,
    }


def record_turn_metrics(world):
    """Appends the latest per-turn metrics snapshot to the world state."""
    world.metrics.append(build_turn_metrics(world))


def get_metrics_log(world):
    """Returns the raw metrics log."""
    return world.metrics


def get_turn_metrics(world, turn_number):
    """Returns the metrics snapshot for a one-based turn number."""
    for snapshot in world.metrics:
        if snapshot["turn"] == turn_number:
            return snapshot

    return None


def get_faction_metrics_history(world, faction_name):
    """Returns one faction's metrics across all recorded turns."""
    history = []

    for snapshot in world.metrics:
        if faction_name in snapshot["factions"]:
            history.append({
                "turn": snapshot["turn"],
                **snapshot["factions"][faction_name],
            })

    return history
