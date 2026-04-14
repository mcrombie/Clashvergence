from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from statistics import mean

from src.maps import MAPS
from src.metrics import get_metrics_log
from src.simulation import run_simulation
from src.world import create_world


DEFAULT_MAPS = sorted(MAPS)
DEFAULT_TURNS = [5, 10, 20, 40, 80, 160]
DEFAULT_RUNS = 200
DEFAULT_SEED = 12345
DEFAULT_OUTPUT = Path("reports/maintenance_strategy_comparison.txt")
DEFAULT_INVALID_MAP_POLICY = "skip"


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
    parser.add_argument(
        "--invalid-map-policy",
        choices=["skip", "fail"],
        default=DEFAULT_INVALID_MAP_POLICY,
        help="How to handle maps where one or more configured factions lack a starting region.",
    )
    return parser.parse_args()


def count_owned_regions(world):
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def summarize_economy(world):
    total_income = {faction_name: 0 for faction_name in world.factions}
    total_maintenance = {faction_name: 0 for faction_name in world.factions}

    for snapshot in get_metrics_log(world):
        for faction_name, faction_metrics in snapshot["factions"].items():
            total_income[faction_name] += faction_metrics.get("income", 0)
            total_maintenance[faction_name] += faction_metrics.get("maintenance", 0)

    return {
        faction_name: {
            "income": total_income[faction_name],
            "maintenance": total_maintenance[faction_name],
            "net_income": total_income[faction_name] - total_maintenance[faction_name],
        }
        for faction_name in world.factions
    }


def get_starting_region_counts(world):
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def validate_map_faction_starts(map_name):
    template_world = create_world(map_name=map_name)
    starting_region_counts = get_starting_region_counts(template_world)
    missing_factions = [
        faction_name
        for faction_name, count in starting_region_counts.items()
        if count == 0
    ]

    if not missing_factions:
        return {
            "valid": True,
            "reason": None,
            "starting_region_counts": starting_region_counts,
        }

    missing_text = ", ".join(missing_factions)
    reason = (
        f"Map '{map_name}' is invalid for this comparison because these configured factions "
        f"have no starting region: {missing_text}."
    )
    return {
        "valid": False,
        "reason": reason,
        "starting_region_counts": starting_region_counts,
    }


def run_comparison_setting(map_name, num_turns, runs):
    template_world = create_world(map_name=map_name)
    faction_names = list(template_world.factions.keys())
    faction_strategies = {
        faction_name: faction.strategy
        for faction_name, faction in template_world.factions.items()
    }

    outright_wins = {faction_name: 0 for faction_name in faction_names}
    shared_firsts = {faction_name: 0 for faction_name in faction_names}
    average_treasury = {faction_name: [] for faction_name in faction_names}
    average_regions = {faction_name: [] for faction_name in faction_names}
    average_income = {faction_name: [] for faction_name in faction_names}
    average_maintenance = {faction_name: [] for faction_name in faction_names}
    average_net_income = {faction_name: [] for faction_name in faction_names}

    for _ in range(runs):
        world = create_world(map_name=map_name)
        world = run_simulation(world, num_turns=num_turns, verbose=False)

        final_treasuries = {
            faction_name: faction.treasury
            for faction_name, faction in world.factions.items()
        }
        final_regions = count_owned_regions(world)
        final_economy = summarize_economy(world)
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
            average_income[faction_name].append(final_economy[faction_name]["income"])
            average_maintenance[faction_name].append(final_economy[faction_name]["maintenance"])
            average_net_income[faction_name].append(final_economy[faction_name]["net_income"])

    return {
        "map_name": map_name,
        "num_turns": num_turns,
        "runs": runs,
        "factions": faction_names,
        "strategies": faction_strategies,
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
        "average_income": {
            faction_name: mean(average_income[faction_name])
            for faction_name in faction_names
        },
        "average_maintenance": {
            faction_name: mean(average_maintenance[faction_name])
            for faction_name in faction_names
        },
        "average_net_income": {
            faction_name: mean(average_net_income[faction_name])
            for faction_name in faction_names
        },
    }


def format_result_table(result):
    lines = []
    lines.append(f"Map: {result['map_name']}")
    lines.append(f"Turns: {result['num_turns']}")
    lines.append(f"Simulations: {result['runs']}")
    lines.append("")
    lines.append("Strategies:")
    for faction_name in result["factions"]:
        lines.append(f"  {faction_name}: {result['strategies'][faction_name]}")
    lines.append("")
    lines.append(
        f"{'Faction':<10} {'Strategy':<13} {'Win':>8} {'Shared':>8} "
        f"{'Treasury':>10} {'Regions':>8} {'Income':>10} {'Maint':>10} {'Net':>10}"
    )
    lines.append("-" * 98)

    for faction_name in result["factions"]:
        lines.append(
            f"{faction_name:<10} "
            f"{result['strategies'][faction_name]:<13} "
            f"{result['outright_win_rate'][faction_name]:>7.2%} "
            f"{result['shared_first_rate'][faction_name]:>7.2%} "
            f"{result['average_treasury'][faction_name]:>10.3f} "
            f"{result['average_regions'][faction_name]:>8.3f} "
            f"{result['average_income'][faction_name]:>10.3f} "
            f"{result['average_maintenance'][faction_name]:>10.3f} "
            f"{result['average_net_income'][faction_name]:>10.3f}"
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


def build_report_with_skips(results, skipped_maps, seed):
    lines = [build_report(results, seed)]

    if skipped_maps:
        lines.append("")
        lines.append("=" * 66)
        lines.append("")
        lines.append("Skipped Maps")
        lines.append("")
        for skipped in skipped_maps:
            lines.append(f"Map: {skipped['map_name']}")
            lines.append(f"Reason: {skipped['reason']}")
            lines.append("")

    return "\n".join(lines).rstrip()


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
    skipped_maps = []
    for map_name in args.maps:
        validation = validate_map_faction_starts(map_name)
        if not validation["valid"]:
            if args.invalid_map_policy == "fail":
                raise ValueError(validation["reason"])

            print(f"WARNING: Skipping. {validation['reason']}", file=sys.stderr)
            skipped_maps.append(
                {
                    "map_name": map_name,
                    "reason": validation["reason"],
                }
            )
            continue

        for num_turns in args.turns:
            results.append(
                run_comparison_setting(
                    map_name=map_name,
                    num_turns=num_turns,
                    runs=args.runs,
                )
            )

    report_text = build_report_with_skips(results, skipped_maps, seed=args.seed)
    print(report_text)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
