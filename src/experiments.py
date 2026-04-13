from src.world import create_world
from src.simulation import run_simulation


def count_owned_regions(world):
    """Returns a dictionary of faction_name -> number of owned regions."""
    owned_region_counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner is not None:
            owned_region_counts[region.owner] += 1

    return owned_region_counts


def summarize_world(world):
    """Returns a summary dictionary for the final state of the world."""
    owned_region_counts = count_owned_regions(world)

    summary = {
        "turn": world.turn,
        "factions": {}
    }

    for faction_name, faction in world.factions.items():
        summary["factions"][faction_name] = {
            "treasury": faction.treasury,
            "owned_regions": owned_region_counts[faction_name],
        }

    return summary


def run_experiment(num_turns, map_name):
    """Runs one simulation and returns a summary."""
    world = create_world(map_name=map_name)
    final_world = run_simulation(
        world,
        num_turns,
        faction_order=None,
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
        "win_counts": {faction_name: 0 for faction_name in faction_names},
        "average_treasury": {faction_name: 0 for faction_name in faction_names},
        "average_owned_regions": {faction_name: 0 for faction_name in faction_names},
    }

    for summary in summaries:
        winner = get_winner(summary)
        aggregate["win_counts"][winner] += 1

        for faction_name in faction_names:
            aggregate["average_treasury"][faction_name] += summary["factions"][faction_name]["treasury"]
            aggregate["average_owned_regions"][faction_name] += summary["factions"][faction_name]["owned_regions"]

    for faction_name in faction_names:
        aggregate["average_treasury"][faction_name] /= len(summaries)
        aggregate["average_owned_regions"][faction_name] /= len(summaries)

    return aggregate


def format_aggregate_summary(aggregate, map_name, label):
    lines = []
    lines.append("\n==============================")
    lines.append(f"Map: {map_name}")
    lines.append(f"{label}")
    lines.append(f"Runs: {aggregate['runs']}")
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


def run_batch(num_turns=20, iterations=100, map_name="thirteen_region_ring"):
    """Runs one batch of simulations and returns the aggregate."""
    summaries = []

    for _ in range(iterations):
        summary = run_experiment(num_turns=num_turns, map_name=map_name)
        summaries.append(summary)

    return aggregate_summaries(summaries)


def run_multiple_batches(
    num_turns=20,
    iterations_per_batch=100,
    num_batches=5,
    map_name="thirteen_region_ring",
    output_file=None,
):
    """Runs multiple batches and aggregates the batch-level results."""
    all_output = []
    batch_aggregates = []

    for batch_number in range(1, num_batches + 1):
        batch_aggregate = run_batch(
            num_turns=num_turns,
            iterations=iterations_per_batch,
            map_name=map_name,
        )
        batch_aggregates.append(batch_aggregate)

        formatted = format_aggregate_summary(
            batch_aggregate,
            map_name=map_name,
            label=f"Batch {batch_number}"
        )
        print(formatted)
        all_output.append(formatted)

    faction_names = list(batch_aggregates[0]["win_counts"].keys())

    overall = {
        "batches": num_batches,
        "runs_per_batch": iterations_per_batch,
        "total_runs": num_batches * iterations_per_batch,
        "average_win_counts": {faction_name: 0 for faction_name in faction_names},
        "average_treasury": {faction_name: 0 for faction_name in faction_names},
        "average_owned_regions": {faction_name: 0 for faction_name in faction_names},
    }

    for batch_aggregate in batch_aggregates:
        for faction_name in faction_names:
            overall["average_win_counts"][faction_name] += batch_aggregate["win_counts"][faction_name]
            overall["average_treasury"][faction_name] += batch_aggregate["average_treasury"][faction_name]
            overall["average_owned_regions"][faction_name] += batch_aggregate["average_owned_regions"][faction_name]

    for faction_name in faction_names:
        overall["average_win_counts"][faction_name] /= num_batches
        overall["average_treasury"][faction_name] /= num_batches
        overall["average_owned_regions"][faction_name] /= num_batches

    overall_lines = []
    overall_lines.append("\n==============================")
    overall_lines.append(f"Map: {map_name}")
    overall_lines.append("Overall Average Across Batches")
    overall_lines.append(f"Batches: {overall['batches']}")
    overall_lines.append(f"Runs per batch: {overall['runs_per_batch']}")
    overall_lines.append(f"Total runs: {overall['total_runs']}")
    overall_lines.append("Average Win Counts Per 100-Run Batch:")

    for faction_name, count in overall["average_win_counts"].items():
        overall_lines.append(f"  {faction_name}: {count:.2f}")

    overall_lines.append("Average Treasury Across Batches:")
    for faction_name, value in overall["average_treasury"].items():
        overall_lines.append(f"  {faction_name}: {value:.2f}")

    overall_lines.append("Average Owned Regions Across Batches:")
    for faction_name, value in overall["average_owned_regions"].items():
        overall_lines.append(f"  {faction_name}: {value:.2f}")

    overall_text = "\n".join(overall_lines)
    print(overall_text)
    all_output.append(overall_text)

    if output_file:
        with open(output_file, "w") as file:
            file.write("\n\n".join(all_output))


