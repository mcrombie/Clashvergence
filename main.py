from src.world import create_world
from src.simulation import run_simulation
from src.narrative import build_chronicle
from src.event_analysis import get_event_log
from src.metrics import get_metrics_log


def build_simulation_setup(world, map_name, num_turns, starting_treasuries):
    """Builds the simulation setup section for the results report."""
    lines = []

    lines.append("Simulation Setup")
    lines.append("")
    lines.append(f"Map: {map_name}")
    lines.append(f"Turns: {num_turns}")
    lines.append(f"Regions: {len(world.regions)}")
    lines.append(f"Factions: {len(world.factions)}")
    lines.append("Faction Strategies:")

    for faction_name, faction in world.factions.items():
        lines.append(
            f"  {faction_name}: strategy={faction.strategy}, "
            f"starting_treasury={starting_treasuries[faction_name]}"
        )

    return lines


def format_event(event):
    """Formats one simulation event for the results report."""
    if event["type"] == "expand":
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} expanded into {event['region']} "
            f"(score={event.get('score', 0)}, resources={event.get('resources', 0)}, "
            f"neighbors={event.get('neighbors', 0)}, "
            f"unclaimed_neighbors={event.get('unclaimed_neighbors', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    if event["type"] == "invest":
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} invested in {event['region']} "
            f"(invest_amount={event.get('invest_amount', 0)}, "
            f"new_resources={event.get('new_resources', 0)})"
        )

    return f"Turn {event['turn'] + 1}: {event}"


def build_results_report(world, map_name, num_turns, starting_treasuries):
    """Builds a detailed simulation report."""
    lines = []

    lines.append("Detailed Simulation Results")
    lines.append("")
    lines.extend(build_simulation_setup(world, map_name, num_turns, starting_treasuries))
    lines.append("")
    lines.append(build_chronicle(world))
    lines.append("")
    lines.append("Event Log")
    lines.append("")

    for event in get_event_log(world):
        lines.append(format_event(event))

    lines.append("")
    lines.append("Per-Turn Metrics")
    lines.append("")

    for snapshot in get_metrics_log(world):
        lines.append(f"Turn {snapshot['turn']}")
        for faction_name, faction_metrics in snapshot["factions"].items():
            lines.append(
                f"  {faction_name}: treasury={faction_metrics['treasury']}, "
                f"regions={faction_metrics['regions']}, "
                f"expansions={faction_metrics['expansions']}, "
                f"investments={faction_metrics['investments']}"
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def main():
    map_name = "multi_ring_symmetry"
    num_turns = 20

    world = create_world(map_name=map_name)
    starting_treasuries = {
        faction_name: faction.treasury
        for faction_name, faction in world.factions.items()
    }
    world = run_simulation(world, num_turns=num_turns, verbose=False)
    chronicle = build_chronicle(world)
    results = build_results_report(world, map_name, num_turns, starting_treasuries)
    print(results)

    with open("results.txt", "w") as file:
        file.write(results)

    with open("chronicle.txt", "w") as file:
        file.write(chronicle)


if __name__ == "__main__":
    main()
