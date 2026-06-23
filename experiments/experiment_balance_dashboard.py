from __future__ import annotations

import argparse
import random
import sys
from collections import Counter
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
PROTECTED_ATTACK_STATUSES = {
    "alliance",
    "non_aggression_pact",
    "overlord",
    "tributary",
    "truce",
}
RUNAWAY_CONTEXT_METRICS = (
    "treasury",
    "regions",
    "population",
    "effective_income",
    "net_income",
    "force_projection",
    "manpower_pool",
    "military_readiness",
    "administrative_efficiency",
    "administrative_overextension",
    "capital_isolated_regions",
    "capital_fragment_count",
    "capital_connectivity_penalty",
    "shock_exposure",
    "shock_resilience",
    "average_institutional_technology",
    "bloc_action_bias_abs",
)
RUNAWAY_BOOL_METRICS = (
    "dual_track_qualified",
    "dual_track_both_tracks_used",
    "military_track_used",
    "admin_track_used",
)


SYSTEM_DEFINITIONS = {
    "expansion": {
        "label": "Expansion",
        "event_types": {"expand"},
    },
    "war": {
        "label": "War",
        "event_types": {"attack", "war_declared", "war_peace"},
    },
    "military_institution": {
        "label": "Military Institution",
        "event_types": {"military_reform", "military_battle_losses"},
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
    "long_cycle_shocks": {
        "label": "Long-Cycle Shocks",
        "event_types": {
            "shock_climate_anomaly",
            "shock_famine",
            "shock_epidemic",
            "shock_soil_exhaustion",
            "shock_ecological_degradation",
            "shock_resource_depletion",
            "shock_trade_collapse",
            "shock_population_loss",
            "shock_recovery",
        },
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
        "long_cycle_shocks": [],
        "military_institution": [],
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
            float(metrics.get("shock_exposure", 0.0) or 0.0) > 0.05
            or float(metrics.get("famine_pressure", 0.0) or 0.0) > 0.02
            or float(metrics.get("epidemic_pressure", 0.0) or 0.0) > 0.02
            or float(metrics.get("trade_collapse_exposure", 0.0) or 0.0) > 0.02
        ):
            signals["long_cycle_shocks"].append(turn)

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

        if (
            float(metrics.get("standing_forces", 0.0) or 0.0) > 0.1
            or float(metrics.get("manpower_capacity", 0.0) or 0.0) > 0.1
            or float(metrics.get("logistics_capacity", 0.0) or 0.0) > 0.1
            or float(metrics.get("naval_power", 0.0) or 0.0) > 0.1
            or float(metrics.get("military_reform_pressure", 0.0) or 0.0) > 0.05
        ):
            signals["military_institution"].append(turn)

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


def _track_size_bucket(region_count: int) -> str:
    if region_count <= 3:
        return "1-3"
    if region_count <= 7:
        return "4-7"
    return "8+"


def build_dual_track_observability(world):
    qualifying_turns = 0
    both_track_turns = 0
    bias_total = 0.0
    bias_samples = 0
    military_action_count = 0
    military_dominant_action_count = 0
    size_buckets = {
        bucket: {
            "samples": 0,
            "military_track_uses": 0,
            "admin_track_uses": 0,
        }
        for bucket in ("1-3", "4-7", "8+")
    }

    for _turn, metrics in _iter_faction_metric_rows(world):
        region_count = int(metrics.get("regions", 0) or 0)
        military_used = bool(metrics.get("military_track_used", False))
        admin_used = bool(metrics.get("admin_track_used", False))
        bucket = _track_size_bucket(region_count)
        size_buckets[bucket]["samples"] += 1
        size_buckets[bucket]["military_track_uses"] += int(military_used)
        size_buckets[bucket]["admin_track_uses"] += int(admin_used)

        if metrics.get("dual_track_qualified", False):
            qualifying_turns += 1
            both_track_turns += int(metrics.get("dual_track_both_tracks_used", False))

        bias_total += float(metrics.get("bloc_action_bias_abs", 0.0) or 0.0)
        bias_samples += 1

        row_military_actions = int(metrics.get("attacks", 0) or 0) + int(metrics.get("expansions", 0) or 0)
        military_action_count += row_military_actions
        if metrics.get("dominant_bloc_track") == "military":
            military_dominant_action_count += row_military_actions

    track_split_by_faction_size = {}
    for bucket, values in size_buckets.items():
        samples = values["samples"]
        track_split_by_faction_size[bucket] = {
            "samples": samples,
            "military_track_rate": values["military_track_uses"] / samples if samples else 0.0,
            "admin_track_rate": values["admin_track_uses"] / samples if samples else 0.0,
        }

    return {
        "qualifying_turns": qualifying_turns,
        "both_track_turns": both_track_turns,
        "dual_track_activation_rate": both_track_turns / qualifying_turns if qualifying_turns else 0.0,
        "bloc_competition_delta": bias_total / bias_samples if bias_samples else 0.0,
        "bloc_competition_delta_sum": bias_total,
        "bloc_competition_delta_samples": bias_samples,
        "military_action_count": military_action_count,
        "military_dominant_action_count": military_dominant_action_count,
        "dominant_bloc_action_alignment": (
            military_dominant_action_count / military_action_count
            if military_action_count
            else 0.0
        ),
        "track_split_by_faction_size": track_split_by_faction_size,
    }


def _safe_number(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _average(values):
    return mean(values) if values else 0.0


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def _snapshot_turn(snapshot):
    return int(snapshot.get("turn", 0) or 0)


def _turn_horizon(world, action_diagnostics=None):
    event_turns = [event.turn + 1 for event in world.events]
    diagnostic_turns = [
        int(record.get("turn", 0) or 0)
        for record in (action_diagnostics or [])
    ]
    return max(
        [1, len(world.metrics), int(getattr(world, "turn", 0) or 0)]
        + event_turns
        + diagnostic_turns
    )


def _phase_for_turn(turn, phase_ranges):
    for phase_name, start_turn, end_turn in phase_ranges:
        if start_turn <= turn <= end_turn:
            return phase_name
    return phase_ranges[-1][0] if phase_ranges else "all"


def _rank_snapshot(snapshot, metric_key):
    return sorted(
        snapshot.get("factions", {}).items(),
        key=lambda item: (_safe_number(item[1].get(metric_key)), item[0]),
        reverse=True,
    )


def _metric_margin(snapshot, faction_name, metric_key):
    factions = snapshot.get("factions", {})
    faction_metrics = factions.get(faction_name)
    if not faction_metrics:
        return {
            "runner_up": None,
            "winner_value": 0.0,
            "runner_up_value": 0.0,
            "margin": 0.0,
        }

    ranked = [
        (name, metrics)
        for name, metrics in _rank_snapshot(snapshot, metric_key)
        if name != faction_name
    ]
    runner_name, runner_metrics = ranked[0] if ranked else (None, {})
    winner_value = _safe_number(faction_metrics.get(metric_key))
    runner_value = _safe_number(runner_metrics.get(metric_key))
    return {
        "runner_up": runner_name,
        "winner_value": winner_value,
        "runner_up_value": runner_value,
        "margin": winner_value - runner_value,
    }


def _nearest_snapshot(world, target_turn):
    if not world.metrics:
        return None
    return min(
        world.metrics,
        key=lambda snapshot: (
            abs(_snapshot_turn(snapshot) - target_turn),
            _snapshot_turn(snapshot),
        ),
    )


def _dominant_runaway_advantage(snapshot_summary):
    candidate_margins = {
        "treasury": snapshot_summary.get("treasury_margin", 0.0),
        "regions": snapshot_summary.get("region_margin", 0.0),
        "force_projection": snapshot_summary.get("force_projection_margin", 0.0),
        "net_income": snapshot_summary.get("net_income_margin", 0.0),
        "admin_efficiency": snapshot_summary.get("admin_efficiency_margin", 0.0),
        "capital_cohesion": -snapshot_summary.get(
            "capital_connectivity_penalty_gap",
            0.0,
        ),
        "technology": snapshot_summary.get("technology_margin", 0.0),
        "shock_resilience": snapshot_summary.get("shock_resilience_margin", 0.0),
    }
    if not candidate_margins:
        return "none"
    name, value = max(candidate_margins.items(), key=lambda item: (item[1], item[0]))
    return name if value > 0 else "none"


def _build_runaway_snapshot(snapshot, winner, label):
    faction_metrics = snapshot.get("factions", {}).get(winner, {})
    treasury_margin = _metric_margin(snapshot, winner, "treasury")
    summary = {
        "label": label,
        "turn": _snapshot_turn(snapshot),
        "winner": winner,
        "runner_up": treasury_margin["runner_up"],
    }

    for metric_key in RUNAWAY_CONTEXT_METRICS:
        summary[metric_key] = _safe_number(faction_metrics.get(metric_key))

    for metric_key in RUNAWAY_BOOL_METRICS:
        summary[metric_key] = bool(faction_metrics.get(metric_key, False))

    margin_specs = {
        "treasury": "treasury_margin",
        "regions": "region_margin",
        "population": "population_margin",
        "effective_income": "effective_income_margin",
        "net_income": "net_income_margin",
        "force_projection": "force_projection_margin",
        "manpower_pool": "manpower_margin",
        "military_readiness": "military_readiness_margin",
        "administrative_efficiency": "admin_efficiency_margin",
        "administrative_overextension": "admin_overextension_gap",
        "capital_isolated_regions": "capital_isolated_region_gap",
        "capital_fragment_count": "capital_fragment_gap",
        "capital_connectivity_penalty": "capital_connectivity_penalty_gap",
        "shock_exposure": "shock_exposure_gap",
        "shock_resilience": "shock_resilience_margin",
        "average_institutional_technology": "technology_margin",
    }
    for metric_key, output_key in margin_specs.items():
        summary[output_key] = _metric_margin(snapshot, winner, metric_key)["margin"]

    summary["dominant_advantage"] = _dominant_runaway_advantage(summary)
    return summary


def build_runaway_context(world, competition=None):
    if competition is None:
        competition = analyze_competition_metrics(world)

    runaway = competition.get("runaway", {})
    winner = runaway.get("winner")
    start_turn = runaway.get("start_turn")
    context = {
        "detected": bool(runaway.get("detected", False)),
        "winner": winner,
        "start_turn": start_turn,
        "snapshots": [],
        "average_treasury_margin": 0.0,
        "average_region_margin": 0.0,
        "average_force_projection_margin": 0.0,
        "average_net_income_margin": 0.0,
        "average_admin_efficiency_margin": 0.0,
        "average_winner_capital_isolated_regions": 0.0,
        "average_winner_capital_fragment_count": 0.0,
        "average_winner_capital_connectivity_penalty": 0.0,
        "average_capital_isolated_region_gap": 0.0,
        "average_capital_fragment_gap": 0.0,
        "average_capital_connectivity_penalty_gap": 0.0,
        "average_shock_exposure_gap": 0.0,
        "average_shock_resilience_margin": 0.0,
        "average_technology_margin": 0.0,
        "dominant_advantage_counts": {},
    }
    if not context["detected"] or winner is None or start_turn is None:
        return context

    final_turn = _snapshot_turn(world.metrics[-1]) if world.metrics else start_turn
    target_snapshots = [
        ("pre_runaway", max(1, int(start_turn) - 10)),
        ("runaway_start", int(start_turn)),
        ("post_runaway", min(final_turn, int(start_turn) + 10)),
        ("final", final_turn),
    ]
    seen_turns = set()
    for label, target_turn in target_snapshots:
        snapshot = _nearest_snapshot(world, target_turn)
        if snapshot is None:
            continue
        snapshot_turn = _snapshot_turn(snapshot)
        if snapshot_turn in seen_turns:
            continue
        seen_turns.add(snapshot_turn)
        context["snapshots"].append(_build_runaway_snapshot(snapshot, winner, label))

    snapshots = context["snapshots"]
    context["average_treasury_margin"] = _average([
        snapshot["treasury_margin"] for snapshot in snapshots
    ])
    context["average_region_margin"] = _average([
        snapshot["region_margin"] for snapshot in snapshots
    ])
    context["average_force_projection_margin"] = _average([
        snapshot["force_projection_margin"] for snapshot in snapshots
    ])
    context["average_net_income_margin"] = _average([
        snapshot["net_income_margin"] for snapshot in snapshots
    ])
    context["average_admin_efficiency_margin"] = _average([
        snapshot["admin_efficiency_margin"] for snapshot in snapshots
    ])
    context["average_winner_capital_isolated_regions"] = _average([
        snapshot["capital_isolated_regions"] for snapshot in snapshots
    ])
    context["average_winner_capital_fragment_count"] = _average([
        snapshot["capital_fragment_count"] for snapshot in snapshots
    ])
    context["average_winner_capital_connectivity_penalty"] = _average([
        snapshot["capital_connectivity_penalty"] for snapshot in snapshots
    ])
    context["average_capital_isolated_region_gap"] = _average([
        snapshot["capital_isolated_region_gap"] for snapshot in snapshots
    ])
    context["average_capital_fragment_gap"] = _average([
        snapshot["capital_fragment_gap"] for snapshot in snapshots
    ])
    context["average_capital_connectivity_penalty_gap"] = _average([
        snapshot["capital_connectivity_penalty_gap"] for snapshot in snapshots
    ])
    context["average_shock_exposure_gap"] = _average([
        snapshot["shock_exposure_gap"] for snapshot in snapshots
    ])
    context["average_shock_resilience_margin"] = _average([
        snapshot["shock_resilience_margin"] for snapshot in snapshots
    ])
    context["average_technology_margin"] = _average([
        snapshot["technology_margin"] for snapshot in snapshots
    ])
    context["dominant_advantage_counts"] = dict(Counter(
        snapshot["dominant_advantage"] for snapshot in snapshots
    ))
    return context


def build_relationship_pressure(world):
    status_counts = Counter(
        relationship.status
        for relationship in world.relationships.values()
    )
    active_wars = [
        war
        for war in world.wars.values()
        if getattr(war, "active", False)
    ]
    tributary_pressure = status_counts.get("tributary", 0) + sum(
        1
        for relationship in world.relationships.values()
        if relationship.subordinate_faction is not None
    )
    war_exhaustion = [
        _safe_number(getattr(war, "war_exhaustion", 0.0))
        for war in active_wars
    ]

    return {
        "active_war_count": len(active_wars),
        "war_count": len(world.wars),
        "rivalry_count": status_counts.get("rival", 0),
        "pact_count": status_counts.get("non_aggression_pact", 0),
        "alliance_count": status_counts.get("alliance", 0),
        "pact_alliance_count": (
            status_counts.get("non_aggression_pact", 0)
            + status_counts.get("alliance", 0)
        ),
        "tributary_pressure_count": tributary_pressure,
        "average_active_war_exhaustion": _average(war_exhaustion),
        "peak_active_war_exhaustion": max(war_exhaustion) if war_exhaustion else 0.0,
        "relationship_status_counts": dict(status_counts),
    }


def build_late_war_cadence(world):
    phase_ranges = get_phase_ranges(_turn_horizon(world))
    phase_data = {
        phase_name: {
            "attacks": 0,
            "successful_attacks": 0,
            "active_war_attacks": 0,
            "rival_attacks": 0,
            "protected_target_attacks": 0,
            "active_war_objective_attacks": 0,
            "low_score_attacks": 0,
            "repeated_same_pair_attacks": 0,
            "pair_region_counts": Counter(),
            "success_chances": [],
            "supply_risks": [],
            "attacker_readiness": [],
            "manpower_commitments": [],
            "attacker_manpower": [],
            "manpower_commitment_ratios": [],
            "target_values": [],
            "scores": [],
        }
        for phase_name, _start_turn, _end_turn in phase_ranges
    }

    for event in world.events:
        if event.type != "attack":
            continue

        phase_name = _phase_for_turn(event.turn + 1, phase_ranges)
        data = phase_data[phase_name]
        data["attacks"] += 1
        if event.get("success", False):
            data["successful_attacks"] += 1

        diplomacy_status = str(event.get("diplomacy_status", "") or "")
        active_war_bonus = _safe_number(event.get("active_war_bonus", 0.0))
        if (
            active_war_bonus > 0
            or bool(event.get("active_war_objective", False))
            or bool(event.get("war_objective", False))
            or diplomacy_status == "war"
        ):
            data["active_war_attacks"] += 1
        if bool(event.get("active_war_objective", False)):
            data["active_war_objective_attacks"] += 1
        if diplomacy_status == "rival":
            data["rival_attacks"] += 1
        if diplomacy_status in PROTECTED_ATTACK_STATUSES:
            data["protected_target_attacks"] += 1

        score = _safe_number(event.get("score", None), default=None)
        success_chance = _safe_number(event.get("success_chance", None), default=None)
        if score is not None:
            data["scores"].append(score)
        if success_chance is not None:
            data["success_chances"].append(success_chance)
        if (
            score is not None
            and score <= 45
        ) or (
            success_chance is not None
            and success_chance <= 0.35
        ):
            data["low_score_attacks"] += 1

        defender = event.get("defender", event.get("target_owner", ""))
        pair_region_key = (event.faction, defender, event.region)
        if data["pair_region_counts"][pair_region_key] > 0:
            data["repeated_same_pair_attacks"] += 1
        data["pair_region_counts"][pair_region_key] += 1

        for event_key, list_key in (
            ("supply_risk", "supply_risks"),
            ("attacker_readiness", "attacker_readiness"),
            ("manpower_commitment", "manpower_commitments"),
            ("attacker_manpower", "attacker_manpower"),
            ("target_taxable_value", "target_values"),
        ):
            value = _safe_number(event.get(event_key, None), default=None)
            if value is not None:
                data[list_key].append(value)

        manpower_commitment = _safe_number(event.get("manpower_commitment", None), default=None)
        attacker_manpower = _safe_number(event.get("attacker_manpower", None), default=None)
        if manpower_commitment is not None and attacker_manpower and attacker_manpower > 0:
            data["manpower_commitment_ratios"].append(
                min(1.0, manpower_commitment / attacker_manpower)
            )

    return {
        phase_name: {
            "attacks": data["attacks"],
            "successful_attacks": data["successful_attacks"],
            "attack_success_rate": _ratio(data["successful_attacks"], data["attacks"]),
            "active_war_attacks": data["active_war_attacks"],
            "active_war_attack_rate": _ratio(data["active_war_attacks"], data["attacks"]),
            "rival_attacks": data["rival_attacks"],
            "rival_attack_rate": _ratio(data["rival_attacks"], data["attacks"]),
            "protected_target_attacks": data["protected_target_attacks"],
            "protected_target_attack_rate": _ratio(
                data["protected_target_attacks"],
                data["attacks"],
            ),
            "active_war_objective_attacks": data["active_war_objective_attacks"],
            "active_war_objective_rate": _ratio(
                data["active_war_objective_attacks"],
                data["attacks"],
            ),
            "low_score_attacks": data["low_score_attacks"],
            "low_score_attack_rate": _ratio(data["low_score_attacks"], data["attacks"]),
            "repeated_same_pair_attacks": data["repeated_same_pair_attacks"],
            "repeated_same_pair_attack_rate": _ratio(
                data["repeated_same_pair_attacks"],
                data["attacks"],
            ),
            "average_success_chance": _average(data["success_chances"]),
            "average_supply_risk": _average(data["supply_risks"]),
            "average_attacker_readiness": _average(data["attacker_readiness"]),
            "average_manpower_commitment": _average(data["manpower_commitments"]),
            "average_attacker_manpower": _average(data["attacker_manpower"]),
            "average_manpower_commitment_ratio": _average(
                data["manpower_commitment_ratios"]
            ),
            "average_target_value": _average(data["target_values"]),
            "average_score": _average(data["scores"]),
        }
        for phase_name, data in phase_data.items()
    }


def build_shock_volume_diagnostics(world):
    shock_events = [
        event
        for event in world.events
        if event.type.startswith("shock_")
    ]
    event_type_counts = Counter(event.type for event in shock_events)
    shocks_by_id = {}
    for shock in list(world.shock_history) + list(world.active_shocks):
        shocks_by_id[getattr(shock, "id", id(shock))] = shock

    shock_kind_counts = Counter()
    durations_by_kind = {}
    affected_regions_by_kind = {}
    intensities_by_kind = {}
    for shock in shocks_by_id.values():
        kind = getattr(shock, "kind", "unknown")
        shock_kind_counts[kind] += 1
        durations_by_kind.setdefault(kind, []).append(
            _safe_number(getattr(shock, "duration_turns", 0.0))
        )
        affected_regions_by_kind.setdefault(kind, []).append(
            len(getattr(shock, "affected_regions", []) or [])
        )
        intensities_by_kind.setdefault(kind, []).append(
            _safe_number(getattr(shock, "intensity", 0.0))
        )

    exposure_samples = []
    resilience_samples = []
    active_pressure_turns = 0
    faction_turns = 0
    for _turn, metrics in _iter_faction_metric_rows(world):
        exposure = _safe_number(metrics.get("shock_exposure", 0.0))
        resilience = _safe_number(metrics.get("shock_resilience", 0.0))
        exposure_samples.append(exposure)
        resilience_samples.append(resilience)
        faction_turns += 1
        if (
            _safe_number(metrics.get("famine_pressure", 0.0)) > 0.05
            or _safe_number(metrics.get("epidemic_pressure", 0.0)) > 0.05
            or _safe_number(metrics.get("trade_collapse_exposure", 0.0)) > 0.05
        ):
            active_pressure_turns += 1

    population_loss_events = event_type_counts.get("shock_population_loss", 0)
    total_population_loss = sum(
        int(event.get("population_loss", event.get("loss", 0)) or 0)
        for event in shock_events
        if event.type == "shock_population_loss"
    )
    recovery_events = event_type_counts.get("shock_recovery", 0)
    onset_events = len(shock_events) - recovery_events - population_loss_events

    return {
        "shock_event_count": len(shock_events),
        "event_type_counts": dict(event_type_counts),
        "onset_event_count": onset_events,
        "recovery_event_count": recovery_events,
        "population_loss_event_count": population_loss_events,
        "total_population_loss": total_population_loss,
        "unique_shock_count": len(shocks_by_id),
        "shock_count_by_kind": dict(shock_kind_counts),
        "shock_kind_summary": {
            kind: {
                "count": shock_kind_counts[kind],
                "average_duration": _average(durations_by_kind.get(kind, [])),
                "average_affected_regions": _average(
                    affected_regions_by_kind.get(kind, [])
                ),
                "average_intensity": _average(intensities_by_kind.get(kind, [])),
            }
            for kind in sorted(shock_kind_counts)
        },
        "average_faction_shock_exposure": _average(exposure_samples),
        "peak_faction_shock_exposure": max(exposure_samples) if exposure_samples else 0.0,
        "average_faction_shock_resilience": _average(resilience_samples),
        "peak_faction_shock_resilience": max(resilience_samples) if resilience_samples else 0.0,
        "active_famine_epidemic_trade_turn_rate": _ratio(
            active_pressure_turns,
            faction_turns,
        ),
    }


def _correlation(x_values, y_values):
    pairs = [
        (float(x_value), float(y_value))
        for x_value, y_value in zip(x_values, y_values)
        if x_value is not None and y_value is not None
    ]
    if len(pairs) < 2:
        return 0.0
    x_mean = mean(x for x, _y in pairs)
    y_mean = mean(y for _x, y in pairs)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    x_denominator = sum((x - x_mean) ** 2 for x, _y in pairs) ** 0.5
    y_denominator = sum((y - y_mean) ** 2 for _x, y in pairs) ** 0.5
    if not x_denominator or not y_denominator:
        return 0.0
    return numerator / (x_denominator * y_denominator)


def build_pressure_propagation_checks(world):
    rows = [metrics for _turn, metrics in _iter_faction_metric_rows(world)]
    region_counts = [_safe_number(metrics.get("regions", 0.0)) for metrics in rows]
    admin_efficiencies = [
        _safe_number(metrics.get("administrative_efficiency", 1.0))
        for metrics in rows
    ]
    overextensions = [
        _safe_number(metrics.get("administrative_overextension", 0.0))
        for metrics in rows
    ]
    capital_isolated_regions = [
        _safe_number(metrics.get("capital_isolated_regions", 0.0))
        for metrics in rows
    ]
    capital_fragment_counts = [
        _safe_number(metrics.get("capital_fragment_count", 0.0))
        for metrics in rows
    ]
    capital_connectivity_penalties = [
        _safe_number(metrics.get("capital_connectivity_penalty", 0.0))
        for metrics in rows
    ]
    admin_reaches = [
        _safe_number(metrics.get("administrative_reach", 1.0))
        for metrics in rows
    ]
    elite_unrest = [
        _safe_number(metrics.get("elite_unrest_pressure", 0.0))
        for metrics in rows
    ]
    manpower_ratios = [
        (
            _safe_number(metrics.get("manpower_pool", 0.0))
            / _safe_number(metrics.get("manpower_capacity", 0.0))
        )
        if _safe_number(metrics.get("manpower_capacity", 0.0)) > 0
        else None
        for metrics in rows
    ]
    attacks = [_safe_number(metrics.get("attacks", 0.0)) for metrics in rows]
    readiness = [
        _safe_number(metrics.get("military_readiness", 0.0))
        for metrics in rows
    ]
    upkeep = [
        _safe_number(metrics.get("military_upkeep", 0.0))
        for metrics in rows
    ]
    shock_exposures = [
        _safe_number(metrics.get("shock_exposure", 0.0))
        for metrics in rows
    ]
    food_deficits = [
        _safe_number(metrics.get("food_deficit", 0.0))
        for metrics in rows
    ]
    migration_outflows = [
        _safe_number(metrics.get("migration_outflow", 0.0))
        + _safe_number(metrics.get("refugee_outflow", 0.0))
        for metrics in rows
    ]
    net_incomes = [
        _safe_number(metrics.get("net_income", 0.0))
        for metrics in rows
    ]
    developments = [
        _safe_number(metrics.get("developments", metrics.get("investments", 0.0)))
        for metrics in rows
    ]
    trade_pressures = [
        max(
            _safe_number(metrics.get("trade_import_dependency", 0.0)),
            _safe_number(metrics.get("trade_corridor_exposure", 0.0)),
            _safe_number(metrics.get("trade_blockade_losses", 0.0)),
            _safe_number(metrics.get("trade_collapse_exposure", 0.0)),
        )
        for metrics in rows
    ]
    bloc_biases = [
        _safe_number(metrics.get("bloc_action_bias_abs", 0.0))
        for metrics in rows
    ]

    large_state_rows = [
        metrics
        for metrics in rows
        if _safe_number(metrics.get("regions", 0.0)) >= 8
    ]
    high_shock_rows = [
        metrics
        for metrics in rows
        if _safe_number(metrics.get("shock_exposure", 0.0)) >= 0.25
    ]
    trade_pressure_rows = [
        metrics
        for metrics in rows
        if max(
            _safe_number(metrics.get("trade_import_dependency", 0.0)),
            _safe_number(metrics.get("trade_corridor_exposure", 0.0)),
            _safe_number(metrics.get("trade_blockade_losses", 0.0)),
            _safe_number(metrics.get("trade_collapse_exposure", 0.0)),
        ) >= 0.2
    ]
    capital_pressure_rows = [
        metrics
        for metrics in rows
        if (
            _safe_number(metrics.get("capital_isolated_regions", 0.0)) > 0.0
            or _safe_number(metrics.get("capital_connectivity_penalty", 0.0)) > 0.0
        )
    ]

    return {
        "samples": len(rows),
        "large_state_samples": len(large_state_rows),
        "large_state_average_admin_efficiency": _average([
            _safe_number(metrics.get("administrative_efficiency", 1.0))
            for metrics in large_state_rows
        ]),
        "large_state_average_overextension": _average([
            _safe_number(metrics.get("administrative_overextension", 0.0))
            for metrics in large_state_rows
        ]),
        "large_state_average_capital_isolated_regions": _average([
            _safe_number(metrics.get("capital_isolated_regions", 0.0))
            for metrics in large_state_rows
        ]),
        "large_state_average_capital_connectivity_penalty": _average([
            _safe_number(metrics.get("capital_connectivity_penalty", 0.0))
            for metrics in large_state_rows
        ]),
        "large_state_dual_track_loss_rate": _ratio(
            sum(
                1
                for metrics in large_state_rows
                if not bool(metrics.get("dual_track_qualified", False))
            ),
            len(large_state_rows),
        ),
        "average_manpower_ratio": _average([
            ratio
            for ratio in manpower_ratios
            if ratio is not None
        ]),
        "high_shock_samples": len(high_shock_rows),
        "high_shock_average_food_deficit": _average([
            _safe_number(metrics.get("food_deficit", 0.0))
            for metrics in high_shock_rows
        ]),
        "high_shock_average_migration_outflow": _average([
            _safe_number(metrics.get("migration_outflow", 0.0))
            + _safe_number(metrics.get("refugee_outflow", 0.0))
            for metrics in high_shock_rows
        ]),
        "high_shock_average_net_income": _average([
            _safe_number(metrics.get("net_income", 0.0))
            for metrics in high_shock_rows
        ]),
        "trade_pressure_samples": len(trade_pressure_rows),
        "trade_pressure_average_net_income": _average([
            _safe_number(metrics.get("net_income", 0.0))
            for metrics in trade_pressure_rows
        ]),
        "capital_pressure_samples": len(capital_pressure_rows),
        "capital_pressure_average_admin_efficiency": _average([
            _safe_number(metrics.get("administrative_efficiency", 1.0))
            for metrics in capital_pressure_rows
        ]),
        "capital_pressure_average_overextension": _average([
            _safe_number(metrics.get("administrative_overextension", 0.0))
            for metrics in capital_pressure_rows
        ]),
        "capital_pressure_average_net_income": _average([
            _safe_number(metrics.get("net_income", 0.0))
            for metrics in capital_pressure_rows
        ]),
        "average_bloc_bias_abs": _average(bloc_biases),
        "correlations": {
            "regions_to_admin_efficiency": _correlation(region_counts, admin_efficiencies),
            "regions_to_overextension": _correlation(region_counts, overextensions),
            "regions_to_capital_isolated_regions": _correlation(
                region_counts,
                capital_isolated_regions,
            ),
            "regions_to_capital_fragment_count": _correlation(
                region_counts,
                capital_fragment_counts,
            ),
            "regions_to_capital_connectivity_penalty": _correlation(
                region_counts,
                capital_connectivity_penalties,
            ),
            "regions_to_admin_reach": _correlation(region_counts, admin_reaches),
            "regions_to_elite_unrest": _correlation(region_counts, elite_unrest),
            "capital_penalty_to_admin_efficiency": _correlation(
                capital_connectivity_penalties,
                admin_efficiencies,
            ),
            "capital_penalty_to_overextension": _correlation(
                capital_connectivity_penalties,
                overextensions,
            ),
            "capital_penalty_to_net_income": _correlation(
                capital_connectivity_penalties,
                net_incomes,
            ),
            "capital_isolation_to_admin_efficiency": _correlation(
                capital_isolated_regions,
                admin_efficiencies,
            ),
            "attacks_to_manpower_ratio": _correlation(attacks, manpower_ratios),
            "attacks_to_readiness": _correlation(attacks, readiness),
            "attacks_to_military_upkeep": _correlation(attacks, upkeep),
            "shock_to_food_deficit": _correlation(shock_exposures, food_deficits),
            "shock_to_migration_outflow": _correlation(shock_exposures, migration_outflows),
            "shock_to_net_income": _correlation(shock_exposures, net_incomes),
            "shock_to_development_choice": _correlation(shock_exposures, developments),
            "trade_pressure_to_net_income": _correlation(trade_pressures, net_incomes),
            "bloc_bias_to_military_action": _correlation(
                bloc_biases,
                [
                    _safe_number(metrics.get("attacks", 0.0))
                    + _safe_number(metrics.get("expansions", 0.0))
                    for metrics in rows
                ],
            ),
        },
    }


def _normalize_action_name(action_name):
    return "develop" if action_name == "invest" else action_name


def _new_action_phase_bucket():
    return {
        "faction_turns": 0,
        "dual_track_qualified_turns": 0,
        "selected_action_counts": Counter(),
        "skipped_turns": 0,
        "best_utility_samples": 0,
        "best_utility_selected": 0,
        "utility_gap_samples": [],
        "utilities": {
            "attack": [],
            "expand": [],
            "explore": [],
            "develop": [],
        },
        "attack_scores": [],
        "attack_success_chances": [],
        "attack_active_war_bonuses": [],
        "attack_supply_risks": [],
        "attack_manpower_commitments": [],
        "attack_readiness": [],
        "attack_resource_need_bonuses": [],
        "attack_trade_chokepoint_bonuses": [],
        "attack_foreign_gateway_bonuses": [],
        "attack_diplomacy_statuses": Counter(),
        "expand_scores": [],
        "explore_scores": [],
        "explore_revealed_counts": [],
        "frontier_pressures": [],
        "develop_scores": [],
        "acute_development_needs": [],
        "food_shortages": [],
        "mobility_shortages": [],
        "metal_shortages": [],
        "admin_agendas": Counter(),
        "bloc_biases": {
            "attack": [],
            "expand": [],
            "develop": [],
        },
        "bloc_abs_biases": [],
    }


def _summarize_action_phase_bucket(bucket):
    faction_turns = bucket["faction_turns"]
    selected_total = sum(bucket["selected_action_counts"].values())
    return {
        "faction_turns": faction_turns,
        "dual_track_qualified_rate": _ratio(
            bucket["dual_track_qualified_turns"],
            faction_turns,
        ),
        "selected_action_counts": dict(bucket["selected_action_counts"]),
        "selected_attack_rate": _ratio(
            bucket["selected_action_counts"].get("attack", 0),
            selected_total,
        ),
        "selected_expand_rate": _ratio(
            bucket["selected_action_counts"].get("expand", 0),
            selected_total,
        ),
        "selected_explore_rate": _ratio(
            bucket["selected_action_counts"].get("explore", 0),
            selected_total,
        ),
        "selected_develop_rate": _ratio(
            bucket["selected_action_counts"].get("develop", 0),
            selected_total,
        ),
        "skip_rate": _ratio(bucket["skipped_turns"], faction_turns),
        "best_utility_selection_rate": _ratio(
            bucket["best_utility_selected"],
            bucket["best_utility_samples"],
        ),
        "average_utility_gap": _average(bucket["utility_gap_samples"]),
        "average_utilities": {
            action_name: _average(values)
            for action_name, values in bucket["utilities"].items()
        },
        "attack_candidate": {
            "samples": len(bucket["attack_scores"]),
            "average_score": _average(bucket["attack_scores"]),
            "average_success_chance": _average(bucket["attack_success_chances"]),
            "average_active_war_bonus": _average(bucket["attack_active_war_bonuses"]),
            "average_supply_risk": _average(bucket["attack_supply_risks"]),
            "average_manpower_commitment": _average(bucket["attack_manpower_commitments"]),
            "average_readiness": _average(bucket["attack_readiness"]),
            "average_resource_need_bonus": _average(
                bucket["attack_resource_need_bonuses"]
            ),
            "average_trade_chokepoint_bonus": _average(
                bucket["attack_trade_chokepoint_bonuses"]
            ),
            "average_foreign_gateway_bonus": _average(
                bucket["attack_foreign_gateway_bonuses"]
            ),
            "diplomacy_status_counts": dict(bucket["attack_diplomacy_statuses"]),
        },
        "expand_candidate": {
            "samples": len(bucket["expand_scores"]),
            "average_score": _average(bucket["expand_scores"]),
            "average_frontier_pressure": _average(bucket["frontier_pressures"]),
        },
        "explore_candidate": {
            "samples": len(bucket["explore_scores"]),
            "average_score": _average(bucket["explore_scores"]),
            "average_revealed_regions": _average(bucket["explore_revealed_counts"]),
        },
        "develop_candidate": {
            "samples": len(bucket["develop_scores"]),
            "average_score": _average(bucket["develop_scores"]),
            "average_acute_development_need": _average(
                bucket["acute_development_needs"]
            ),
            "average_food_shortage": _average(bucket["food_shortages"]),
            "average_mobility_shortage": _average(bucket["mobility_shortages"]),
            "average_metal_shortage": _average(bucket["metal_shortages"]),
            "admin_agenda_counts": dict(bucket["admin_agendas"]),
        },
        "bloc_bias": {
            "average_attack_bias": _average(bucket["bloc_biases"]["attack"]),
            "average_expand_bias": _average(bucket["bloc_biases"]["expand"]),
            "average_develop_bias": _average(bucket["bloc_biases"]["develop"]),
            "average_abs_bias": _average(bucket["bloc_abs_biases"]),
        },
    }


def build_action_incentive_diagnostics(action_diagnostics):
    if not action_diagnostics:
        empty_bucket = _new_action_phase_bucket()
        return {
            "total_faction_turns": 0,
            "dual_track_qualified_rate": 0.0,
            "selected_action_counts": {},
            "phase_summary": {},
            **_summarize_action_phase_bucket(empty_bucket),
        }

    horizon = max(int(record.get("turn", 0) or 0) for record in action_diagnostics)
    phase_ranges = get_phase_ranges(max(1, horizon))
    phase_buckets = {
        phase_name: _new_action_phase_bucket()
        for phase_name, _start_turn, _end_turn in phase_ranges
    }
    overall_bucket = _new_action_phase_bucket()

    for record in action_diagnostics:
        phase_name = _phase_for_turn(int(record.get("turn", 0) or 0), phase_ranges)
        for bucket in (overall_bucket, phase_buckets[phase_name]):
            bucket["faction_turns"] += 1
            if record.get("dual_track_qualified", False):
                bucket["dual_track_qualified_turns"] += 1

            selected_actions = [
                _normalize_action_name(selected.get("action"))
                for selected in record.get("selected_actions", [])
                if selected.get("action")
            ]
            if not selected_actions:
                bucket["skipped_turns"] += 1
            for action_name in selected_actions:
                bucket["selected_action_counts"][action_name] += 1

            utilities = {
                _normalize_action_name(action_name): _safe_number(value)
                for action_name, value in record.get("utilities", {}).items()
            }
            for action_name in ("attack", "expand", "explore", "develop"):
                if action_name in utilities:
                    bucket["utilities"][action_name].append(utilities[action_name])
            if utilities:
                best_action = max(
                    utilities,
                    key=lambda action_name: (utilities[action_name], action_name),
                )
                bucket["best_utility_samples"] += 1
                if best_action in selected_actions:
                    bucket["best_utility_selected"] += 1
                if selected_actions:
                    selected_utility = max(
                        utilities.get(action_name, 0.0)
                        for action_name in selected_actions
                    )
                    bucket["utility_gap_samples"].append(
                        max(0.0, utilities[best_action] - selected_utility)
                    )

            components = record.get("components", {})
            targets = record.get("targets", {})
            attack = components.get("attack") or {}
            if targets.get("attack"):
                bucket["attack_scores"].append(_safe_number(attack.get("score", 0.0)))
                bucket["attack_success_chances"].append(
                    _safe_number(attack.get("success_chance", 0.0))
                )
                bucket["attack_active_war_bonuses"].append(
                    _safe_number(attack.get("active_war_bonus", 0.0))
                )
                bucket["attack_supply_risks"].append(
                    _safe_number(attack.get("supply_risk", 0.0))
                )
                bucket["attack_manpower_commitments"].append(
                    _safe_number(attack.get("manpower_commitment", 0.0))
                )
                bucket["attack_readiness"].append(
                    _safe_number(attack.get("attacker_readiness", 0.0))
                )
                bucket["attack_resource_need_bonuses"].append(
                    _safe_number(attack.get("resource_need_bonus", 0.0))
                )
                bucket["attack_trade_chokepoint_bonuses"].append(
                    _safe_number(attack.get("trade_chokepoint_bonus", 0.0))
                )
                bucket["attack_foreign_gateway_bonuses"].append(
                    _safe_number(attack.get("foreign_gateway_bonus", 0.0))
                )
                diplomacy_status = str(attack.get("diplomacy_status", "") or "none")
                bucket["attack_diplomacy_statuses"][diplomacy_status] += 1

            expand = components.get("expand") or {}
            if targets.get("expand"):
                bucket["expand_scores"].append(_safe_number(expand.get("score", 0.0)))
                bucket["frontier_pressures"].append(
                    _safe_number(
                        record.get("pressures", {}).get("frontier_pressure", 0.0)
                    )
                )

            explore = components.get("explore") or {}
            if targets.get("explore"):
                bucket["explore_scores"].append(_safe_number(explore.get("score", 0.0)))
                bucket["explore_revealed_counts"].append(
                    _safe_number(explore.get("revealed_region_count", 0.0))
                )

            develop = components.get("develop") or {}
            if targets.get("develop"):
                bucket["develop_scores"].append(
                    _safe_number(develop.get("score", 0.0))
                )
                bucket["acute_development_needs"].append(
                    _safe_number(
                        record.get("pressures", {}).get("acute_development_need", 0.0)
                    )
                )
                shortages = record.get("resource_shortages", {})
                bucket["food_shortages"].append(
                    _safe_number(shortages.get("food_security", 0.0))
                )
                bucket["mobility_shortages"].append(
                    _safe_number(shortages.get("mobility_capacity", 0.0))
                )
                bucket["metal_shortages"].append(
                    _safe_number(shortages.get("metal_capacity", 0.0))
                )
                agenda = record.get("dominant_admin_agenda") or "none"
                bucket["admin_agendas"][agenda] += 1

            bloc_biases = record.get("bloc_biases", {})
            abs_biases = []
            for action_name in ("attack", "expand", "develop"):
                bias = _safe_number(bloc_biases.get(action_name, 0.0))
                bucket["bloc_biases"][action_name].append(bias)
                abs_biases.append(abs(bias))
            bucket["bloc_abs_biases"].append(max(abs_biases) if abs_biases else 0.0)

    summary = _summarize_action_phase_bucket(overall_bucket)
    summary["total_faction_turns"] = overall_bucket["faction_turns"]
    summary["phase_summary"] = {
        phase_name: _summarize_action_phase_bucket(bucket)
        for phase_name, bucket in phase_buckets.items()
    }
    return summary


def build_pressure_diagnostics(world, competition=None, action_diagnostics=None):
    if competition is None:
        competition = analyze_competition_metrics(world)

    return {
        "runaway": build_runaway_context(world, competition=competition),
        "relationship_pressure": build_relationship_pressure(world),
        "late_war_cadence": build_late_war_cadence(world),
        "shock_volume": build_shock_volume_diagnostics(world),
        "pressure_propagation": build_pressure_propagation_checks(world),
        "action_incentives": build_action_incentive_diagnostics(
            action_diagnostics or []
        ),
    }


def _nested_numeric_values(run_diagnostics, path):
    values = []
    for diagnostics in run_diagnostics:
        current = diagnostics
        for key in path:
            current = current.get(key, {}) if isinstance(current, dict) else {}
        if isinstance(current, (int, float)):
            values.append(float(current))
    return values


def _average_nested(run_diagnostics, path):
    return _average(_nested_numeric_values(run_diagnostics, path))


def _aggregate_phase_metrics(run_diagnostics, path):
    phase_names = []
    for diagnostics in run_diagnostics:
        current = diagnostics
        for key in path:
            current = current.get(key, {}) if isinstance(current, dict) else {}
        for phase_name in current:
            if phase_name not in phase_names:
                phase_names.append(phase_name)

    aggregate = {}
    for phase_name in phase_names:
        phase_runs = []
        for diagnostics in run_diagnostics:
            current = diagnostics
            for key in path:
                current = current.get(key, {}) if isinstance(current, dict) else {}
            if phase_name in current:
                phase_runs.append(current[phase_name])
        metric_names = sorted({
            metric_name
            for phase_run in phase_runs
            for metric_name, value in phase_run.items()
            if isinstance(value, (int, float))
        })
        aggregate[phase_name] = {
            metric_name: _average([
                float(phase_run.get(metric_name, 0.0))
                for phase_run in phase_runs
                if isinstance(phase_run.get(metric_name, 0.0), (int, float))
            ])
            for metric_name in metric_names
        }
    return aggregate


def _aggregate_selected_action_counts(run_diagnostics):
    counts = Counter()
    for diagnostics in run_diagnostics:
        counts.update(
            diagnostics.get("action_incentives", {}).get("selected_action_counts", {})
        )
    return dict(counts)


def _aggregate_counter_path(run_diagnostics, path):
    counter = Counter()
    for diagnostics in run_diagnostics:
        current = diagnostics
        for key in path:
            current = current.get(key, {}) if isinstance(current, dict) else {}
        if isinstance(current, dict):
            counter.update(current)
    return dict(counter)


def summarize_pressure_diagnostics(run_diagnostics):
    if not run_diagnostics:
        return {
            "run_count": 0,
            "runaway": {},
            "relationship_pressure": {},
            "late_war_cadence": {},
            "shock_volume": {},
            "pressure_propagation": {},
            "action_incentives": {},
        }

    runaway_winners = Counter(
        diagnostics.get("runaway", {}).get("winner")
        for diagnostics in run_diagnostics
        if diagnostics.get("runaway", {}).get("winner") is not None
    )
    runaway_start_turns = [
        diagnostics.get("runaway", {}).get("start_turn")
        for diagnostics in run_diagnostics
        if diagnostics.get("runaway", {}).get("start_turn") is not None
    ]

    return {
        "run_count": len(run_diagnostics),
        "runaway": {
            "detected_rate": _average([
                1.0 if diagnostics.get("runaway", {}).get("detected", False) else 0.0
                for diagnostics in run_diagnostics
            ]),
            "average_start_turn": _average(runaway_start_turns),
            "winner_counts": dict(runaway_winners),
            "average_treasury_margin": _average_nested(
                run_diagnostics,
                ("runaway", "average_treasury_margin"),
            ),
            "average_region_margin": _average_nested(
                run_diagnostics,
                ("runaway", "average_region_margin"),
            ),
            "average_force_projection_margin": _average_nested(
                run_diagnostics,
                ("runaway", "average_force_projection_margin"),
            ),
            "average_net_income_margin": _average_nested(
                run_diagnostics,
                ("runaway", "average_net_income_margin"),
            ),
            "average_admin_efficiency_margin": _average_nested(
                run_diagnostics,
                ("runaway", "average_admin_efficiency_margin"),
            ),
            "average_winner_capital_isolated_regions": _average_nested(
                run_diagnostics,
                ("runaway", "average_winner_capital_isolated_regions"),
            ),
            "average_winner_capital_fragment_count": _average_nested(
                run_diagnostics,
                ("runaway", "average_winner_capital_fragment_count"),
            ),
            "average_winner_capital_connectivity_penalty": _average_nested(
                run_diagnostics,
                ("runaway", "average_winner_capital_connectivity_penalty"),
            ),
            "average_capital_isolated_region_gap": _average_nested(
                run_diagnostics,
                ("runaway", "average_capital_isolated_region_gap"),
            ),
            "average_capital_fragment_gap": _average_nested(
                run_diagnostics,
                ("runaway", "average_capital_fragment_gap"),
            ),
            "average_capital_connectivity_penalty_gap": _average_nested(
                run_diagnostics,
                ("runaway", "average_capital_connectivity_penalty_gap"),
            ),
            "average_shock_exposure_gap": _average_nested(
                run_diagnostics,
                ("runaway", "average_shock_exposure_gap"),
            ),
            "average_shock_resilience_margin": _average_nested(
                run_diagnostics,
                ("runaway", "average_shock_resilience_margin"),
            ),
            "average_technology_margin": _average_nested(
                run_diagnostics,
                ("runaway", "average_technology_margin"),
            ),
            "dominant_advantage_counts": _aggregate_counter_path(
                run_diagnostics,
                ("runaway", "dominant_advantage_counts"),
            ),
        },
        "relationship_pressure": {
            "average_active_war_count": _average_nested(
                run_diagnostics,
                ("relationship_pressure", "active_war_count"),
            ),
            "average_rivalry_count": _average_nested(
                run_diagnostics,
                ("relationship_pressure", "rivalry_count"),
            ),
            "average_pact_alliance_count": _average_nested(
                run_diagnostics,
                ("relationship_pressure", "pact_alliance_count"),
            ),
            "average_tributary_pressure_count": _average_nested(
                run_diagnostics,
                ("relationship_pressure", "tributary_pressure_count"),
            ),
            "average_active_war_exhaustion": _average_nested(
                run_diagnostics,
                ("relationship_pressure", "average_active_war_exhaustion"),
            ),
        },
        "late_war_cadence": _aggregate_phase_metrics(
            run_diagnostics,
            ("late_war_cadence",),
        ),
        "shock_volume": {
            "average_shock_event_count": _average_nested(
                run_diagnostics,
                ("shock_volume", "shock_event_count"),
            ),
            "average_onset_event_count": _average_nested(
                run_diagnostics,
                ("shock_volume", "onset_event_count"),
            ),
            "average_recovery_event_count": _average_nested(
                run_diagnostics,
                ("shock_volume", "recovery_event_count"),
            ),
            "average_population_loss_event_count": _average_nested(
                run_diagnostics,
                ("shock_volume", "population_loss_event_count"),
            ),
            "average_total_population_loss": _average_nested(
                run_diagnostics,
                ("shock_volume", "total_population_loss"),
            ),
            "average_unique_shock_count": _average_nested(
                run_diagnostics,
                ("shock_volume", "unique_shock_count"),
            ),
            "average_faction_shock_exposure": _average_nested(
                run_diagnostics,
                ("shock_volume", "average_faction_shock_exposure"),
            ),
            "peak_faction_shock_exposure": max(
                _nested_numeric_values(
                    run_diagnostics,
                    ("shock_volume", "peak_faction_shock_exposure"),
                )
                or [0.0]
            ),
            "average_faction_shock_resilience": _average_nested(
                run_diagnostics,
                ("shock_volume", "average_faction_shock_resilience"),
            ),
            "active_famine_epidemic_trade_turn_rate": _average_nested(
                run_diagnostics,
                ("shock_volume", "active_famine_epidemic_trade_turn_rate"),
            ),
            "event_type_counts": _aggregate_counter_path(
                run_diagnostics,
                ("shock_volume", "event_type_counts"),
            ),
            "shock_count_by_kind": _aggregate_counter_path(
                run_diagnostics,
                ("shock_volume", "shock_count_by_kind"),
            ),
        },
        "pressure_propagation": {
            "average_large_state_admin_efficiency": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "large_state_average_admin_efficiency"),
            ),
            "average_large_state_overextension": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "large_state_average_overextension"),
            ),
            "average_large_state_capital_isolated_regions": _average_nested(
                run_diagnostics,
                (
                    "pressure_propagation",
                    "large_state_average_capital_isolated_regions",
                ),
            ),
            "average_large_state_capital_connectivity_penalty": _average_nested(
                run_diagnostics,
                (
                    "pressure_propagation",
                    "large_state_average_capital_connectivity_penalty",
                ),
            ),
            "average_large_state_dual_track_loss_rate": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "large_state_dual_track_loss_rate"),
            ),
            "average_manpower_ratio": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "average_manpower_ratio"),
            ),
            "average_high_shock_food_deficit": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "high_shock_average_food_deficit"),
            ),
            "average_high_shock_migration_outflow": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "high_shock_average_migration_outflow"),
            ),
            "average_high_shock_net_income": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "high_shock_average_net_income"),
            ),
            "average_trade_pressure_net_income": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "trade_pressure_average_net_income"),
            ),
            "average_capital_pressure_admin_efficiency": _average_nested(
                run_diagnostics,
                (
                    "pressure_propagation",
                    "capital_pressure_average_admin_efficiency",
                ),
            ),
            "average_capital_pressure_overextension": _average_nested(
                run_diagnostics,
                (
                    "pressure_propagation",
                    "capital_pressure_average_overextension",
                ),
            ),
            "average_capital_pressure_net_income": _average_nested(
                run_diagnostics,
                (
                    "pressure_propagation",
                    "capital_pressure_average_net_income",
                ),
            ),
            "average_bloc_bias_abs": _average_nested(
                run_diagnostics,
                ("pressure_propagation", "average_bloc_bias_abs"),
            ),
            "correlations": {
                "regions_to_admin_efficiency": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "regions_to_admin_efficiency",
                    ),
                ),
                "regions_to_overextension": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "regions_to_overextension",
                    ),
                ),
                "regions_to_capital_connectivity_penalty": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "regions_to_capital_connectivity_penalty",
                    ),
                ),
                "capital_penalty_to_admin_efficiency": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "capital_penalty_to_admin_efficiency",
                    ),
                ),
                "capital_penalty_to_overextension": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "capital_penalty_to_overextension",
                    ),
                ),
                "capital_penalty_to_net_income": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "capital_penalty_to_net_income",
                    ),
                ),
                "attacks_to_manpower_ratio": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "attacks_to_manpower_ratio",
                    ),
                ),
                "shock_to_food_deficit": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "shock_to_food_deficit",
                    ),
                ),
                "shock_to_net_income": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "shock_to_net_income",
                    ),
                ),
                "trade_pressure_to_net_income": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "trade_pressure_to_net_income",
                    ),
                ),
                "bloc_bias_to_military_action": _average_nested(
                    run_diagnostics,
                    (
                        "pressure_propagation",
                        "correlations",
                        "bloc_bias_to_military_action",
                    ),
                ),
            },
        },
        "action_incentives": {
            "average_total_faction_turns": _average_nested(
                run_diagnostics,
                ("action_incentives", "total_faction_turns"),
            ),
            "dual_track_qualified_rate": _average_nested(
                run_diagnostics,
                ("action_incentives", "dual_track_qualified_rate"),
            ),
            "selected_action_counts": _aggregate_selected_action_counts(run_diagnostics),
            "best_utility_selection_rate": _average_nested(
                run_diagnostics,
                ("action_incentives", "best_utility_selection_rate"),
            ),
            "average_utility_gap": _average_nested(
                run_diagnostics,
                ("action_incentives", "average_utility_gap"),
            ),
            "average_attack_utility": _average_nested(
                run_diagnostics,
                ("action_incentives", "average_utilities", "attack"),
            ),
            "average_expand_utility": _average_nested(
                run_diagnostics,
                ("action_incentives", "average_utilities", "expand"),
            ),
            "average_explore_utility": _average_nested(
                run_diagnostics,
                ("action_incentives", "average_utilities", "explore"),
            ),
            "average_develop_utility": _average_nested(
                run_diagnostics,
                ("action_incentives", "average_utilities", "develop"),
            ),
            "attack_candidate": {
                "average_score": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "attack_candidate", "average_score"),
                ),
                "average_success_chance": _average_nested(
                    run_diagnostics,
                    (
                        "action_incentives",
                        "attack_candidate",
                        "average_success_chance",
                    ),
                ),
                "average_active_war_bonus": _average_nested(
                    run_diagnostics,
                    (
                        "action_incentives",
                        "attack_candidate",
                        "average_active_war_bonus",
                    ),
                ),
                "average_supply_risk": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "attack_candidate", "average_supply_risk"),
                ),
                "average_manpower_commitment": _average_nested(
                    run_diagnostics,
                    (
                        "action_incentives",
                        "attack_candidate",
                        "average_manpower_commitment",
                    ),
                ),
                "average_readiness": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "attack_candidate", "average_readiness"),
                ),
            },
            "expand_candidate": {
                "average_score": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "expand_candidate", "average_score"),
                ),
                "average_frontier_pressure": _average_nested(
                    run_diagnostics,
                    (
                        "action_incentives",
                        "expand_candidate",
                        "average_frontier_pressure",
                    ),
                ),
            },
            "explore_candidate": {
                "average_score": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "explore_candidate", "average_score"),
                ),
                "average_revealed_regions": _average_nested(
                    run_diagnostics,
                    (
                        "action_incentives",
                        "explore_candidate",
                        "average_revealed_regions",
                    ),
                ),
            },
            "develop_candidate": {
                "average_score": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "develop_candidate", "average_score"),
                ),
                "average_acute_development_need": _average_nested(
                    run_diagnostics,
                    (
                        "action_incentives",
                        "develop_candidate",
                        "average_acute_development_need",
                    ),
                ),
                "average_food_shortage": _average_nested(
                    run_diagnostics,
                    (
                        "action_incentives",
                        "develop_candidate",
                        "average_food_shortage",
                    ),
                ),
            },
            "bloc_bias": {
                "average_attack_bias": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "bloc_bias", "average_attack_bias"),
                ),
                "average_expand_bias": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "bloc_bias", "average_expand_bias"),
                ),
                "average_develop_bias": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "bloc_bias", "average_develop_bias"),
                ),
                "average_abs_bias": _average_nested(
                    run_diagnostics,
                    ("action_incentives", "bloc_bias", "average_abs_bias"),
                ),
            },
        },
    }


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
    dual_track_totals = {
        "qualifying_turns": 0,
        "both_track_turns": 0,
        "bloc_competition_delta_sum": 0.0,
        "bloc_competition_delta_samples": 0,
        "military_action_count": 0,
        "military_dominant_action_count": 0,
        "track_split_by_faction_size": {
            bucket: {
                "samples": 0,
                "military_track_rate_numerator": 0.0,
                "admin_track_rate_numerator": 0.0,
            }
            for bucket in ("1-3", "4-7", "8+")
        },
    }
    pressure_diagnostic_runs = []

    for _ in range(runs):
        world = create_world(
            map_name=map_name,
            num_factions=num_factions,
        )
        action_diagnostics = []
        world = run_simulation(
            world,
            num_turns=num_turns,
            verbose=False,
            action_diagnostics_callback=action_diagnostics.append,
        )
        final_regions = count_owned_regions(world)
        competition = analyze_competition_metrics(world)
        phase_counts = build_phase_action_counts(world)
        run_system_activity = build_system_activity(world)
        run_dual_track = build_dual_track_observability(world)
        run_pressure_diagnostics = build_pressure_diagnostics(
            world,
            competition=competition,
            action_diagnostics=action_diagnostics,
        )
        pressure_diagnostic_runs.append(run_pressure_diagnostics)

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

        dual_track_totals["qualifying_turns"] += run_dual_track["qualifying_turns"]
        dual_track_totals["both_track_turns"] += run_dual_track["both_track_turns"]
        dual_track_totals["bloc_competition_delta_sum"] += run_dual_track["bloc_competition_delta_sum"]
        dual_track_totals["bloc_competition_delta_samples"] += run_dual_track["bloc_competition_delta_samples"]
        dual_track_totals["military_action_count"] += run_dual_track["military_action_count"]
        dual_track_totals["military_dominant_action_count"] += run_dual_track["military_dominant_action_count"]
        for bucket, values in run_dual_track["track_split_by_faction_size"].items():
            target = dual_track_totals["track_split_by_faction_size"][bucket]
            samples = values["samples"]
            target["samples"] += samples
            target["military_track_rate_numerator"] += values["military_track_rate"] * samples
            target["admin_track_rate_numerator"] += values["admin_track_rate"] * samples

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
    track_split_summary = {}
    for bucket, values in dual_track_totals["track_split_by_faction_size"].items():
        samples = values["samples"]
        track_split_summary[bucket] = {
            "samples": samples,
            "military_track_rate": (
                values["military_track_rate_numerator"] / samples
                if samples
                else 0.0
            ),
            "admin_track_rate": (
                values["admin_track_rate_numerator"] / samples
                if samples
                else 0.0
            ),
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
        "dual_track_actions": {
            "qualifying_turns": dual_track_totals["qualifying_turns"],
            "both_track_turns": dual_track_totals["both_track_turns"],
            "dual_track_activation_rate": (
                dual_track_totals["both_track_turns"]
                / dual_track_totals["qualifying_turns"]
                if dual_track_totals["qualifying_turns"]
                else 0.0
            ),
            "bloc_competition_delta": (
                dual_track_totals["bloc_competition_delta_sum"]
                / dual_track_totals["bloc_competition_delta_samples"]
                if dual_track_totals["bloc_competition_delta_samples"]
                else 0.0
            ),
            "military_action_count": dual_track_totals["military_action_count"],
            "military_dominant_action_count": dual_track_totals["military_dominant_action_count"],
            "dominant_bloc_action_alignment": (
                dual_track_totals["military_dominant_action_count"]
                / dual_track_totals["military_action_count"]
                if dual_track_totals["military_action_count"]
                else 0.0
            ),
            "track_split_by_faction_size": track_split_summary,
        },
        "pressure_diagnostics": summarize_pressure_diagnostics(pressure_diagnostic_runs),
    }


