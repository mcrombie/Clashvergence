from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.experiment_compare import validate_map_faction_starts, validate_maps
from src.maps import MAPS
from src.narrative import build_chronicle
from src.simulation import run_simulation
from src.world import create_world


DEFAULT_MAPS = sorted(MAPS)
DEFAULT_TURNS = [5, 10, 20, 40, 80, 160]
DEFAULT_SEED = 12345
DEFAULT_OUTPUT = ROOT / "reports/narrative_comparison.txt"
DEFAULT_INVALID_MAP_POLICY = "skip"
DEFAULT_NUM_FACTIONS = 4


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate narrative comparisons across maps and turn horizons."
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
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Base random seed for reproducible narrative sweeps.",
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
    parser.add_argument(
        "--num-factions",
        type=int,
        default=DEFAULT_NUM_FACTIONS,
        help="Number of factions to include in each simulation.",
    )
    return parser.parse_args()


def build_strategy_lines(world):
    lines = ["Strategies:"]
    for faction_name, faction in world.factions.items():
        lines.append(f"  {faction_name}: {faction.strategy}")
    return lines


def run_narrative_setting(map_name, num_turns, scenario_seed, num_factions):
    random.seed(scenario_seed)
    world = create_world(map_name=map_name, num_factions=num_factions)
    world = run_simulation(world, num_turns=num_turns, verbose=False)

    return {
        "map_name": map_name,
        "num_turns": num_turns,
        "seed": scenario_seed,
        "factions": list(world.factions),
        "strategies": {
            faction_name: faction.strategy
            for faction_name, faction in world.factions.items()
        },
        "chronicle": build_chronicle(world),
    }


def format_narrative_result(result):
    lines = []
    lines.append(f"Map: {result['map_name']}")
    lines.append(f"Turns: {result['num_turns']}")
    lines.append(f"Seed: {result['seed']}")
    lines.append(f"Configured factions: {len(result['factions'])}")
    lines.append("")
    lines.append("Strategies:")
    for faction_name in result["factions"]:
        lines.append(f"  {faction_name}: {result['strategies'][faction_name]}")
    lines.append("")
    lines.append(result["chronicle"])
    return "\n".join(lines)


def build_report(results, skipped_maps, base_seed):
    lines = []
    lines.append("Narrative Comparison Report")
    lines.append("")
    lines.append(f"Base seed: {base_seed}")
    lines.append("")

    for index, result in enumerate(results):
        if index > 0:
            lines.append("")
            lines.append("=" * 72)
            lines.append("")
        lines.append(format_narrative_result(result))

    if skipped_maps:
        lines.append("")
        lines.append("=" * 72)
        lines.append("")
        lines.append("Skipped Maps")
        lines.append("")
        for skipped in skipped_maps:
            lines.append(f"Map: {skipped['map_name']}")
            lines.append(f"Reason: {skipped['reason']}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    args = parse_args()
    validate_maps(args.maps)

    results = []
    skipped_maps = []
    scenario_index = 0

    for map_name in args.maps:
        validation = validate_map_faction_starts(map_name, num_factions=args.num_factions)
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
            scenario_seed = args.seed + scenario_index
            results.append(
                run_narrative_setting(
                    map_name=map_name,
                    num_turns=num_turns,
                    scenario_seed=scenario_seed,
                    num_factions=args.num_factions,
                )
            )
            scenario_index += 1

    report_text = build_report(results, skipped_maps, base_seed=args.seed)
    print(report_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
