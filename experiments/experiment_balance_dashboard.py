from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.experiment_compare import validate_map_faction_starts, validate_maps
from src.event_analysis import get_phase_ranges
from src.maps import MAPS
from src.metrics import analyze_competition_metrics
from src.simulation import run_simulation
from src.world import create_world


DEFAULT_MAPS = ["thirty_seven_region_ring"]
DEFAULT_TURNS = [10, 20, 40, 80]
DEFAULT_RUNS = 100
DEFAULT_SEED = 12345
DEFAULT_OUTPUT = ROOT / "reports/balance_dashboard.txt"
DEFAULT_INVALID_MAP_POLICY = "skip"
DEFAULT_NUM_FACTIONS = 4


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a balance dashboard report across maps and turn horizons."
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
    parser.add_argument(
        "--num-factions",
        type=int,
        default=DEFAULT_NUM_FACTIONS,
        help="Number of factions to include in each simulation.",
    )
    parser.add_argument(
        "--disable-legacy-strategy-bias",
        action="store_true",
        help="Disable the legacy strategy utility biases so decisions rely on doctrine only.",
    )
    return parser.parse_args()


def count_owned_regions(world):
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def build_phase_action_counts(world):
    phase_ranges = get_phase_ranges(len(world.metrics))
    phase_counts = {
        phase_name: {
            "attacks": 0,
            "successful_attacks": 0,
            "expansions": 0,
            "investments": 0,
        }
        for phase_name, _start_turn, _end_turn in phase_ranges
    }

    for event in world.events:
        one_based_turn = event.turn + 1
        for phase_name, start_turn, end_turn in phase_ranges:
            if start_turn <= one_based_turn <= end_turn:
                if event.type == "attack":
                    phase_counts[phase_name]["attacks"] += 1
                    if event.get("success", False):
                        phase_counts[phase_name]["successful_attacks"] += 1
                elif event.type == "expand":
                    phase_counts[phase_name]["expansions"] += 1
                elif event.type == "invest":
                    phase_counts[phase_name]["investments"] += 1
                break

    return phase_counts