def run_turn_horizon_comparison(
    turn_counts,
    iterations_per_batch=100,
    num_batches=5,
    map_name="thirteen_region_ring",
    output_file=None,
):
    """Runs multiple batch experiments across different turn horizons."""
    all_output = []

    for num_turns in turn_counts:
        header_lines = []
        header_lines.append("\n########################################")
        header_lines.append(f"TURN HORIZON: {num_turns}")
        header_lines.append("########################################")
        header_text = "\n".join(header_lines)

        print(header_text)
        all_output.append(header_text)

        batch_aggregates = []

        for batch_number in range(1, num_batches + 1):
            batch_aggregate = run_batch(
                num_turns=num_turns,
                iterations=iterations_per_batch,
                map_name=map_name,
            )
            batch_aggregates.append(batch_aggregate)

            formatted = format_aggregate_summary(
                batch_aggregate,
                map_name=map_name,
                label=f"Batch {batch_number} | Turns: {num_turns}"
            )
            print(formatted)
            all_output.append(formatted)

        faction_names = list(batch_aggregates[0]["win_counts"].keys())

        overall = {
            "batches": num_batches,
            "runs_per_batch": iterations_per_batch,
            "total_runs": num_batches * iterations_per_batch,
            "average_win_counts": {faction_name: 0 for faction_name in faction_names},
            "average_treasury": {faction_name: 0 for faction_name in faction_names},
            "average_owned_regions": {faction_name: 0 for faction_name in faction_names},
        }

        for batch_aggregate in batch_aggregates:
            for faction_name in faction_names:
                overall["average_win_counts"][faction_name] += batch_aggregate["win_counts"][faction_name]
                overall["average_treasury"][faction_name] += batch_aggregate["average_treasury"][faction_name]
                overall["average_owned_regions"][faction_name] += batch_aggregate["average_owned_regions"][faction_name]

        for faction_name in faction_names:
            overall["average_win_counts"][faction_name] /= num_batches
            overall["average_treasury"][faction_name] /= num_batches
            overall["average_owned_regions"][faction_name] /= num_batches

        overall_lines = []
        overall_lines.append("\n==============================")
        overall_lines.append(f"Map: {map_name}")
        overall_lines.append(f"Overall Average Across Batches | Turns: {num_turns}")
        overall_lines.append(f"Batches: {overall['batches']}")
        overall_lines.append(f"Runs per batch: {overall['runs_per_batch']}")
        overall_lines.append(f"Total runs: {overall['total_runs']}")
        overall_lines.append("Average Win Counts Per 100-Run Batch:")

        for faction_name, count in overall["average_win_counts"].items():
            overall_lines.append(f"  {faction_name}: {count:.2f}")

        overall_lines.append("Average Treasury Across Batches:")
        for faction_name, value in overall["average_treasury"].items():
            overall_lines.append(f"  {faction_name}: {value:.2f}")

        overall_lines.append("Average Owned Regions Across Batches:")
        for faction_name, value in overall["average_owned_regions"].items():
            overall_lines.append(f"  {faction_name}: {value:.2f}")

        overall_text = "\n".join(overall_lines)
        print(overall_text)
        all_output.append(overall_text)

    if output_file:
        with open(output_file, "w") as file:
            file.write("\n\n".join(all_output))
