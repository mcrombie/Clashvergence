from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS_ROOT = ROOT.parents[1]
WORLD_BUILDER_ROOT = PROGRAMS_ROOT / "typescript" / "world-builder"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.experiment_balance_dashboard import (  # noqa: E402
    SYSTEM_DEFINITIONS,
    build_dual_track_observability,
    build_system_activity,
)
from src.maps import MAPS  # noqa: E402
from src.metrics import analyze_competition_metrics  # noqa: E402
from src.simulation import run_simulation  # noqa: E402
from src.world import create_world  # noqa: E402


DEFAULT_SOURCE_MAP_CANDIDATES = [
    WORLD_BUILDER_ROOT / "saved_maps" / "azhora.azmap",
    WORLD_BUILDER_ROOT / "map" / "resources" / "examples" / "azhora.wwmap",
]
DEFAULT_TRANSLATOR = WORLD_BUILDER_ROOT / "wwmap_to_clashvergence.py"
DEFAULT_GENERATED_MAP = ROOT / "reports" / "calibration" / "azhora.cmap.json"
DEFAULT_OUTPUT = ROOT / "reports" / "azhora_calibration_report.txt"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "azhora_calibration_report.json"

POLITICAL_EVENT_TYPES = {
    "attack",
    "war_declared",
    "war_peace",
    "diplomacy_alliance",
    "diplomacy_break",
    "diplomacy_pact",
    "diplomacy_rivalry",
    "diplomacy_tributary",
    "diplomacy_tributary_break",
    "diplomacy_truce",
    "diplomacy_truce_end",
    "unrest_secession",
    "rebel_independence",
}


def _default_source_map() -> Path | None:
    for candidate in DEFAULT_SOURCE_MAP_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run many seeded Azhora simulations and write a compact calibration report."
        )
    )
    parser.add_argument(
        "--source-map",
        type=Path,
        default=_default_source_map(),
        help=(
            "World Builder .azmap/.wwmap source map. Translated before the runs. "
            "Ignored when --map-file is supplied."
        ),
    )
    parser.add_argument(
        "--map-file",
        type=Path,
        help="Pre-translated Clashvergence .cmap.json map file to run directly.",
    )
    parser.add_argument(
        "--translator",
        type=Path,
        default=DEFAULT_TRANSLATOR,
        help="Path to wwmap_to_clashvergence.py.",
    )
    parser.add_argument(
        "--generated-map",
        type=Path,
        default=DEFAULT_GENERATED_MAP,
        help="Where translated source maps should be written.",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=120,
        help="Turns per simulation run.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=25,
        help="Number of seeded runs.",
    )
    parser.add_argument(
        "--num-factions",
        type=int,
        default=9,
        help="Faction count to request during source-map translation.",
    )
    parser.add_argument(
        "--seed-prefix",
        default="azhora-calibration",
        help="Prefix used to derive per-run seeds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Text report output path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=DEFAULT_JSON_OUTPUT,
        help="Machine-readable summary output path.",
    )
    return parser.parse_args()


