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
DEAD_SYSTEM_ACTIVE_RATE_THRESHOLD = 0.05


SYSTEM_DEFINITIONS = {
    "expansion": {
        "label": "Expansion",
        "event_types": {"expand"},
    },
    "war": {
        "label": "War",
        "event_types": {"attack", "war_declared", "war_peace"},
    },
    "development": {
        "label": "Development",
        "event_types": {"develop", "invest"},
    },
    "polity": {
        "label": "Polity Advancement",
        "event_types": {"polity_advance"},
    },
    "diplomacy": {
        "label": "Diplomacy",
        "event_types": {
            "diplomacy_alliance",
            "diplomacy_break",
            "diplomacy_pact",
            "diplomacy_rivalry",
            "diplomacy_tributary",
            "diplomacy_tributary_break",
            "diplomacy_truce",
            "diplomacy_truce_end",
            "war_declared",
            "war_peace",
        },
    },
    "trade_economy": {
        "label": "Trade Economy",
        "event_types": set(),
    },
    "trade_disruption": {
        "label": "Trade Disruption",
        "event_types": set(),
    },
    "administration": {
        "label": "Administration",
        "event_types": set(),
    },
    "unrest": {
        "label": "Unrest",
        "event_types": {
            "regime_agitation",
            "unrest_crisis",
            "unrest_disturbance",
            "unrest_secession",
        },
    },
    "rebellion": {
        "label": "Rebellion",
        "event_types": {"rebel_independence", "unrest_secession"},
    },
    "migration": {
        "label": "Migration",
        "event_types": {"migration_wave", "refugee_wave"},
    },
    "religion": {
        "label": "Religion",
        "event_types": {"religious_reform"},
    },
    "succession": {
        "label": "Succession",
        "event_types": {"succession", "succession_crisis"},
    },
    "food_stress": {
        "label": "Food Stress",
        "event_types": set(),
    },
    "technology": {
        "label": "Technology",
        "event_types": {"technology_adoption", "technology_institutionalized"},
    },
}


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
                elif event.type in {"develop", "invest"}:
                    phase_counts[phase_name]["investments"] += 1
                break

    return phase_counts


def _iter_faction_metric_rows(world):
    for snapshot in world.metrics:
        turn = int(snapshot.get("turn", 0) or 0)
        for faction_metrics in snapshot.get("factions", {}).values():
            yield turn, faction_metrics


def _metric_system_signals(world):
    signals = {
        "administration": [],
        "food_stress": [],
        "migration": [],
        "religion": [],
        "succession": [],
        "trade_disruption": [],
        "trade_economy": [],
        "technology": [],
    }

    for turn, metrics in _iter_faction_metric_rows(world):
        if (
            float(metrics.get("trade_income", 0.0) or 0.0) > 0.01
            or float(metrics.get("trade_transit_value", 0.0) or 0.0) > 0.01
            or float(metrics.get("trade_foreign_income", 0.0) or 0.0) > 0.01
            or float(metrics.get("trade_foreign_imported_flow", 0.0) or 0.0) > 0.01
            or float(metrics.get("trade_import_dependency", 0.0) or 0.0) > 0.05
        ):
            signals["trade_economy"].append(turn)

        if (
            float(metrics.get("trade_warfare_damage", 0.0) or 0.0) > 0.01
            or float(metrics.get("trade_blockade_losses", 0.0) or 0.0) > 0.01
        ):
            signals["trade_disruption"].append(turn)

        if (
            float(metrics.get("administrative_overextension", 0.0) or 0.0) > 0.05
            or float(metrics.get("administrative_overextension_penalty", 0.0) or 0.0) > 0.01
            or float(metrics.get("administrative_efficiency", 1.0) or 1.0) < 0.95
        ):
            signals["administration"].append(turn)

        if (
            float(metrics.get("food_deficit", 0.0) or 0.0) > 0.01
            or float(metrics.get("food_shortage", 0.0) or 0.0) > 0.01
            or float(metrics.get("food_balance", 0.0) or 0.0) < -0.01
        ):
            signals["food_stress"].append(turn)

        if (
            int(metrics.get("migration_inflow", 0) or 0) > 0
            or int(metrics.get("migration_outflow", 0) or 0) > 0
            or int(metrics.get("refugee_inflow", 0) or 0) > 0
            or int(metrics.get("refugee_outflow", 0) or 0) > 0
            or int(metrics.get("frontier_settlers", 0) or 0) > 0
        ):
            signals["migration"].append(turn)

        if (
            float(metrics.get("reform_pressure", 0.0) or 0.0) > 0.2
            or float(metrics.get("religious_legitimacy", 0.5) or 0.5) < 0.42
            or int(metrics.get("sacred_sites_controlled", 0) or 0)
            != int(metrics.get("total_sacred_sites", 0) or 0)
        ):
            signals["religion"].append(turn)

        if (
            int(metrics.get("regency_turns", 0) or 0) > 0
            or int(metrics.get("succession_crisis_turns", 0) or 0) > 0
            or float(metrics.get("claimant_pressure", 0.0) or 0.0) > 0.2
        ):
            signals["succession"].append(turn)

        if (
            float(metrics.get("average_technology_presence", 0.0) or 0.0) > 0.08
            or float(metrics.get("average_institutional_technology", 0.0) or 0.0) > 0.04
        ):
            signals["technology"].append(turn)

    return signals