def summarize_setting(map_name, num_turns, runs, num_factions, use_legacy_strategy_bias):
    template_world = create_world(
        map_name=map_name,
        num_factions=num_factions,
        use_legacy_strategy_bias=use_legacy_strategy_bias,
    )
    faction_names = list(template_world.factions.keys())
    strategies = {
        faction_name: faction.strategy
        for faction_name, faction in template_world.factions.items()
    }
    phase_names = [phase_name for phase_name, _start_turn, _end_turn in get_phase_ranges(num_turns)]

    outright_wins = {faction_name: 0 for faction_name in faction_names}
    shared_firsts = {faction_name: 0 for faction_name in faction_names}
    average_treasury = {faction_name: [] for faction_name in faction_names}
    average_regions = {faction_name: [] for faction_name in faction_names}
    elimination_rate = {faction_name: 0 for faction_name in faction_names}
    elimination_turns = {faction_name: [] for faction_name in faction_names}
    phase_actions = {
        phase_name: {
            "attacks": [],
            "successful_attacks": [],
            "expansions": [],
            "investments": [],
        }
        for phase_name in phase_names
    }
    lead_changes = []
    runaway_rates = []
    runaway_turns = []
    comeback_rates = []
    comeback_deficits = []
    eliminated_faction_counts = []
    largest_treasury_leads = []
    largest_region_leads = []

    for _ in range(runs):
        world = create_world(
            map_name=map_name,
            num_factions=num_factions,
            use_legacy_strategy_bias=use_legacy_strategy_bias,
        )
        world = run_simulation(world, num_turns=num_turns, verbose=False)
        final_regions = count_owned_regions(world)
        competition = analyze_competition_metrics(world)
        phase_counts = build_phase_action_counts(world)

        final_treasuries = {
            faction_name: faction.treasury
            for faction_name, faction in world.factions.items()
        }
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

            elimination = competition["eliminations"][faction_name]
            if elimination["eliminated"]:
                elimination_rate[faction_name] += 1
                elimination_turns[faction_name].append(elimination["turn"])

        for phase_name in phase_names:
            for action_name in phase_actions[phase_name]:
                phase_actions[phase_name][action_name].append(phase_counts[phase_name][action_name])

        lead_changes.append(competition["lead_changes"])
        runaway_rates.append(1.0 if competition["runaway"]["detected"] else 0.0)
        if competition["runaway"]["start_turn"] is not None:
            runaway_turns.append(competition["runaway"]["start_turn"])
        comeback_rates.append(1.0 if competition["comeback"]["detected"] else 0.0)
        if competition["comeback"]["detected"]:
            comeback_deficits.append(competition["comeback"]["max_deficit_overcome"])
        eliminated_faction_counts.append(competition["eliminated_factions"])
        largest_treasury_leads.append(competition["largest_treasury_lead"]["margin"])
        largest_region_leads.append(competition["largest_region_lead"]["margin"])

    outright_win_rates = {
        faction_name: outright_wins[faction_name] / runs
        for faction_name in faction_names
    }
    shared_first_rates = {
        faction_name: shared_firsts[faction_name] / runs
        for faction_name in faction_names
    }

    return {
        "map_name": map_name,
        "num_turns": num_turns,
        "runs": runs,
        "use_legacy_strategy_bias": use_legacy_strategy_bias,
        "factions": faction_names,
        "strategies": strategies,
        "outcome_balance": {
            "outright_win_rate": outright_win_rates,
            "shared_first_rate": shared_first_rates,
            "average_treasury": {
                faction_name: mean(average_treasury[faction_name])
                for faction_name in faction_names
            },
            "average_regions": {
                faction_name: mean(average_regions[faction_name])
                for faction_name in faction_names
            },
            "win_rate_spread": max(outright_win_rates.values()) - min(outright_win_rates.values()),
            "win_rate_stddev": pstdev(outright_win_rates.values()) if len(outright_win_rates) > 1 else 0.0,
        },
        "game_health": {
            "average_lead_changes": mean(lead_changes) if lead_changes else 0.0,
            "runaway_rate": mean(runaway_rates) if runaway_rates else 0.0,
            "average_runaway_turn": mean(runaway_turns) if runaway_turns else None,
            "comeback_rate": mean(comeback_rates) if comeback_rates else 0.0,
            "average_comeback_deficit": mean(comeback_deficits) if comeback_deficits else 0.0,
            "average_eliminated_factions": mean(eliminated_faction_counts) if eliminated_faction_counts else 0.0,
            "average_largest_treasury_lead": mean(largest_treasury_leads) if largest_treasury_leads else 0.0,
            "average_largest_region_lead": mean(largest_region_leads) if largest_region_leads else 0.0,
        },
        "survival": {
            "elimination_rate": {
                faction_name: elimination_rate[faction_name] / runs
                for faction_name in faction_names
            },
            "average_elimination_turn": {
                faction_name: (
                    mean(elimination_turns[faction_name])
                    if elimination_turns[faction_name]
                    else None
                )
                for faction_name in faction_names
            },
        },
        "pacing": {
            phase_name: {
                action_name: mean(values) if values else 0.0
                for action_name, values in actions.items()
            }
            for phase_name, actions in phase_actions.items()
        },
    }