def format_setting_report(result):
    lines = []
    outcome = result["outcome_balance"]
    health = result["game_health"]
    survival = result["survival"]
    pacing = result["pacing"]
    diplomacy = result["diplomacy"]
    system_activity = result["system_activity"]
    dual_track = result.get("dual_track_actions", {})
    pressure = result.get("pressure_diagnostics", {})

    lines.append(f"Map: {result['map_name']}")
    lines.append(f"Turns: {result['num_turns']}")
    lines.append(f"Simulations: {result['runs']}")
    lines.append("Decision Model: dual-track actions + bloc competition")
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

    runaway_pressure = pressure.get("runaway", {})
    relationship_pressure = pressure.get("relationship_pressure", {})
    late_phase_summaries = pressure.get("late_war_cadence", {})
    late_war = late_phase_summaries.get("late", {})
    if not late_war and late_phase_summaries:
        late_war = list(late_phase_summaries.values())[-1]
    shock_volume = pressure.get("shock_volume", {})
    propagation = pressure.get("pressure_propagation", {})
    action_incentives = pressure.get("action_incentives", {})
    selected_action_counts = action_incentives.get("selected_action_counts", {})
    selected_actions_total = sum(selected_action_counts.values())
    attack_candidate = action_incentives.get("attack_candidate", {})
    expand_candidate = action_incentives.get("expand_candidate", {})
    explore_candidate = action_incentives.get("explore_candidate", {})
    develop_candidate = action_incentives.get("develop_candidate", {})
    bloc_bias = action_incentives.get("bloc_bias", {})
    correlations = propagation.get("correlations", {})

    lines.append("")
    lines.append("Pressure Diagnostics")
    lines.append(
        f"  Runaway margins: treasury {runaway_pressure.get('average_treasury_margin', 0.0):.2f} | "
        f"regions {runaway_pressure.get('average_region_margin', 0.0):.2f} | "
        f"force projection {runaway_pressure.get('average_force_projection_margin', 0.0):.2f} | "
        f"net income {runaway_pressure.get('average_net_income_margin', 0.0):.2f}"
    )
    lines.append(
        f"  Durable pressure: admin eff margin "
        f"{runaway_pressure.get('average_admin_efficiency_margin', 0.0):.3f} | "
        f"shock exposure gap {runaway_pressure.get('average_shock_exposure_gap', 0.0):.3f} | "
        f"shock resilience margin {runaway_pressure.get('average_shock_resilience_margin', 0.0):.3f} | "
        f"technology margin {runaway_pressure.get('average_technology_margin', 0.0):.3f}"
    )
    lines.append(
        f"  Capital fracture: winner isolated "
        f"{runaway_pressure.get('average_winner_capital_isolated_regions', 0.0):.2f} | "
        f"winner fragments {runaway_pressure.get('average_winner_capital_fragment_count', 0.0):.2f} | "
        f"winner penalty {runaway_pressure.get('average_winner_capital_connectivity_penalty', 0.0):.3f} | "
        f"penalty gap {runaway_pressure.get('average_capital_connectivity_penalty_gap', 0.0):.3f}"
    )
    lines.append(
        f"  Diplomacy pressure: active wars "
        f"{relationship_pressure.get('average_active_war_count', 0.0):.2f} | "
        f"rivalries {relationship_pressure.get('average_rivalry_count', 0.0):.2f} | "
        f"pacts/alliances {relationship_pressure.get('average_pact_alliance_count', 0.0):.2f} | "
        f"tributary pressure {relationship_pressure.get('average_tributary_pressure_count', 0.0):.2f}"
    )
    lines.append(
        f"  Late war: attacks {late_war.get('attacks', 0.0):.2f} | "
        f"active-war rate {late_war.get('active_war_attack_rate', 0.0):.2%} | "
        f"rival rate {late_war.get('rival_attack_rate', 0.0):.2%} | "
        f"low-score rate {late_war.get('low_score_attack_rate', 0.0):.2%} | "
        f"repeat rate {late_war.get('repeated_same_pair_attack_rate', 0.0):.2%}"
    )
    lines.append(
        f"  Shock volume: events {shock_volume.get('average_shock_event_count', 0.0):.2f} | "
        f"onsets {shock_volume.get('average_onset_event_count', 0.0):.2f} | "
        f"recoveries {shock_volume.get('average_recovery_event_count', 0.0):.2f} | "
        f"population-loss events {shock_volume.get('average_population_loss_event_count', 0.0):.2f} | "
        f"avg exposure {shock_volume.get('average_faction_shock_exposure', 0.0):.3f}"
    )
    lines.append(
        f"  Pressure bite: large-state admin eff "
        f"{propagation.get('average_large_state_admin_efficiency', 0.0):.3f} | "
        f"overextension {propagation.get('average_large_state_overextension', 0.0):.3f} | "
        f"capital penalty {propagation.get('average_large_state_capital_connectivity_penalty', 0.0):.3f} | "
        f"dual-track loss {propagation.get('average_large_state_dual_track_loss_rate', 0.0):.2%} | "
        f"manpower ratio {propagation.get('average_manpower_ratio', 0.0):.2%} | "
        f"high-shock net {propagation.get('average_high_shock_net_income', 0.0):.2f}"
    )
    lines.append(
        f"  Capital bite: admin eff "
        f"{propagation.get('average_capital_pressure_admin_efficiency', 0.0):.3f} | "
        f"overextension {propagation.get('average_capital_pressure_overextension', 0.0):.3f} | "
        f"net income {propagation.get('average_capital_pressure_net_income', 0.0):.2f}"
    )
    lines.append(
        f"  Pressure correlations: regions->admin "
        f"{correlations.get('regions_to_admin_efficiency', 0.0):.2f} | "
        f"regions->overextension {correlations.get('regions_to_overextension', 0.0):.2f} | "
        f"regions->capital penalty {correlations.get('regions_to_capital_connectivity_penalty', 0.0):.2f} | "
        f"capital penalty->admin {correlations.get('capital_penalty_to_admin_efficiency', 0.0):.2f} | "
        f"shock->food deficit {correlations.get('shock_to_food_deficit', 0.0):.2f} | "
        f"trade pressure->net income {correlations.get('trade_pressure_to_net_income', 0.0):.2f}"
    )
    lines.append(
        f"  Action incentives: attack "
        f"{_ratio(selected_action_counts.get('attack', 0), selected_actions_total):.2%} | "
        f"expand {_ratio(selected_action_counts.get('expand', 0), selected_actions_total):.2%} | "
        f"explore {_ratio(selected_action_counts.get('explore', 0), selected_actions_total):.2%} | "
        f"develop {_ratio(selected_action_counts.get('develop', 0), selected_actions_total):.2%} | "
        f"best-utility selected {action_incentives.get('best_utility_selection_rate', 0.0):.2%} | "
        f"dual-track qualified {action_incentives.get('dual_track_qualified_rate', 0.0):.2%}"
    )
    lines.append(
        f"  Best candidates: attack score {attack_candidate.get('average_score', 0.0):.2f} "
        f"/ success {attack_candidate.get('average_success_chance', 0.0):.2%} | "
        f"expand score {expand_candidate.get('average_score', 0.0):.2f} "
        f"/ frontier {expand_candidate.get('average_frontier_pressure', 0.0):.3f} | "
        f"explore score {explore_candidate.get('average_score', 0.0):.2f} "
        f"/ revealed {explore_candidate.get('average_revealed_regions', 0.0):.2f} | "
        f"develop score {develop_candidate.get('average_score', 0.0):.2f} "
        f"/ acute need {develop_candidate.get('average_acute_development_need', 0.0):.3f}"
    )
    lines.append(
        f"  Bloc/action bias: abs {bloc_bias.get('average_abs_bias', 0.0):.4f} | "
        f"attack {bloc_bias.get('average_attack_bias', 0.0):.4f} | "
        f"expand {bloc_bias.get('average_expand_bias', 0.0):.4f} | "
        f"develop {bloc_bias.get('average_develop_bias', 0.0):.4f}"
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
    lines.append("Dual-Track Actions")
    lines.append(
        f"  Activation: {dual_track.get('dual_track_activation_rate', 0.0):.2%} "
        f"({int(dual_track.get('both_track_turns', 0))}/"
        f"{int(dual_track.get('qualifying_turns', 0))} qualifying faction-turns)"
    )
    lines.append(
        f"  Avg bloc utility delta: {dual_track.get('bloc_competition_delta', 0.0):.4f} | "
        f"Military-action dominant-bloc alignment: "
        f"{dual_track.get('dominant_bloc_action_alignment', 0.0):.2%}"
    )
    track_split = dual_track.get("track_split_by_faction_size", {})
    if track_split:
        split_parts = []
        for bucket in ("1-3", "4-7", "8+"):
            values = track_split.get(bucket, {})
            split_parts.append(
                f"{bucket}: mil {values.get('military_track_rate', 0.0):.0%}/"
                f"admin {values.get('admin_track_rate', 0.0):.0%}"
            )
        lines.append("  Track split by size: " + " | ".join(split_parts))

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
    lines.append("Decision model: dual-track actions + bloc competition")
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