def build_system_activity(world):
    metric_signals = _metric_system_signals(world)
    activity = {}

    for system_name, definition in SYSTEM_DEFINITIONS.items():
        event_types = definition["event_types"]
        matching_events = [
            event
            for event in world.events
            if event.type in event_types
        ]
        if system_name == "trade_disruption":
            matching_events = [
                event
                for event in world.events
                if event.type == "attack"
                and (
                    event.get("trade_warfare_hit", False)
                    or float(event.get("trade_warfare_pressure_added", 0.0) or 0.0) > 0.08
                    or float(event.get("trade_blockade_added", 0.0) or 0.0) > 0.0
                )
            ]
        event_count = len(matching_events)
        signal_turns = [
            event.turn + 1
            for event in matching_events
        ]

        signal_turns.extend(metric_signals.get(system_name, []))
        first_turn = min(signal_turns) if signal_turns else None

        activity[system_name] = {
            "label": definition["label"],
            "event_count": event_count,
            "metric_signal_count": len(metric_signals.get(system_name, [])),
            "active": first_turn is not None,
            "first_turn": first_turn,
        }

    return activity


def summarize_setting(map_name, num_turns, runs, num_factions):
    template_world = create_world(
        map_name=map_name,
        num_factions=num_factions,
    )
    faction_names = list(template_world.factions.keys())
    doctrines = {
        faction_name: faction.doctrine_label
        for faction_name, faction in template_world.factions.items()
    }
    phase_names = [phase_name for phase_name, _start_turn, _end_turn in get_phase_ranges(num_turns)]

    outright_wins = {faction_name: 0 for faction_name in faction_names}
    shared_firsts = {faction_name: 0 for faction_name in faction_names}
    non_starting_outright_wins = 0
    non_starting_shared_firsts = 0
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
    final_faction_counts = []
    diplomacy_event_counts = {
        "truces": [],
        "truce_ends": [],
        "pacts": [],
        "alliances": [],
        "rivalries": [],
        "breaks": [],
        "secessions": [],
        "independence": [],
    }
    system_activity = {
        system_name: {
            "event_counts": [],
            "metric_signal_counts": [],
            "active_runs": 0,
            "first_turns": [],
        }
        for system_name in SYSTEM_DEFINITIONS
    }

    for _ in range(runs):
        world = create_world(
            map_name=map_name,
            num_factions=num_factions,
        )
        world = run_simulation(world, num_turns=num_turns, verbose=False)
        final_regions = count_owned_regions(world)
        competition = analyze_competition_metrics(world)
        phase_counts = build_phase_action_counts(world)
        run_system_activity = build_system_activity(world)

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
            if leaders[0] in outright_wins:
                outright_wins[leaders[0]] += 1
            else:
                non_starting_outright_wins += 1
        else:
            for faction_name in leaders:
                if faction_name in shared_firsts:
                    shared_firsts[faction_name] += 1
                else:
                    non_starting_shared_firsts += 1

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

        for system_name, activity in run_system_activity.items():
            system_activity[system_name]["event_counts"].append(activity["event_count"])
            system_activity[system_name]["metric_signal_counts"].append(activity["metric_signal_count"])
            if activity["active"]:
                system_activity[system_name]["active_runs"] += 1
            if activity["first_turn"] is not None:
                system_activity[system_name]["first_turns"].append(activity["first_turn"])

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
        final_faction_counts.append(len(world.factions))

        event_type_counts = {
            "diplomacy_truce": 0,
            "diplomacy_truce_end": 0,
            "diplomacy_pact": 0,
            "diplomacy_alliance": 0,
            "diplomacy_rivalry": 0,
            "diplomacy_break": 0,
            "unrest_secession": 0,
            "rebel_independence": 0,
        }
        for event in world.events:
            if event.type in event_type_counts:
                event_type_counts[event.type] += 1
        diplomacy_event_counts["truces"].append(event_type_counts["diplomacy_truce"])
        diplomacy_event_counts["truce_ends"].append(event_type_counts["diplomacy_truce_end"])
        diplomacy_event_counts["pacts"].append(event_type_counts["diplomacy_pact"])
        diplomacy_event_counts["alliances"].append(event_type_counts["diplomacy_alliance"])
        diplomacy_event_counts["rivalries"].append(event_type_counts["diplomacy_rivalry"])
        diplomacy_event_counts["breaks"].append(event_type_counts["diplomacy_break"])
        diplomacy_event_counts["secessions"].append(event_type_counts["unrest_secession"])
        diplomacy_event_counts["independence"].append(event_type_counts["rebel_independence"])

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
        "factions": faction_names,
        "doctrines": doctrines,
        "outcome_balance": {
            "outright_win_rate": outright_win_rates,
            "shared_first_rate": shared_first_rates,
            "non_starting_outright_win_rate": non_starting_outright_wins / runs,
            "non_starting_shared_first_rate": non_starting_shared_firsts / runs,
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
            "average_final_factions": mean(final_faction_counts) if final_faction_counts else 0.0,
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
        "diplomacy": {
            metric_name: mean(values) if values else 0.0
            for metric_name, values in diplomacy_event_counts.items()
        },
        "system_activity": {
            system_name: {
                "label": SYSTEM_DEFINITIONS[system_name]["label"],
                "average_events": mean(values["event_counts"]) if values["event_counts"] else 0.0,
                "average_metric_signals": (
                    mean(values["metric_signal_counts"])
                    if values["metric_signal_counts"]
                    else 0.0
                ),
                "active_rate": values["active_runs"] / runs,
                "dead_run_rate": 1.0 - (values["active_runs"] / runs),
                "average_first_turn": (
                    mean(values["first_turns"])
                    if values["first_turns"]
                    else None
                ),
                "status": (
                    "dead"
                    if (values["active_runs"] / runs) < DEAD_SYSTEM_ACTIVE_RATE_THRESHOLD
                    else "active"
                ),
            }
            for system_name, values in system_activity.items()
        },
    }


