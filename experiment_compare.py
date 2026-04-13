from __future__ import annotations

import argparse
import random
from pathlib import Path
from statistics import mean

from src.maps import MAPS
from src.simulation import run_simulation
from src.world import create_world


DEFAULT_MAPS = ["thirteen_region_ring", "multi_ring_symmetry"]
DEFAULT_TURNS = [10, 20, 40]
DEFAULT_RUNS = 1000
DEFAULT_SEED = 12345
DEFAULT_OUTPUT = Path("reports/map_strategy_comparison.txt")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compare faction performance across maps and turn horizons."
    )
    parser.add_argument(
        "--maps",
        nargs="+",
        default=DEFAULT_MAPS,
        help="One or more map names to compare.",
    )
    parser.add_argument(
        "--turns",
        nargs="+",
        type=int,
        default=DEFAULT_TURNS,
        help="One or more turn counts to simulate.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help="Number of simulations to run for each map/turn setting.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed for reproducible results.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Report file path.",
    )
    return parser.parse_args()


def count_owned_regions(world):
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def run_comparison_setting(map_name, num_turns, runs):
    faction_names = list(create_world(map_name=map_name).factions.keys())

    outright_wins = {faction_name: 0 for faction_name in faction_names}
    shared_firsts = {faction_name: 0 for faction_name in faction_names}
    average_treasury = {faction_name: [] for faction_name in faction_names}
    average_regions = {faction_name: [] for faction_name in faction_names}

    for _ in range(runs):
        world = create_world(map_name=map_name)
        world = run_simulation(world, num_turns=num_turns, verbose=False)

        final_treasuries = {
            faction_name: faction.treasury
            for faction_name, faction in world.factions.items()
        }
        final_regions = count_owned_regions(world)
        best_treasury = max(final_treasuries.values())
        leaders = [
            faction_name
            for faction_name, treasury in final_treasuries.items()
            if treasury == best_treasury
        ]

        if len(leaders) == 1:
            outright_wins[leaders[0]] += 1
        else:
            for faction_name in leaders:
                shared_firsts[faction_name] += 1

        for faction_name in faction_names:
            average_treasury[faction_name].append(final_treasuries[faction_name])
            average_regions[faction_name].append(final_regions[faction_name])

    return {
        "map_name": map_name,
        "num_turns": num_turns,
        "runs": runs,
        "factions": faction_names,
        "outright_win_rate": {
            faction_name: outright_wins[faction_name] / runs
            for faction_name in faction_names
        },
        "shared_first_rate": {
            faction_name: shared_firsts[faction_name] / runs
            for faction_name in faction_names
        },
        "average_treasury": {
            faction_name: mean(average_treasury[faction_name])
            for faction_name in faction_names
        },
        "average_regions": {
            faction_name: mean(average_regions[faction_name])
            for faction_name in faction_names
        },
    }


def format_result_table(result):
    lines = []
    lines.append(f"Map: {result['map_name']}")
    lines.append(f"Turns: {result['num_turns']}")
    lines.append(f"Simulations: {result['runs']}")
    lines.append("")
    lines.append(
        f"{'Faction':<10} {'Outright Win':>12} {'Shared First':>13} "
        f"{'Avg Treasury':>13} {'Avg Regions':>12}"
    )
    lines.append("-" * 66)

    for faction_name in result["factions"]:
        lines.append(
            f"{faction_name:<10} "
            f"{result['outright_win_rate'][faction_name]:>11.2%} "
            f"{result['shared_first_rate'][faction_name]:>12.2%} "
            f"{result['average_treasury'][faction_name]:>13.3f} "
            f"{result['average_regions'][faction_name]:>12.3f}"
        )

    return "\n".join(lines)


def build_report(results, seed):
    lines = []
    lines.append("Map Strategy Comparison")
    lines.append("")
    lines.append(f"Seed: {seed}")
    lines.append("")

    for index, result in enumerate(results):
        if index > 0:
            lines.append("")
            lines.append("=" * 66)
            lines.append("")
        lines.append(format_result_table(result))

    return "\n".join(lines)


def validate_maps(map_names):
    invalid_maps = [map_name for map_name in map_names if map_name not in MAPS]
    if invalid_maps:
        available_maps = ", ".join(sorted(MAPS))
        invalid_text = ", ".join(invalid_maps)
        raise ValueError(
            f"Unknown map(s): {invalid_text}. Available maps: {available_maps}"
        )


def main():
    args = parse_args()
    validate_maps(args.maps)
    random.seed(args.seed)

    results = []
    for map_name in args.maps:
        for num_turns in args.turns:
            results.append(
                run_comparison_setting(
                    map_name=map_name,
                    num_turns=num_turns,
                    runs=args.runs,
                )
            )

    report_text = build_report(results, seed=args.seed)
    print(report_text)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