def format_setting_report(result):
    lines = []
    outcome = result["outcome_balance"]
    health = result["game_health"]
    survival = result["survival"]
    pacing = result["pacing"]

    lines.append(f"Map: {result['map_name']}")
    lines.append(f"Turns: {result['num_turns']}")
    lines.append(f"Simulations: {result['runs']}")
    lines.append(
        "Decision Model: strategy + doctrine"
        if result["use_legacy_strategy_bias"]
        else "Decision Model: doctrine only"
    )
    lines.append("")
    lines.append("Outcome Balance")
    lines.append(
        f"  Win-rate spread: {outcome['win_rate_spread']:.2%} | "
        f"Win-rate stddev: {outcome['win_rate_stddev']:.3f}"
    )
    lines.append(
        f"{'Faction':<18} {'Strategy':<13} {'Win':>8} {'Shared':>8} {'Treasury':>10} {'Regions':>8} {'Elim':>8} {'ElimTurn':>10}"
    )
    lines.append("-" * 92)

    for faction_name in result["factions"]:
        elimination_turn = survival["average_elimination_turn"][faction_name]
        elimination_turn_text = f"{elimination_turn:.2f}" if elimination_turn is not None else "n/a"
        lines.append(
            f"{faction_name:<18} "
            f"{result['strategies'][faction_name]:<13} "
            f"{outcome['outright_win_rate'][faction_name]:>7.2%} "
            f"{outcome['shared_first_rate'][faction_name]:>7.2%} "
            f"{outcome['average_treasury'][faction_name]:>10.2f} "
            f"{outcome['average_regions'][faction_name]:>8.2f} "
            f"{survival['elimination_rate'][faction_name]:>7.2%} "
            f"{elimination_turn_text:>10}"
        )

    lines.append("")
    lines.append("Game Health")
    runaway_turn_text = (
        f"{health['average_runaway_turn']:.2f}"
        if health["average_runaway_turn"] is not None
        else "n/a"
    )
    lines.append(
        f"  Avg lead changes: {health['average_lead_changes']:.2f} | "
        f"Runaway rate: {health['runaway_rate']:.2%} | "
        f"Avg runaway turn: {runaway_turn_text}"
    )
    lines.append(
        f"  Comeback rate: {health['comeback_rate']:.2%} | "
        f"Avg comeback deficit overcome: {health['average_comeback_deficit']:.2f}"
    )
    lines.append(
        f"  Avg eliminated factions: {health['average_eliminated_factions']:.2f} | "
        f"Avg largest treasury lead: {health['average_largest_treasury_lead']:.2f} | "
        f"Avg largest region lead: {health['average_largest_region_lead']:.2f}"
    )

    lines.append("")
    lines.append("Pacing")
    for phase_name, actions in pacing.items():
        attack_attempts = actions["attacks"]
        successful_attacks = actions["successful_attacks"]
        attack_success_rate = (
            successful_attacks / attack_attempts
            if attack_attempts > 0
            else 0.0
        )
        lines.append(
            f"  {phase_name.title()}: attacks={attack_attempts:.2f}, "
            f"attack_success={attack_success_rate:.2%}, "
            f"expansions={actions['expansions']:.2f}, "
            f"investments={actions['investments']:.2f}"
        )

    return "\n".join(lines)


def build_report(results, skipped_maps, seed, use_legacy_strategy_bias):
    lines = []
    lines.append("Balance Dashboard Report")
    lines.append("")
    lines.append(f"Seed: {seed}")
    lines.append(
        "Legacy strategy bias: enabled"
        if use_legacy_strategy_bias
        else "Legacy strategy bias: disabled"
    )
    lines.append("")

    for index, result in enumerate(results):
        if index > 0:
            lines.append("")
            lines.append("=" * 92)
            lines.append("")
        lines.append(format_setting_report(result))

    if skipped_maps:
        lines.append("")
        lines.append("=" * 92)
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
    random.seed(args.seed)

    results = []
    skipped_maps = []

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
            results.append(
                summarize_setting(
                    map_name=map_name,
                    num_turns=num_turns,
                    runs=args.runs,
                    num_factions=args.num_factions,
                    use_legacy_strategy_bias=not args.disable_legacy_strategy_bias,
                )
            )

    report_text = build_report(
        results,
        skipped_maps,
        seed=args.seed,
        use_legacy_strategy_bias=not args.disable_legacy_strategy_bias,
    )
    print(report_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
