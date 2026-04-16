from src.heartland import get_region_core_status


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


def build_turn_metrics(world, economy_snapshot=None):
    """Builds a per-faction metrics snapshot for the just-completed turn."""
    turn_events = get_turn_events(world, world.turn)
    owned_region_counts = get_owned_region_counts(world)
    faction_metrics = {}

    for faction_name, faction in world.factions.items():
        attacks = 0
        expansions = 0
        investments = 0
        homeland_regions = 0
        core_regions = 0
        frontier_regions = 0
        economy_data = (economy_snapshot or {}).get(faction_name, {})
        income = economy_data.get("base_income", 0)
        empire_penalty = economy_data.get("empire_penalty", 0)
        effective_income = economy_data.get("effective_income", 0)
        maintenance = economy_data.get("maintenance", 0)

        for event in turn_events:
            if event.faction != faction_name:
                continue

            if event.type == "attack":
                attacks += 1
            elif event.type == "expand":
                expansions += 1
            elif event.type == "invest":
                investments += 1

        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            status = get_region_core_status(region)
            if status == "homeland":
                homeland_regions += 1
            elif status == "core":
                core_regions += 1
            else:
                frontier_regions += 1

        faction_metrics[faction_name] = {
            "treasury": faction.treasury,
            "regions": owned_region_counts[faction_name],
            "attacks": attacks,
            "expansions": expansions,
            "investments": investments,
            "income": income,
            "empire_penalty": empire_penalty,
            "effective_income": effective_income,
            "maintenance": maintenance,
            "net_income": effective_income - maintenance,
            "doctrine_label": faction.doctrine_label,
            "terrain_identity": faction.doctrine_profile.terrain_identity,
            "homeland_identity": faction.doctrine_profile.homeland_identity,
            "expansion_posture": faction.doctrine_profile.expansion_posture,
            "war_posture": faction.doctrine_profile.war_posture,
            "development_posture": faction.doctrine_profile.development_posture,
            "insularity": faction.doctrine_profile.insularity,
            "homeland_regions": homeland_regions,
            "core_regions": core_regions,
            "frontier_regions": frontier_regions,
        }

    return {
        "turn": world.turn + 1,
        "factions": faction_metrics,
    }


def record_turn_metrics(world, economy_snapshot=None):
    """Appends the latest per-turn metrics snapshot to the world state."""
    world.metrics.append(build_turn_metrics(world, economy_snapshot=economy_snapshot))


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