def _strip_generated_suffix(path: Path) -> str:
    name = path.name
    for suffix in (".cmap.json", ".cvmap.json", ".json"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _inject_map_file(map_file_path: Path) -> tuple[str, int, dict[str, Any]]:
    map_def = json.loads(map_file_path.read_text(encoding="utf-8"))
    map_name = f"azhora_calibration_{_strip_generated_suffix(map_file_path)}"
    MAPS[map_name] = map_def
    num_factions = int(map_def.get("num_factions", 4))
    return map_name, num_factions, map_def


def _is_generated_map(path: Path) -> bool:
    return path.name.lower().endswith((".cmap.json", ".cvmap.json"))


def _resolve_map_file(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    if args.map_file:
        map_file = args.map_file.resolve()
        if not map_file.exists():
            raise SystemExit(f"Map file not found: {map_file}")
        return map_file, {
            "source_map": None,
            "generated_map": str(map_file),
            "translated": False,
            "translator_stdout": "",
            "translator_stderr": "",
        }

    if args.source_map is None:
        searched = "\n".join(str(path) for path in DEFAULT_SOURCE_MAP_CANDIDATES)
        raise SystemExit(f"No default Azhora source map found. Searched:\n{searched}")

    source_map = args.source_map.resolve()
    if not source_map.exists():
        raise SystemExit(f"Source map not found: {source_map}")

    if _is_generated_map(source_map):
        return source_map, {
            "source_map": str(source_map),
            "generated_map": str(source_map),
            "translated": False,
            "translator_stdout": "",
            "translator_stderr": "",
        }

    translator = args.translator.resolve()
    if not translator.exists():
        raise SystemExit(f"Translator not found: {translator}")

    generated_map = args.generated_map.resolve()
    generated_map.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            str(translator),
            str(source_map),
            str(generated_map),
            str(args.num_factions),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "\n\n".join(
                part
                for part in [
                    "Azhora source-map translation failed.",
                    f"Translator: {translator}",
                    f"Source: {source_map}",
                    f"Generated map: {generated_map}",
                    f"stdout:\n{result.stdout.strip()}" if result.stdout.strip() else "",
                    f"stderr:\n{result.stderr.strip()}" if result.stderr.strip() else "",
                ]
                if part
            )
        )
    return generated_map, {
        "source_map": str(source_map),
        "generated_map": str(generated_map),
        "translated": True,
        "translator_stdout": result.stdout.strip(),
        "translator_stderr": result.stderr.strip(),
    }


def _faction_family_label(faction) -> str:
    if faction.is_rebel:
        return "Successor States"
    profile = faction.identity.language_profile if faction.identity else None
    family_name = getattr(profile, "family_name", "")
    if family_name:
        return family_name
    return faction.culture_name or faction.display_name


def _build_starting_family_labels(world) -> dict[str, str]:
    return {
        faction.internal_id: _faction_family_label(faction)
        for faction in world.factions.values()
        if not faction.is_rebel
    }


def _label_for_faction(world, faction_name: str | None, starting_labels: dict[str, str]) -> str:
    if faction_name is None:
        return "Unowned"
    faction = world.factions.get(faction_name)
    if faction is None:
        return faction_name
    if faction.is_rebel:
        return "Successor States"
    return starting_labels.get(faction.internal_id, _faction_family_label(faction))


def _owned_region_counts(world) -> dict[str, int]:
    counts = {faction_name: 0 for faction_name in world.factions}
    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1
    return counts


def _count_region_owner_changes(world, starting_labels: dict[str, str]) -> dict[str, dict[str, Any]]:
    region_stats: dict[str, dict[str, Any]] = {}
    if not world.region_history:
        return region_stats

    region_names = sorted(world.regions)
    previous_owners = {
        region_name: world.region_history[0].get(region_name, {}).get("owner")
        for region_name in region_names
    }
    changes = Counter()

    for snapshot in world.region_history[1:]:
        for region_name in region_names:
            owner = snapshot.get(region_name, {}).get("owner")
            if owner != previous_owners.get(region_name):
                changes[region_name] += 1
                previous_owners[region_name] = owner

    final_snapshot = world.region_history[-1]
    for region_name in region_names:
        final_owner = final_snapshot.get(region_name, {}).get("owner")
        region_stats[region_name] = {
            "changes": changes[region_name],
            "final_owner": _label_for_faction(world, final_owner, starting_labels),
        }
    return region_stats


def _winner_labels(values: dict[str, float], world, starting_labels: dict[str, str]) -> list[str]:
    if not values:
        return []
    best = max(values.values())
    return sorted(
        {
            _label_for_faction(world, faction_name, starting_labels)
            for faction_name, value in values.items()
            if value == best
        }
    )


def _average(counter: Counter, key: str, runs: int) -> float:
    return counter[key] / runs if runs else 0.0


def run_one(map_name: str, num_factions: int, turns: int, seed: str) -> dict[str, Any]:
    random.seed(seed)
    world = create_world(map_name=map_name, num_factions=num_factions, seed=seed)
    starting_labels = _build_starting_family_labels(world)
    world = run_simulation(world, num_turns=turns, verbose=False)

    owned_counts = _owned_region_counts(world)
    treasuries = {
        faction_name: float(faction.treasury)
        for faction_name, faction in world.factions.items()
    }
    region_values = {
        faction_name: float(owned_counts.get(faction_name, 0))
        for faction_name in world.factions
    }
    event_counts = Counter(event.type for event in world.events)
    system_activity = build_system_activity(world)
    dual_track_observability = build_dual_track_observability(world)
    competition = analyze_competition_metrics(world)
    region_changes = _count_region_owner_changes(world, starting_labels)

    family_final = {
        label: {
            "treasury": 0.0,
            "regions": 0,
            "population": 0,
            "active_factions": 0,
        }
        for label in sorted(set(starting_labels.values()) | {"Successor States"})
    }
    for faction_name, faction in world.factions.items():
        label = _label_for_faction(world, faction_name, starting_labels)
        family_final.setdefault(
            label,
            {"treasury": 0.0, "regions": 0, "population": 0, "active_factions": 0},
        )
        regions = owned_counts.get(faction_name, 0)
        family_final[label]["treasury"] += float(faction.treasury)
        family_final[label]["regions"] += regions
        family_final[label]["population"] += sum(
            region.population
            for region in world.regions.values()
            if region.owner == faction_name
        )
        if regions > 0:
            family_final[label]["active_factions"] += 1

    return {
        "seed": seed,
        "world": world,
        "starting_labels": starting_labels,
        "treasury_winners": _winner_labels(treasuries, world, starting_labels),
        "region_winners": _winner_labels(region_values, world, starting_labels),
        "family_final": family_final,
        "event_counts": event_counts,
        "system_activity": system_activity,
        "dual_track_actions": dual_track_observability,
        "competition": competition,
        "region_changes": region_changes,
        "final_faction_count": len(world.factions),
        "successor_faction_count": sum(1 for faction in world.factions.values() if faction.is_rebel),
    }


def summarize_runs(
    run_results: list[dict[str, Any]],
    *,
    map_name: str,
    num_factions: int,
    turns: int,
    map_info: dict[str, Any],
) -> dict[str, Any]:
    runs = len(run_results)
    family_labels = sorted(
        {
            label
            for result in run_results
            for label in result["family_final"]
        }
    )

    treasury_winners = Counter()
    region_winners = Counter()
    event_totals = Counter()
    region_change_totals = Counter()
    region_changed_runs = Counter()
    region_final_owners: dict[str, Counter] = defaultdict(Counter)
    system_totals: dict[str, dict[str, Any]] = {
        system_name: {
            "active_runs": 0,
            "event_counts": [],
            "metric_signal_counts": [],
            "first_turns": [],
        }
        for system_name in SYSTEM_DEFINITIONS
    }
    family_totals = {
        label: {
            "treasury": [],
            "regions": [],
            "population": [],
            "collapse_runs": 0,
            "active_factions": [],
        }
        for label in family_labels
    }
    health_lists = {
        "lead_changes": [],
        "runaway": [],
        "runaway_turn": [],
        "comeback": [],
        "largest_treasury_lead": [],
        "largest_region_lead": [],
        "final_factions": [],
        "successor_factions": [],
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

    notable = {
        "most_secessions": None,
        "largest_treasury_runaway": None,
        "most_region_churn": None,
    }

    for result in run_results:
        for label in result["treasury_winners"]:
            treasury_winners[label] += 1
        for label in result["region_winners"]:
            region_winners[label] += 1

        event_totals.update(result["event_counts"])
        secessions = result["event_counts"].get("unrest_secession", 0)
        churn = sum(region["changes"] for region in result["region_changes"].values())
        treasury_lead = result["competition"]["largest_treasury_lead"]["margin"]

        if notable["most_secessions"] is None or secessions > notable["most_secessions"]["value"]:
            notable["most_secessions"] = {"seed": result["seed"], "value": secessions}
        if notable["most_region_churn"] is None or churn > notable["most_region_churn"]["value"]:
            notable["most_region_churn"] = {"seed": result["seed"], "value": churn}
        if (
            notable["largest_treasury_runaway"] is None
            or treasury_lead > notable["largest_treasury_runaway"]["value"]
        ):
            notable["largest_treasury_runaway"] = {"seed": result["seed"], "value": treasury_lead}

        for label in family_labels:
            values = result["family_final"].get(
                label,
                {"treasury": 0.0, "regions": 0, "population": 0, "active_factions": 0},
            )
            family_totals[label]["treasury"].append(float(values["treasury"]))
            family_totals[label]["regions"].append(float(values["regions"]))
            family_totals[label]["population"].append(float(values["population"]))
            family_totals[label]["active_factions"].append(float(values["active_factions"]))
            if label != "Successor States" and int(values["regions"]) <= 0:
                family_totals[label]["collapse_runs"] += 1

        for region_name, region in result["region_changes"].items():
            changes = int(region["changes"])
            region_change_totals[region_name] += changes
            if changes > 0:
                region_changed_runs[region_name] += 1
            region_final_owners[region_name][region["final_owner"]] += 1

        for system_name, activity in result["system_activity"].items():
            slot = system_totals[system_name]
            slot["event_counts"].append(activity["event_count"])
            slot["metric_signal_counts"].append(activity["metric_signal_count"])
            if activity["active"]:
                slot["active_runs"] += 1
            if activity["first_turn"] is not None:
                slot["first_turns"].append(activity["first_turn"])

        dual_track = result["dual_track_actions"]
        dual_track_totals["qualifying_turns"] += dual_track["qualifying_turns"]
        dual_track_totals["both_track_turns"] += dual_track["both_track_turns"]
        dual_track_totals["bloc_competition_delta_sum"] += dual_track["bloc_competition_delta_sum"]
        dual_track_totals["bloc_competition_delta_samples"] += dual_track["bloc_competition_delta_samples"]
        dual_track_totals["military_action_count"] += dual_track["military_action_count"]
        dual_track_totals["military_dominant_action_count"] += dual_track["military_dominant_action_count"]
        for bucket, values in dual_track["track_split_by_faction_size"].items():
            target = dual_track_totals["track_split_by_faction_size"][bucket]
            samples = values["samples"]
            target["samples"] += samples
            target["military_track_rate_numerator"] += values["military_track_rate"] * samples
            target["admin_track_rate_numerator"] += values["admin_track_rate"] * samples

        competition = result["competition"]
        health_lists["lead_changes"].append(competition["lead_changes"])
        health_lists["runaway"].append(1.0 if competition["runaway"]["detected"] else 0.0)
        if competition["runaway"]["start_turn"] is not None:
            health_lists["runaway_turn"].append(competition["runaway"]["start_turn"])
        health_lists["comeback"].append(1.0 if competition["comeback"]["detected"] else 0.0)
        health_lists["largest_treasury_lead"].append(competition["largest_treasury_lead"]["margin"])
        health_lists["largest_region_lead"].append(competition["largest_region_lead"]["margin"])
        health_lists["final_factions"].append(result["final_faction_count"])
        health_lists["successor_factions"].append(result["successor_faction_count"])

    family_summary = {
        label: {
            "treasury_leader_rate": _average(treasury_winners, label, runs),
            "territory_leader_rate": _average(region_winners, label, runs),
            "average_treasury": mean(values["treasury"]) if values["treasury"] else 0.0,
            "average_regions": mean(values["regions"]) if values["regions"] else 0.0,
            "average_population": mean(values["population"]) if values["population"] else 0.0,
            "average_active_factions": mean(values["active_factions"]) if values["active_factions"] else 0.0,
            "collapse_rate": values["collapse_runs"] / runs if runs else 0.0,
        }
        for label, values in family_totals.items()
    }
    system_summary = {
        system_name: {
            "label": SYSTEM_DEFINITIONS[system_name]["label"],
            "active_rate": values["active_runs"] / runs if runs else 0.0,
            "average_events": mean(values["event_counts"]) if values["event_counts"] else 0.0,
            "average_metric_signals": (
                mean(values["metric_signal_counts"]) if values["metric_signal_counts"] else 0.0
            ),
            "average_first_turn": mean(values["first_turns"]) if values["first_turns"] else None,
        }
        for system_name, values in system_totals.items()
    }
    region_summary = {
        region_name: {
            "average_owner_changes": region_change_totals[region_name] / runs if runs else 0.0,
            "changed_run_rate": region_changed_runs[region_name] / runs if runs else 0.0,
            "most_common_final_owner": (
                region_final_owners[region_name].most_common(1)[0][0]
                if region_final_owners[region_name]
                else "Unknown"
            ),
            "most_common_final_owner_rate": (
                region_final_owners[region_name].most_common(1)[0][1] / runs
                if region_final_owners[region_name] and runs
                else 0.0
            ),
        }
        for region_name in sorted(region_change_totals)
    }
    political_average = {
        event_type: event_totals[event_type] / runs if runs else 0.0
        for event_type in sorted(POLITICAL_EVENT_TYPES | set(event_totals))
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
        "turns": turns,
        "runs": runs,
        "num_factions": num_factions,
        "map_info": map_info,
        "families": family_summary,
        "regions": region_summary,
        "systems": system_summary,
        "events": political_average,
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
        "health": {
            "average_lead_changes": mean(health_lists["lead_changes"]) if runs else 0.0,
            "runaway_rate": mean(health_lists["runaway"]) if runs else 0.0,
            "average_runaway_turn": (
                mean(health_lists["runaway_turn"]) if health_lists["runaway_turn"] else None
            ),
            "comeback_rate": mean(health_lists["comeback"]) if runs else 0.0,
            "average_largest_treasury_lead": mean(health_lists["largest_treasury_lead"]) if runs else 0.0,
            "average_largest_region_lead": mean(health_lists["largest_region_lead"]) if runs else 0.0,
            "average_final_factions": mean(health_lists["final_factions"]) if runs else 0.0,
            "average_successor_factions": mean(health_lists["successor_factions"]) if runs else 0.0,
        },
        "notable_seeds": notable,
        "suspicious_findings": _build_suspicious_findings(
            family_summary,
            region_summary,
            system_summary,
            political_average,
            {
                "runaway_rate": mean(health_lists["runaway"]) if runs else 0.0,
                "average_successor_factions": mean(health_lists["successor_factions"]) if runs else 0.0,
            },
        ),
    }


def _build_suspicious_findings(
    family_summary: dict[str, Any],
    region_summary: dict[str, Any],
    system_summary: dict[str, Any],
    events: dict[str, float],
    health: dict[str, float],
) -> list[str]:
    findings: list[str] = []
    quiet_systems = [
        system["label"]
        for system in system_summary.values()
        if system["active_rate"] < 0.20
    ]
    if quiet_systems:
        findings.append(f"Quiet systems: {', '.join(quiet_systems)}.")
    if health["runaway_rate"] > 0.60:
        findings.append(f"Treasury runaways are common ({health['runaway_rate']:.0%} of runs).")
    if family_summary.get("Successor States", {}).get("territory_leader_rate", 0.0) > 0.20:
        findings.append("Successor states frequently finish as territorial leaders.")
    collapsed = [
        label
        for label, values in family_summary.items()
        if label != "Successor States" and values["collapse_rate"] > 0.35
    ]
    if collapsed:
        findings.append(f"High collapse rates: {', '.join(collapsed)}.")
    if events.get("diplomacy_rivalry", 0.0) > 12.0:
        findings.append("Rivalry events are very frequent; repeated rivalry logging may need inspection.")
    overstable = [
        region
        for region, values in region_summary.items()
        if values["changed_run_rate"] < 0.03
    ]
    if len(overstable) > max(4, len(region_summary) // 3):
        findings.append("Many regions almost never change owner; check whether starts or geography are too sticky.")
    if not findings:
        findings.append("No obvious calibration warnings crossed the current thresholds.")
    return findings


def _format_percent(value: float) -> str:
    return f"{value:.0%}"


def _format_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _top_items(mapping: dict[str, Any], key: str, limit: int = 8) -> list[tuple[str, Any]]:
    return sorted(
        mapping.items(),
        key=lambda item: (-float(item[1].get(key, 0.0)), item[0]),
    )[:limit]


def format_report(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    map_info = summary["map_info"]
    lines.append("Azhora Calibration Report")
    lines.append("")
    lines.append(f"Runs: {summary['runs']}")
    lines.append(f"Turns per run: {summary['turns']}")
    lines.append(f"Map: {summary['map_name']}")
    if map_info.get("source_map"):
        lines.append(f"Source map: {map_info['source_map']}")
    lines.append(f"Generated map: {map_info['generated_map']}")
    lines.append(f"Translated this run: {'yes' if map_info.get('translated') else 'no'}")
    lines.append("")

    lines.append("Outcome By Family")
    lines.append(
        f"{'Family':<20} {'TreasLead':>10} {'TerrLead':>9} {'Treasury':>10} "
        f"{'Regions':>8} {'Pop':>10} {'Collapse':>9}"
    )
    lines.append("-" * 83)
    for label, values in sorted(
        summary["families"].items(),
        key=lambda item: (-item[1]["treasury_leader_rate"], item[0]),
    ):
        lines.append(
            f"{label:<20} "
            f"{_format_percent(values['treasury_leader_rate']):>10} "
            f"{_format_percent(values['territory_leader_rate']):>9} "
            f"{_format_float(values['average_treasury']):>10} "
            f"{_format_float(values['average_regions']):>8} "
            f"{_format_float(values['average_population'], 0):>10} "
            f"{_format_percent(values['collapse_rate']):>9}"
        )
    lines.append("")

    health = summary["health"]
    runaway_turn = health["average_runaway_turn"]
    runaway_turn_text = f"{runaway_turn:.1f}" if runaway_turn is not None else "n/a"
    lines.append("Run Shape")
    lines.append(
        f"  Runaway rate: {_format_percent(health['runaway_rate'])}"
        f" | Avg runaway turn: {runaway_turn_text}"
        f" | Comeback rate: {_format_percent(health['comeback_rate'])}"
    )
    lines.append(
        f"  Avg lead changes: {_format_float(health['average_lead_changes'])}"
        f" | Avg treasury lead: {_format_float(health['average_largest_treasury_lead'])}"
        f" | Avg region lead: {_format_float(health['average_largest_region_lead'])}"
    )
    lines.append(
        f"  Avg final factions: {_format_float(health['average_final_factions'])}"
        f" | Avg successor factions: {_format_float(health['average_successor_factions'])}"
    )
    lines.append("")

    dual_track = summary.get("dual_track_actions", {})
    lines.append("Dual-Track Actions")
    lines.append(
        f"  Activation: {_format_percent(dual_track.get('dual_track_activation_rate', 0.0))}"
        f" ({int(dual_track.get('both_track_turns', 0))}/"
        f"{int(dual_track.get('qualifying_turns', 0))} qualifying faction-turns)"
    )
    lines.append(
        f"  Avg bloc utility delta: {_format_float(dual_track.get('bloc_competition_delta', 0.0), 4)}"
        f" | Military-action dominant-bloc alignment: "
        f"{_format_percent(dual_track.get('dominant_bloc_action_alignment', 0.0))}"
    )
    track_split = dual_track.get("track_split_by_faction_size", {})
    if track_split:
        lines.append(
            "  Track split by size: "
            + " | ".join(
                f"{bucket}: mil {_format_percent(track_split.get(bucket, {}).get('military_track_rate', 0.0))}/"
                f"admin {_format_percent(track_split.get(bucket, {}).get('admin_track_rate', 0.0))}"
                for bucket in ("1-3", "4-7", "8+")
            )
        )
    lines.append("")

    lines.append("Most Contested Regions")
    for region_name, values in _top_items(summary["regions"], "average_owner_changes", limit=10):
        lines.append(
            f"  {region_name}: {_format_float(values['average_owner_changes'])} owner changes/run"
            f" | changed in {_format_percent(values['changed_run_rate'])}"
            f" | usual final owner {values['most_common_final_owner']}"
            f" ({_format_percent(values['most_common_final_owner_rate'])})"
        )
    lines.append("")

    lines.append("System Activity")
    lines.append(f"{'System':<22} {'Active':>8} {'Events':>8} {'Signals':>8} {'First':>8}")
    lines.append("-" * 60)
    for system_name in SYSTEM_DEFINITIONS:
        system = summary["systems"][system_name]
        first_turn = system["average_first_turn"]
        first_text = f"{first_turn:.1f}" if first_turn is not None else "n/a"
        lines.append(
            f"{system['label']:<22} "
            f"{_format_percent(system['active_rate']):>8} "
            f"{_format_float(system['average_events']):>8} "
            f"{_format_float(system['average_metric_signals']):>8} "
            f"{first_text:>8}"
        )
    lines.append("")

    lines.append("Political Event Averages")
    for event_type in sorted(POLITICAL_EVENT_TYPES):
        lines.append(f"  {event_type}: {_format_float(summary['events'].get(event_type, 0.0))}")
    lines.append("")

    lines.append("Seeds To Inspect")
    for label, entry in summary["notable_seeds"].items():
        if entry:
            value = entry["value"]
            value_text = _format_float(value) if isinstance(value, float) else str(value)
            lines.append(f"  {label}: {entry['seed']} ({value_text})")
    lines.append("")

    lines.append("Calibration Warnings")
    for finding in summary["suspicious_findings"]:
        lines.append(f"  - {finding}")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1.")
    if args.turns < 1:
        raise SystemExit("--turns must be at least 1.")

    map_file, map_info = _resolve_map_file(args)
    map_name, num_factions, _map_def = _inject_map_file(map_file)

    run_results = []
    for index in range(args.runs):
        seed = f"{args.seed_prefix}-{index + 1:03d}"
        print(f"Running {index + 1}/{args.runs}: {seed}", file=sys.stderr)
        run_results.append(run_one(map_name, num_factions, args.turns, seed))

    summary = summarize_runs(
        run_results,
        map_name=map_name,
        num_factions=num_factions,
        turns=args.turns,
        map_info=map_info,
    )
    report = format_report(summary)

    print(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")


if __name__ == "__main__":
    main()