def format_setting_report(result):
    lines = []
    outcome = result["outcome_balance"]
    health = result["game_health"]
    survival = result["survival"]
    pacing = result["pacing"]
    diplomacy = result["diplomacy"]
    system_activity = result["system_activity"]

    lines.append(f"Map: {result['map_name']}")
    lines.append(f"Turns: {result['num_turns']}")
    lines.append(f"Simulations: {result['runs']}")
    lines.append("Decision Model: doctrine only")
    lines.append("")
    lines.append("Outcome Balance")
    lines.append(
        f"  Win-rate spread: {outcome['win_rate_spread']:.2%} | "
        f"Win-rate stddev: {outcome['win_rate_stddev']:.3f}"
    )
    lines.append(
        f"  Non-starting outright wins: {outcome['non_starting_outright_win_rate']:.2%} | "
        f"Non-starting shared firsts: {outcome['non_starting_shared_first_rate']:.2%}"
    )
    lines.append(
        f"{'Faction':<18} {'Doctrine':<24} {'Win':>8} {'Shared':>8} {'Treasury':>10} {'Regions':>8} {'Elim':>8} {'ElimTurn':>10}"
    )
    lines.append("-" * 103)

    for faction_name in result["factions"]:
        elimination_turn = survival["average_elimination_turn"][faction_name]
        elimination_turn_text = f"{elimination_turn:.2f}" if elimination_turn is not None else "n/a"
        lines.append(
            f"{faction_name:<18} "
            f"{result['doctrines'][faction_name]:<24} "
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
        f"Avg largest region lead: {health['average_largest_region_lead']:.2f} | "
        f"Avg final factions: {health['average_final_factions']:.2f}"
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

    lines.append("")
    lines.append("Political Dynamics")
    lines.append(
        f"  Truces={diplomacy['truces']:.2f} | "
        f"Truce endings={diplomacy['truce_ends']:.2f} | "
        f"Pacts={diplomacy['pacts']:.2f} | "
        f"Alliances={diplomacy['alliances']:.2f} | "
        f"Rivalries={diplomacy['rivalries']:.2f} | "
        f"Breaks={diplomacy['breaks']:.2f}"
    )
    lines.append(
        f"  Secessions={diplomacy['secessions']:.2f} | "
        f"Rebel independence={diplomacy['independence']:.2f}"
    )

    lines.append("")
    lines.append("System Activity")
    lines.append(
        f"{'System':<20} {'Status':<8} {'Active':>8} {'DeadRun':>8} "
        f"{'Events':>8} {'Signals':>8} {'FirstTurn':>10}"
    )
    lines.append("-" * 82)
    for system_name in SYSTEM_DEFINITIONS:
        activity = system_activity.get(system_name)
        if activity is None:
            activity = {
                "label": SYSTEM_DEFINITIONS[system_name]["label"],
                "average_events": 0.0,
                "average_metric_signals": 0.0,
                "active_rate": 0.0,
                "dead_run_rate": 1.0,
                "average_first_turn": None,
                "status": "dead",
            }
        first_turn = activity["average_first_turn"]
        first_turn_text = f"{first_turn:.2f}" if first_turn is not None else "n/a"
        lines.append(
            f"{activity['label']:<20} "
            f"{activity['status']:<8} "
            f"{activity['active_rate']:>7.2%} "
            f"{activity['dead_run_rate']:>7.2%} "
            f"{activity['average_events']:>8.2f} "
            f"{activity['average_metric_signals']:>8.2f} "
            f"{first_turn_text:>10}"
        )

    dead_systems = [
        activity["label"]
        for activity in system_activity.values()
        if activity["status"] == "dead"
    ]
    if dead_systems:
        lines.append(f"  Dead or near-silent systems: {', '.join(dead_systems)}")
    else:
        lines.append("  Dead or near-silent systems: none")

    return "\n".join(lines)


def build_report(results, skipped_maps, seed):
    lines = []
    lines.append("Balance Dashboard Report")
    lines.append("")
    lines.append(f"Seed: {seed}")
    lines.append("Legacy strategy bias: removed")
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
                )
            )

    report_text = build_report(
        results,
        skipped_maps,
        seed=args.seed,
    )
    print(report_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
