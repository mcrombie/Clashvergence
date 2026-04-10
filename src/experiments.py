from src.world import create_world
from src.simulation import run_simulation


def count_owned_regions(world):
    """Returns a dictionary of faction_name -> number of owned regions."""
    owned_region_counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner is not None:
            owned_region_counts[region.owner] += 1

    return owned_region_counts


def get_center_owner(world):
    """Returns the owner of the center region M."""
    return world.regions["M"].owner


def summarize_world(world):
    """Returns a summary dictionary for the final state of the world."""
    owned_region_counts = count_owned_regions(world)

    summary = {
        "turn": world.turn,
        "center_owner": get_center_owner(world),
        "factions": {}
    }

    for faction_name, faction in world.factions.items():
        summary["factions"][faction_name] = {
            "treasury": faction.treasury,
            "owned_regions": owned_region_counts[faction_name],
        }

    return summary


def run_experiment(num_turns, faction_order, map_name):
    """Runs one simulation and returns a summary."""
    world = create_world(map_name=map_name)
    final_world = run_simulation(
        world,
        num_turns,
        faction_order=faction_order,
        verbose=False,
    )
    return summarize_world(final_world)


def get_winner(summary):
    """Returns the faction with the highest treasury."""
    return max(
        summary["factions"],
        key=lambda faction_name: summary["factions"][faction_name]["treasury"]
    )


def aggregate_summaries(summaries):
    """Aggregates multiple experiment summaries."""
    faction_names = list(summaries[0]["factions"].keys())

    aggregate = {
        "runs": len(summaries),
        "center_owner_counts": {},
        "win_counts": {faction_name: 0 for faction_name in faction_names},
        "average_treasury": {faction_name: 0 for faction_name in faction_names},
        "average_owned_regions": {faction_name: 0 for faction_name in faction_names},
    }

    for summary in summaries:
        center_owner = summary["center_owner"]
        aggregate["center_owner_counts"][center_owner] = (
            aggregate["center_owner_counts"].get(center_owner, 0) + 1
        )

        winner = get_winner(summary)
        aggregate["win_counts"][winner] += 1

        for faction_name in faction_names:
            aggregate["average_treasury"][faction_name] += summary["factions"][faction_name]["treasury"]
            aggregate["average_owned_regions"][faction_name] += summary["factions"][faction_name]["owned_regions"]

    for faction_name in faction_names:
        aggregate["average_treasury"][faction_name] /= len(summaries)
        aggregate["average_owned_regions"][faction_name] /= len(summaries)

    return aggregate


def format_aggregate_summary(aggregate, faction_order, map_name):
    lines = []
    lines.append("\n==============================")
    lines.append(f"Map: {map_name}")
    # lines.append(f"Faction Order: {faction_order}")
    lines.append(f"Runs: {aggregate['runs']}")
    lines.append("Center Owner Counts:")

    for faction_name, count in aggregate["center_owner_counts"].items():
        lines.append(f"  {faction_name}: {count}")

    lines.append("Win Counts:")
    for faction_name, count in aggregate["win_counts"].items():
        lines.append(f"  {faction_name}: {count}")

    lines.append("Average Results:")
    for faction_name in aggregate["average_treasury"]:
        lines.append(
            f"  {faction_name}: "
            f"avg_treasury={aggregate['average_treasury'][faction_name]:.2f}, "
            f"avg_owned_regions={aggregate['average_owned_regions'][faction_name]:.2f}"
        )

    return "\n".join(lines)


def run_order_comparison(
    num_turns=10,
    iterations=10,
    map_name="seven_region_ring",
    output_file=None,
):
    """Runs repeated simulations for several faction orders on a chosen map."""

    faction_orders = [
    ["Faction1", "Faction2", "Faction3"]
    ]

    all_output = []

    for faction_order in faction_orders:
        summaries = []

        for _ in range(iterations):
            summary = run_experiment(
                num_turns=num_turns,
                faction_order=faction_order,
                map_name=map_name,
            )
            summaries.append(summary)

        aggregate = aggregate_summaries(summaries)
        formatted = format_aggregate_summary(
            aggregate=aggregate,
            faction_order=faction_order,
            map_name=map_name,
        )

        print(formatted)
        all_output.append(formatted)

    if output_file:
        with open(output_file, "w") as file:
            file.write("\n\n".join(all_output))