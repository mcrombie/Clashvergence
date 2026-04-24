from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from src.calendar import format_snapshot_date, format_turn_date, format_turn_span
from src.event_analysis import ensure_event_importance_scores
from src.metrics import get_faction_metrics_history


PHASE_LABELS = ("Early", "Mid", "Late")
MAJOR_EVENT_TYPES = {
    "expand",
    "attack",
    "develop",
    "invest",
    "war_declared",
    "war_peace",
    "unrest_secession",
    "rebel_independence",
    "succession",
    "succession_crisis",
    "religious_reform",
    "polity_advance",
    "regime_agitation",
    "migration_wave",
    "refugee_wave",
    "unrest_crisis",
    "unrest_disturbance",
    "diplomacy_tributary",
    "diplomacy_alliance",
    "diplomacy_rivalry",
}

EVENT_TYPE_BASE_WEIGHTS = {
    "war_peace": 6.0,
    "unrest_secession": 6.0,
    "rebel_independence": 5.5,
    "succession_crisis": 5.0,
    "war_declared": 4.5,
    "religious_reform": 4.2,
    "polity_advance": 4.0,
    "succession": 3.8,
    "attack": 3.6,
    "regime_agitation": 3.4,
    "refugee_wave": 3.4,
    "migration_wave": 2.8,
    "expand": 2.8,
    "diplomacy_tributary": 2.6,
    "diplomacy_alliance": 2.2,
    "diplomacy_rivalry": 2.0,
    "unrest_crisis": 2.0,
    "unrest_disturbance": 1.4,
    "develop": 1.2,
    "invest": 1.2,
}

EVENT_PRIORITY = {
    event_type: priority
    for priority, event_type in enumerate(
        [
            "war_peace",
            "unrest_secession",
            "rebel_independence",
            "succession_crisis",
            "war_declared",
            "religious_reform",
            "polity_advance",
            "attack",
            "regime_agitation",
            "refugee_wave",
            "migration_wave",
            "expand",
            "succession",
            "diplomacy_tributary",
            "diplomacy_alliance",
            "diplomacy_rivalry",
            "develop",
            "invest",
            "unrest_crisis",
            "unrest_disturbance",
        ]
    )
}

DRIVER_ORDER = {
    "internal fracture": 0,
    "military conquest": 1,
    "state-building": 2,
    "administrative strain": 3,
    "economic conversion": 4,
    "trade warfare": 5,
    "migration pressure": 6,
    "religious transformation": 7,
    "diplomatic hierarchy": 8,
}

TURNING_POINT_TYPE_LIMITS = {
    "develop": 2,
    "invest": 2,
    "expand": 2,
}


@dataclass
class PhaseAnalysis:
    name: str
    start_turn: int
    end_turn: int
    leader: str | None
    leader_regions: int
    leader_treasury: int
    event_counts: Counter
    region_deltas: dict[str, int]
    treasury_deltas: dict[str, int]
    top_driver: str
    contested: bool
    summary: str


@dataclass
class NarrativeDriver:
    name: str
    score: float
    detail: str


def _display_name(world, faction_name: str | None) -> str:
    if faction_name is None:
        return "another faction"
    faction = world.factions.get(faction_name)
    if faction is None:
        return faction_name
    return faction.display_name


def _format_turn(zero_based_turn: int | None) -> str:
    if zero_based_turn is None:
        return "an unknown turn"
    return format_turn_date(zero_based_turn)


def _count_noun(count: int | float, singular: str, plural: str | None = None) -> str:
    plural = plural or f"{singular}s"
    noun = singular if count == 1 else plural
    if isinstance(count, float) and count.is_integer():
        count = int(count)
    return f"{count} {noun}"


def _current_region_counts(world) -> dict[str, int]:
    counts = {faction_name: 0 for faction_name in world.factions}
    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1
    return counts


def _initial_region_counts(world) -> dict[str, int]:
    counts = {faction_name: 0 for faction_name in world.factions}
    if world.region_history:
        for region_snapshot in world.region_history[0].values():
            owner = region_snapshot.get("owner")
            if owner in counts:
                counts[owner] += 1
        return counts

    if world.metrics:
        first_snapshot = world.metrics[0]
        for faction_name, metrics in first_snapshot["factions"].items():
            counts[faction_name] = int(metrics.get("regions", 0))
    return counts


def _build_final_standings(world) -> list[dict[str, Any]]:
    region_counts = _current_region_counts(world)
    standings = []
    for faction_name, faction in world.factions.items():
        standings.append(
            {
                "faction": faction_name,
                "display_name": faction.display_name,
                "treasury": int(faction.treasury),
                "regions": int(region_counts.get(faction_name, 0)),
                "government": faction.government_type,
                "doctrine": faction.doctrine_label,
                "ethnicity": faction.primary_ethnicity,
                "is_rebel": bool(faction.is_rebel),
                "origin_faction": faction.origin_faction,
                "conflict_type": faction.rebel_conflict_type,
            }
        )

    standings.sort(
        key=lambda entry: (
            entry["treasury"],
            entry["regions"],
            entry["display_name"],
        ),
        reverse=True,
    )
    for rank, entry in enumerate(standings, start=1):
        entry["rank"] = rank
    return standings


def _event_involves_faction(event, faction_name: str) -> bool:
    if event.faction == faction_name:
        return True

    related_keys = (
        "winner",
        "loser",
        "defender",
        "counterpart",
        "origin_faction",
        "rebel_faction",
        "claimant_faction",
        "subordinate",
        "lead_sponsor",
    )
    for key in related_keys:
        if event.get(key) == faction_name:
            return True
    return False


def get_phase_ranges(total_turns: int) -> list[tuple[str, int, int]]:
    if total_turns <= 0:
        return []

    early_end = max(1, total_turns // 3)
    mid_end = max(early_end + 1, (2 * total_turns) // 3)
    mid_end = min(mid_end, total_turns)

    ranges = [("Early", 1, early_end)]
    if early_end + 1 <= mid_end:
        ranges.append(("Mid", early_end + 1, mid_end))
    if mid_end + 1 <= total_turns:
        ranges.append(("Late", mid_end + 1, total_turns))
    return ranges


def _phase_event_bucket(event_type: str) -> str:
    if event_type in {"attack", "war_declared", "war_peace", "diplomacy_rivalry"}:
        return "warfare"
    if event_type in {"expand"}:
        return "expansion"
    if event_type in {"develop", "invest", "polity_advance", "diplomacy_alliance", "diplomacy_tributary"}:
        return "state-building"
    if event_type in {"religious_reform"}:
        return "religious"
    if event_type in {"migration_wave", "refugee_wave"}:
        return "migration"
    if event_type in {"succession", "succession_crisis", "unrest_secession", "rebel_independence", "regime_agitation", "unrest_crisis", "unrest_disturbance"}:
        return "fracture"
    return "other"


def _phase_driver_label(counter: Counter) -> str:
    ranked = sorted(counter.items(), key=lambda item: (item[1], item[0]), reverse=True)
    if not ranked or ranked[0][1] == 0:
        return "quiet consolidation"
    return ranked[0][0]


def _get_phase_start_metrics(world, start_turn: int) -> dict[str, dict[str, int]]:
    if start_turn <= 1:
        initial_regions = _initial_region_counts(world)
        return {
            faction_name: {
                "regions": initial_regions.get(faction_name, 0),
                "treasury": int(world.factions[faction_name].starting_treasury),
            }
            for faction_name in world.factions
        }

    previous_snapshot = next(
        (snapshot for snapshot in world.metrics if snapshot["turn"] == start_turn - 1),
        None,
    )
    if previous_snapshot is None:
        return {
            faction_name: {"regions": 0, "treasury": int(world.factions[faction_name].starting_treasury)}
            for faction_name in world.factions
        }
    return {
        faction_name: {
            "regions": int(metrics.get("regions", 0)),
            "treasury": int(metrics.get("treasury", 0)),
        }
        for faction_name, metrics in previous_snapshot["factions"].items()
    }


def _get_phase_end_metrics(end_snapshot: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        faction_name: {
            "regions": int(metrics.get("regions", 0)),
            "treasury": int(metrics.get("treasury", 0)),
        }
        for faction_name, metrics in end_snapshot["factions"].items()
    }


def _describe_phase_driver(driver: str, counter: Counter) -> str:
    if driver == "fracture":
        return (
            f"internal fracture set the pace with "
            f"{_count_noun(counter['fracture'], 'shock')}"
        )
    if driver == "warfare":
        return (
            f"warfare dominated through {_count_noun(counter['warfare'], 'major clash')}"
        )
    if driver == "state-building":
        return (
            f"state-building led the phase with "
            f"{_count_noun(counter['state-building'], 'institutional step')}"
        )
    if driver == "expansion":
        return f"frontier expansion remained central with {_count_noun(counter['expansion'], 'claim')}"
    if driver == "migration":
        return f"population movement mattered, with {_count_noun(counter['migration'], 'major migration wave')}"
    if driver == "religious":
        return f"religious change reshaped the phase through {_count_noun(counter['religious'], 'reform')}"
    return "no single dynamic overpowered the rest"


def summarize_phases(world) -> tuple[list[PhaseAnalysis], list[str]]:
    total_turns = max(int(world.turn), len(world.metrics))
    analyses: list[PhaseAnalysis] = []
    summaries: list[str] = []

    for phase_name, start_turn, end_turn in get_phase_ranges(total_turns):
        phase_snapshots = [
            snapshot
            for snapshot in world.metrics
            if start_turn <= snapshot["turn"] <= end_turn
        ]
        if not phase_snapshots:
            continue

        phase_events = [
            event
            for event in world.events
            if start_turn - 1 <= event.turn <= end_turn - 1
        ]

        start_metrics = _get_phase_start_metrics(world, start_turn)
        end_snapshot = phase_snapshots[-1]
        end_metrics = _get_phase_end_metrics(end_snapshot)
        faction_names = sorted(set(start_metrics) | set(end_metrics))
        region_deltas = {
            faction_name: int(end_metrics.get(faction_name, {}).get("regions", 0))
            - int(start_metrics.get(faction_name, {}).get("regions", 0))
            for faction_name in faction_names
        }
        treasury_deltas = {
            faction_name: int(end_metrics.get(faction_name, {}).get("treasury", 0))
            - int(start_metrics.get(faction_name, {}).get("treasury", 0))
            for faction_name in faction_names
        }

        ranking = sorted(
            end_snapshot["factions"].items(),
            key=lambda item: (
                int(item[1].get("treasury", 0)),
                int(item[1].get("regions", 0)),
            ),
            reverse=True,
        )
        leader = ranking[0][0] if ranking else None
        leader_treasury = int(ranking[0][1].get("treasury", 0)) if ranking else 0
        leader_regions = int(ranking[0][1].get("regions", 0)) if ranking else 0
        runner_up_treasury = int(ranking[1][1].get("treasury", 0)) if len(ranking) > 1 else leader_treasury
        contested = len(ranking) > 1 and abs(leader_treasury - runner_up_treasury) <= 3

        bucket_counts = Counter()
        for event in phase_events:
            bucket_counts[_phase_event_bucket(event.type)] += 1

        top_driver = _phase_driver_label(bucket_counts)
        region_riser = max(region_deltas.items(), key=lambda item: (item[1], item[0]), default=(None, 0))
        treasury_riser = max(treasury_deltas.items(), key=lambda item: (item[1], item[0]), default=(None, 0))

        fragments = [
            f"{phase_name} ({start_turn}-{end_turn}): {_display_name(world, leader)} led the phase at "
            f"{leader_treasury} treasury and {_count_noun(leader_regions, 'region')}"
            if leader is not None
            else f"{phase_name} ({start_turn}-{end_turn}): no clear leader emerged."
        ]
        fragments.append(_describe_phase_driver(top_driver, bucket_counts))
        if contested:
            fragments.append("the treasury race remained tight")
        if region_riser[0] is not None and region_riser[1] > 0:
            fragments.append(
                f"{_display_name(world, region_riser[0])} gained {_count_noun(region_riser[1], 'region')} most quickly"
            )
        elif treasury_riser[0] is not None and treasury_riser[1] > 0:
            fragments.append(
                f"{_display_name(world, treasury_riser[0])} added {treasury_riser[1]} treasury fastest"
            )

        summary = ". ".join(fragment.rstrip(".") for fragment in fragments if fragment) + "."
        analysis = PhaseAnalysis(
            name=phase_name,
            start_turn=start_turn,
            end_turn=end_turn,
            leader=leader,
            leader_regions=leader_regions,
            leader_treasury=leader_treasury,
            event_counts=bucket_counts,
            region_deltas=region_deltas,
            treasury_deltas=treasury_deltas,
            top_driver=top_driver,
            contested=contested,
            summary=summary,
        )
        analyses.append(analysis)
        summaries.append(summary)

    return analyses, summaries


def _event_primary_score(event) -> float:
    base = float(event.get("importance_score", 0.0) or 0.0)
    if base <= 0.0:
        base = float(event.significance or 0.0)
    return base


def _score_turning_point(event) -> float:
    score = _event_primary_score(event) + EVENT_TYPE_BASE_WEIGHTS.get(event.type, 0.0)
    tags = set(event.tags or [])

    if event.type == "attack" and event.get("success", False):
        score += 1.8
    if event.type == "unrest_secession":
        score += float(event.get("joined_region_count", 0) or 0) * 0.9
    if event.type in {"migration_wave", "refugee_wave"}:
        score += min(3.0, float(event.get("population_moved", 0) or 0) / 40.0)
    if event.type == "war_peace":
        peace_term = str(event.get("peace_term", ""))
        if peace_term and peace_term != "white_peace":
            score += 1.3
    if event.type == "religious_reform":
        score += 0.8
    if event.type == "polity_advance":
        score += 0.6

    if "civil_war" in tags:
        score += 2.0
    if "collapse" in tags:
        score += 1.4
    if "restoration" in tags or "revival" in tags:
        score += 1.1
    if "claimant" in tags:
        score += 1.0
    return round(score, 3)


def _summarize_turning_point_event(world, event) -> str | None:
    actor = _display_name(world, event.faction)
    region = event.region or event.get("war_target_region") or event.get("claimant_region")
    region_text = f" at {region}" if region else ""
    turn_text = _format_turn(event.turn)

    if event.type == "war_declared":
        defender = _display_name(world, event.get("defender") or event.get("counterpart"))
        objective = event.get("war_objective_label") or event.get("war_objective") or "war"
        return f"On {turn_text}, {actor} declared war on {defender}{region_text}, opening a conflict over {objective}."

    if event.type == "war_peace":
        winner = _display_name(world, event.get("winner") or event.faction)
        loser = _display_name(world, event.get("loser") or event.get("counterpart"))
        peace_term = str(event.get("peace_term", "peace")).replace("_", " ")
        return f"On {turn_text}, the war between {winner} and {loser} closed in a {peace_term} settlement."

    if event.type == "unrest_secession":
        rebel = _display_name(world, event.get("rebel_faction"))
        joined = int(event.get("joined_region_count", 0) or 0)
        conflict_type = str(event.get("conflict_type", "secession")).replace("_", " ")
        joined_text = ""
        if joined > 0:
            joined_text = f", drawing in {_count_noun(joined, 'additional region')}"
        return f"On {turn_text}, {region or 'a region'} broke from {actor} to form {rebel} in a {conflict_type}{joined_text}."

    if event.type == "rebel_independence":
        origin = _display_name(world, event.get("origin_faction"))
        successor_ethnicity = event.get("successor_ethnicity")
        ethnicity_text = f" under the new {successor_ethnicity} identity" if successor_ethnicity else ""
        return f"On {turn_text}, {actor} secured full independence from {origin}{ethnicity_text}."

    if event.type == "succession_crisis":
        claimant = _display_name(world, event.get("claimant_faction"))
        claimant_text = f"; claimant support crystallized around {claimant}" if claimant and claimant != "another faction" else ""
        return f"On {turn_text}, {actor} entered a succession crisis{claimant_text}."

    if event.type == "succession":
        new_ruler = event.get("new_ruler")
        succession_type = str(event.get("succession_type", "transition")).replace("_", " ")
        if new_ruler:
            return f"On {turn_text}, {actor} passed into a {succession_type} under {new_ruler}."
        return f"On {turn_text}, {actor} underwent a {succession_type} succession."

    if event.type == "religious_reform":
        old_religion = event.get("old_religion") or "the old faith"
        new_religion = event.get("new_religion") or "a reformed creed"
        return f"On {turn_text}, {actor} broke from {old_religion} and established {new_religion}."

    if event.type == "polity_advance":
        old_tier = str(event.get("old_polity_tier", "lower order")).replace("_", " ")
        new_tier = str(event.get("new_polity_tier", "higher order")).replace("_", " ")
        new_government = event.get("new_government_type") or "new institutions"
        return f"On {turn_text}, {actor} advanced from {old_tier} to {new_tier}, emerging as a {new_government}."

    if event.type == "regime_agitation":
        sponsor = _display_name(world, event.get("lead_sponsor"))
        return f"On {turn_text}, outside regime agitation destabilized {region or 'a border region'} under {actor}, with pressure led by {sponsor}."

    if event.type in {"migration_wave", "refugee_wave"}:
        moved = int(event.get("population_moved", 0) or 0)
        destination = event.get("top_destination")
        destination_text = f" toward {destination}" if destination else ""
        wave_text = "refugees fled" if event.type == "refugee_wave" else "population shifted"
        return f"On {turn_text}, {wave_text} from {region or 'a troubled region'}{destination_text}, involving {_count_noun(moved, 'person')}."

    if event.type == "attack":
        defender = _display_name(world, event.get("defender"))
        if event.get("success", False):
            return f"On {turn_text}, {actor} captured {region or 'a contested region'} from {defender}."
        return f"On {turn_text}, {actor} failed in an assault on {region or 'a contested region'} held by {defender}."

    if event.type == "expand":
        strategic_role = event.get("strategic_role")
        role_text = ""
        if strategic_role == "junction":
            role_text = ", taking a key junction"
        elif strategic_role == "frontier":
            role_text = ", opening a new frontier"
        return f"On {turn_text}, {actor} claimed {region or 'new territory'}{role_text}."

    if event.type in {"develop", "invest"}:
        taxable_change = float(event.get("taxable_change", 0.0) or 0.0)
        project_type = str(event.get("project_type", "development")).replace("_", " ")
        if taxable_change > 0:
            return f"On {turn_text}, {actor} improved {region or 'one of its regions'} through {project_type}, lifting taxable value by {taxable_change:.2f}."
        return f"On {turn_text}, {actor} invested in {region or 'one of its regions'} through {project_type}."

    if event.type == "diplomacy_tributary":
        subordinate = _display_name(world, event.get("subordinate") or event.get("counterpart"))
        relation = str(event.get("subordination_type", "tributary")).replace("_", " ")
        return f"On {turn_text}, {actor} forced {subordinate} into a {relation} relationship."

    if event.type == "diplomacy_alliance":
        counterpart = _display_name(world, event.get("counterpart"))
        return f"On {turn_text}, {actor} and {counterpart} entered an alliance."

    if event.type == "diplomacy_rivalry":
        counterpart = _display_name(world, event.get("counterpart"))
        return f"On {turn_text}, {actor} and {counterpart} hardened into open rivalry."

    return None


def _top_turning_points(
    world,
    limit: int = 5,
    *,
    focal_faction: str | None = None,
) -> list[dict[str, Any]]:
    ensure_event_importance_scores(world)
    candidates = []
    for event in world.events:
        if event.type not in MAJOR_EVENT_TYPES:
            continue
        if focal_faction is not None and not _event_involves_faction(event, focal_faction):
            continue
        summary = _summarize_turning_point_event(world, event)
        if summary is None:
            continue
        candidates.append(
            {
                "event": event,
                "score": _score_turning_point(event),
                "summary": summary,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["score"],
            -EVENT_PRIORITY.get(item["event"].type, 999),
            item["event"].turn,
        ),
        reverse=True,
    )

    selected = []
    seen_keys = set()
    selected_type_counts: Counter[str] = Counter()
    for item in candidates:
        event = item["event"]
        key = (event.turn, event.type, event.faction, event.region)
        if key in seen_keys:
            continue
        type_limit = TURNING_POINT_TYPE_LIMITS.get(event.type, limit)
        if selected_type_counts[event.type] >= type_limit:
            continue
        seen_keys.add(key)
        selected.append(item)
        selected_type_counts[event.type] += 1
        if len(selected) >= limit:
            break
    return selected


def _peak_metric_value(world, metric_key: str) -> float:
    peak = 0.0
    for snapshot in world.metrics:
        for metrics in snapshot["factions"].values():
            peak = max(peak, float(metrics.get(metric_key, 0.0) or 0.0))
    return peak


def _event_type_counts(world) -> Counter:
    counter = Counter()
    for event in world.events:
        counter[event.type] += 1
    return counter


def _build_driver_breakdown(world, standings: list[dict[str, Any]]) -> list[NarrativeDriver]:
    counts = _event_type_counts(world)
    winner = standings[0] if standings else None
    runner_up = standings[1] if len(standings) > 1 else None
    drivers: list[NarrativeDriver] = []

    attack_successes = sum(
        1 for event in world.events if event.type == "attack" and event.get("success", False)
    )
    internal_fracture_score = (
        counts["unrest_secession"] * 3.0
        + counts["rebel_independence"] * 2.8
        + counts["succession_crisis"] * 2.5
        + counts["regime_agitation"] * 1.6
        + counts["unrest_crisis"] * 1.2
    )
    if internal_fracture_score > 0:
        detail = (
            f"Internal fracture kept reshaping the board: "
            f"{_count_noun(counts['unrest_secession'], 'secession')}, "
            f"{_count_noun(counts['rebel_independence'], 'rebel state')} reaching independence, and "
            f"{_count_noun(counts['succession_crisis'], 'succession crisis')}."
        )
        drivers.append(NarrativeDriver("internal fracture", internal_fracture_score, detail))

    military_score = (
        attack_successes * 2.2
        + counts["war_declared"] * 1.7
        + counts["war_peace"] * 1.2
        + counts["diplomacy_rivalry"] * 0.5
    )
    if military_score > 0:
        detail = (
            f"Military pressure remained decisive through "
            f"{_count_noun(attack_successes, 'successful conquest')} and "
            f"{_count_noun(counts['war_declared'], 'formal war declaration')}."
        )
        drivers.append(NarrativeDriver("military conquest", military_score, detail))

    state_building_score = (
        counts["polity_advance"] * 2.4
        + (counts["develop"] + counts["invest"]) * 0.45
        + counts["diplomacy_tributary"] * 0.6
    )
    if state_building_score > 0:
        detail = (
            f"State-building mattered as well: "
            f"{_count_noun(counts['polity_advance'], 'polity advance')} and "
            f"{_count_noun(counts['develop'] + counts['invest'], 'development project')} "
            f"helped stronger cores harden into lasting advantages."
        )
        drivers.append(NarrativeDriver("state-building", state_building_score, detail))

    administrative_peak = _peak_metric_value(world, "administrative_overextension")
    strain_score = (
        administrative_peak * 6.0
        + counts["unrest_crisis"] * 0.8
        + counts["regime_agitation"] * 0.7
    )
    if strain_score > 1.0:
        detail = (
            f"Administrative strain limited several states: peak overextension reached "
            f"{administrative_peak:.2f}, and crisis unrest repeatedly stalled integration."
        )
        drivers.append(NarrativeDriver("administrative strain", strain_score, detail))

    trade_peak = _peak_metric_value(world, "trade_warfare_damage") + _peak_metric_value(world, "trade_blockade_losses")
    trade_score = trade_peak * 4.0
    if trade_score > 1.0:
        detail = (
            f"Trade warfare bit into exposed powers, with peak combined blockade and corridor damage reaching "
            f"{trade_peak:.2f}."
        )
        drivers.append(NarrativeDriver("trade warfare", trade_score, detail))

    migration_events = counts["migration_wave"] + counts["refugee_wave"]
    migration_score = (
        counts["refugee_wave"] * 2.0
        + counts["migration_wave"] * 1.2
        + max(
            _peak_metric_value(world, "refugee_inflow"),
            _peak_metric_value(world, "refugee_outflow"),
            _peak_metric_value(world, "migration_inflow"),
            _peak_metric_value(world, "migration_outflow"),
        ) / 35.0
    )
    if migration_score > 1.0:
        detail = (
            f"Population movement amplified instability through {_count_noun(migration_events, 'major wave')} "
            f"of migration or flight."
        )
        drivers.append(NarrativeDriver("migration pressure", migration_score, detail))

    religion_score = counts["religious_reform"] * 3.0
    if religion_score > 0:
        detail = (
            f"Religious transformation altered legitimacy, with "
            f"{_count_noun(counts['religious_reform'], 'reform')} creating new political-religious alignments."
        )
        drivers.append(NarrativeDriver("religious transformation", religion_score, detail))

    if winner is not None:
        treasury_margin = winner["treasury"] - (runner_up["treasury"] if runner_up is not None else 0)
        economic_peak = _peak_metric_value(world, "trade_income") + _peak_metric_value(world, "tribute_income")
        economic_lead_is_meaningful = treasury_margin >= 2
        won_on_efficiency = (
            runner_up is not None
            and winner["regions"] < runner_up["regions"]
            and treasury_margin > 0
        )
        economic_score = (
            max(0, treasury_margin) * 0.35
            + (counts["develop"] + counts["invest"]) * 0.15
            + economic_peak * 1.25
        )
        if economic_score > 1.0 and (
            won_on_efficiency
            or economic_lead_is_meaningful
            or economic_peak >= 2.0
        ):
            if won_on_efficiency:
                detail = (
                    f"The winning edge came from economic conversion: {winner['display_name']} finished ahead on treasury "
                    f"despite conceding more land to {runner_up['display_name']}."
                )
            elif runner_up is not None and treasury_margin == 0:
                detail = (
                    "Economic depth mattered even without a clean treasury winner: "
                    "trade and tribute kept the leading powers locked together deep into the finish."
                )
            elif economic_lead_is_meaningful:
                detail = (
                    f"Treasury conversion mattered in the end: {winner['display_name']} closed {treasury_margin} treasury "
                    f"clear of the runner-up."
                )
            else:
                detail = (
                    f"Economic depth helped sustain {winner['display_name']}'s position, with trade and tribute "
                    "padding the final balance even without a runaway lead."
                )
            drivers.append(NarrativeDriver("economic conversion", economic_score, detail))

    hierarchy_score = counts["diplomacy_tributary"] * 1.6 + counts["diplomacy_alliance"] * 0.9
    if hierarchy_score > 1.0:
        detail = (
            f"Diplomatic hierarchy shaped the finish through {_count_noun(counts['diplomacy_tributary'], 'tributary settlement')} "
            f"and {_count_noun(counts['diplomacy_alliance'], 'alliance')}."
        )
        drivers.append(NarrativeDriver("diplomatic hierarchy", hierarchy_score, detail))

    drivers.sort(
        key=lambda driver: (
            driver.score,
            -DRIVER_ORDER.get(driver.name, 999),
            driver.name,
        ),
        reverse=True,
    )
    return drivers


def _classify_outcome(world, standings: list[dict[str, Any]], drivers: list[NarrativeDriver]) -> tuple[str, str]:
    if not standings:
        return ("empty", "No faction survived long enough to produce a meaningful ending.")

    winner = standings[0]
    runner_up = standings[1] if len(standings) > 1 else None
    alive = [entry for entry in standings if entry["regions"] > 0]
    total_regions = max(1, len(world.regions))
    treasury_margin = winner["treasury"] - (runner_up["treasury"] if runner_up is not None else 0)
    region_margin = winner["regions"] - (runner_up["regions"] if runner_up is not None else 0)
    leading_driver = drivers[0].name if drivers else "military conquest"

    if runner_up is not None and treasury_margin == 0 and region_margin == 0:
        return (
            "dead_heat",
            f"After {world.turn} turns spanning {format_turn_span(world.turn)}, the world closed in an effective dead heat: {winner['display_name']} only finished atop the table by tie-break, level with {runner_up['display_name']} on both treasury and region count.",
        )

    if runner_up is not None and treasury_margin == 0 and region_margin > 0:
        return (
            "territorial_edge",
            f"After {world.turn} turns spanning {format_turn_span(world.turn)}, the leading powers shared the treasury lead, but {winner['display_name']} held the stronger territorial position with {region_margin} more regions than {runner_up['display_name']}.",
        )

    if winner["regions"] == total_regions or len(alive) <= 1:
        return (
            "domination",
            f"After {world.turn} turns spanning {format_turn_span(world.turn)}, {winner['display_name']} stood alone as the dominant territorial power, holding {_count_noun(winner['regions'], 'region')} and finishing on {winner['treasury']} treasury.",
        )

    if runner_up is not None and winner["regions"] < runner_up["regions"] and treasury_margin > 0:
        return (
            "economic_win",
            f"After {world.turn} turns spanning {format_turn_span(world.turn)}, {winner['display_name']} won the age on treasury rather than sheer map share, finishing {treasury_margin} treasury ahead of {runner_up['display_name']} despite holding fewer regions.",
        )

    if region_margin >= max(3, total_regions // 5) or treasury_margin >= 8:
        return (
            "hegemonic_edge",
            f"After {world.turn} turns spanning {format_turn_span(world.turn)}, {winner['display_name']} closed as the clear hegemon, leading by {treasury_margin} treasury and {region_margin} regions over the nearest rival.",
        )

    if leading_driver == "internal fracture" and len(alive) >= 3:
        return (
            "fractured_order",
            f"After {world.turn} turns spanning {format_turn_span(world.turn)}, the world ended in a fractured order: {winner['display_name']} finished first, but repeated breakaways kept the field politically splintered.",
        )

    return (
        "contested_balance",
        f"After {world.turn} turns spanning {format_turn_span(world.turn)}, {winner['display_name']} finished first in a contested balance, with no power fully extinguishing the rest of the field.",
    )


def summarize_strategic_interpretation(world) -> list[str]:
    standings = _build_final_standings(world)
    if not standings:
        return ["No end-state interpretation is available."]

    drivers = _build_driver_breakdown(world, standings)
    outcome_type, outcome_line = _classify_outcome(world, standings, drivers)
    turning_points = _top_turning_points(world, limit=3)

    lines = [outcome_line]

    if drivers:
        top_driver_names = [driver.name for driver in drivers[:3]]
        if len(top_driver_names) == 1:
            driver_summary = top_driver_names[0]
        elif len(top_driver_names) == 2:
            driver_summary = f"{top_driver_names[0]} and {top_driver_names[1]}"
        else:
            driver_summary = f"{top_driver_names[0]}, {top_driver_names[1]}, and {top_driver_names[2]}"
        lines.append(
            f"The ending was driven primarily by {driver_summary}."
        )

    if turning_points:
        lines.append(turning_points[0]["summary"])

    if outcome_type == "economic_win" and len(standings) > 1:
        lines.append(
            f"{standings[1]['display_name']} actually held more land, but {standings[0]['display_name']} converted position into treasury more efficiently."
        )

    return lines


def _build_faction_snapshot_series(world, faction_name: str) -> list[dict[str, Any]]:
    history = get_faction_metrics_history(world, faction_name)
    if history:
        return history

    current_regions = _current_region_counts(world).get(faction_name, 0)
    faction = world.factions[faction_name]
    return [
        {
            "turn": max(world.turn, 1),
            "regions": current_regions,
            "treasury": int(faction.treasury),
            "population": 0,
            "polity_tier": faction.polity_tier,
            "government_form": faction.government_form,
            "legitimacy": float(faction.succession.legitimacy or 0.0),
        }
    ]


def _build_faction_epilogue(world, standings_by_name: dict[str, dict[str, Any]], faction_name: str) -> str:
    faction = world.factions[faction_name]
    display_name = faction.display_name
    history = _build_faction_snapshot_series(world, faction_name)
    current = standings_by_name[faction_name]
    initial_regions = _initial_region_counts(world).get(faction_name, 0)
    peak_entry = max(history, key=lambda item: (int(item.get("regions", 0)), int(item.get("treasury", 0)), -int(item.get("turn", 0))))
    peak_regions = int(peak_entry.get("regions", 0))
    peak_turn = int(peak_entry.get("turn", history[-1].get("turn", world.turn)))
    final_regions = int(current["regions"])
    final_treasury = int(current["treasury"])
    opening_turn = int(history[0].get("turn", 1))

    faction_events = [event for event in world.events if event.faction == faction_name]
    event_counts = Counter(event.type for event in faction_events)
    highest_scored_event = max(
        faction_events,
        key=lambda event: _score_turning_point(event),
        default=None,
    )

    clauses = []
    if faction.is_rebel and faction.origin_faction:
        conflict_type = faction.rebel_conflict_type or "secession"
        clauses.append(
            f"{display_name} began as a {conflict_type.replace('_', ' ')} breakaway from {_display_name(world, faction.origin_faction)}"
        )
    elif opening_turn > 1:
        clauses.append(f"{display_name} only emerged by {format_snapshot_date(opening_turn)}")
    else:
        clauses.append(
            f"{display_name} opened with {_count_noun(initial_regions, 'region')}"
        )

    clauses.append(
        f"peaked at {_count_noun(peak_regions, 'region')} by {format_snapshot_date(peak_turn)}"
    )

    if final_regions <= 0:
        clauses.append("but disappeared from the map by the end")
    elif current["rank"] == 1:
        clauses.append(
            f"and finished first with {final_treasury} treasury across {_count_noun(final_regions, 'region')}"
        )
    elif final_regions < peak_regions:
        clauses.append(
            f"but slipped back to {final_treasury} treasury and {_count_noun(final_regions, 'region')}"
        )
    else:
        clauses.append(
            f"and endured to the finish with {final_treasury} treasury and {_count_noun(final_regions, 'region')}"
        )

    flavor_clauses = []
    if event_counts["succession_crisis"] > 0:
        flavor_clauses.append(
            f"succession crises hit it {_count_noun(event_counts['succession_crisis'], 'time')}"
        )
    if event_counts["religious_reform"] > 0:
        flavor_clauses.append("it reworked its religious legitimacy")
    if event_counts["polity_advance"] > 0:
        flavor_clauses.append("it climbed into a higher polity tier")
    if event_counts["rebel_independence"] > 0:
        flavor_clauses.append("its independence hardened into recognized statehood")
    if event_counts["unrest_secession"] > 0:
        flavor_clauses.append(
            f"its own lands shed {_count_noun(event_counts['unrest_secession'], 'province')}"
        )

    if highest_scored_event is not None:
        event_sentence = _summarize_turning_point_event(world, highest_scored_event)
        if event_sentence is not None:
            event_sentence = event_sentence.rstrip(".")
            event_sentence = event_sentence[0].lower() + event_sentence[1:]
            flavor_clauses.append(f"its defining moment came when {event_sentence}")

    sentence = ", ".join(clauses[:2]) + ", " + clauses[2] + "."
    if flavor_clauses:
        sentence += " " + " ".join(
            clause[0].upper() + clause[1:] + "."
            for clause in flavor_clauses[:2]
        )
    return sentence


def _select_epilogue_factions(world, standings: list[dict[str, Any]]) -> list[str]:
    alive = [entry["faction"] for entry in standings if entry["regions"] > 0]
    selected: list[str] = []
    selected.extend(alive[:4])

    notable_rebels = [
        entry["faction"]
        for entry in standings
        if entry["is_rebel"] and entry["faction"] not in selected
    ]
    selected.extend(notable_rebels[:2])

    if len(selected) < 5:
        for entry in standings:
            if entry["faction"] in selected:
                continue
            history = _build_faction_snapshot_series(world, entry["faction"])
            peak_regions = max(int(item.get("regions", 0)) for item in history)
            if peak_regions >= 2:
                selected.append(entry["faction"])
            if len(selected) >= 5:
                break

    return selected[:6]


def summarize_faction_epilogues(world) -> list[str]:
    standings = _build_final_standings(world)
    if not standings:
        return []

    standings_by_name = {entry["faction"]: entry for entry in standings}
    return [
        _build_faction_epilogue(world, standings_by_name, faction_name)
        for faction_name in _select_epilogue_factions(world, standings)
    ]


def summarize_final_standings(world) -> list[str]:
    standings = _build_final_standings(world)
    lines = []
    for index, entry in enumerate(standings):
        history = _build_faction_snapshot_series(world, entry["faction"])
        peak_regions = max(int(snapshot.get("regions", 0)) for snapshot in history)
        tie_note = ""
        previous_entry = standings[index - 1] if index > 0 else None
        next_entry = standings[index + 1] if index + 1 < len(standings) else None
        tied_with = None
        if previous_entry is not None and (
            previous_entry["treasury"] == entry["treasury"]
            and previous_entry["regions"] == entry["regions"]
        ):
            tied_with = previous_entry["display_name"]
        elif next_entry is not None and (
            next_entry["treasury"] == entry["treasury"]
            and next_entry["regions"] == entry["regions"]
        ):
            tied_with = next_entry["display_name"]
        if tied_with is not None:
            tie_note = f", tied on both measures with {tied_with}"
        lines.append(
            f"{entry['rank']}. {entry['display_name']} - {entry['treasury']} treasury, "
            f"{_count_noun(entry['regions'], 'region')}, peak {_count_noun(peak_regions, 'region')}{tie_note}."
        )
    return lines


def summarize_structural_drivers(world) -> list[str]:
    standings = _build_final_standings(world)
    drivers = _build_driver_breakdown(world, standings)
    return [driver.detail for driver in drivers[:4]]


def summarize_turning_points(world) -> list[str]:
    return [item["summary"] for item in _top_turning_points(world, limit=5)]


def summarize_victor_history(world) -> list[str]:
    standings = _build_final_standings(world)
    if not standings:
        return []

    winner = standings[0]
    runner_up = standings[1] if len(standings) > 1 else None
    drivers = _build_driver_breakdown(world, standings)
    outcome_type, _outcome_line = _classify_outcome(world, standings, drivers)
    treasury_margin = winner["treasury"] - (runner_up["treasury"] if runner_up is not None else 0)
    region_margin = winner["regions"] - (runner_up["regions"] if runner_up is not None else 0)
    winner_turning_points = _top_turning_points(
        world,
        limit=2,
        focal_faction=winner["faction"],
    )
    turning_points = winner_turning_points or _top_turning_points(world, limit=2)

    if outcome_type == "dead_heat" and runner_up is not None:
        sentence = (
            f"From {winner['display_name']}'s own chroniclers, the age would be remembered as a finish too close for comfort, "
            f"one in which they refused to yield first place to {runner_up['display_name']}."
        )
    elif outcome_type == "economic_win":
        sentence = (
            f"From {winner['display_name']}'s own chroniclers, the age would be remembered as proof that "
            f"{winner['doctrine'].lower()} habits could outlast broader territorial reach."
        )
    else:
        sentence = (
            f"From {winner['display_name']}'s own chroniclers, the age would be remembered as proof that "
            f"{winner['doctrine'].lower()} habits could be turned into durable supremacy."
        )

    lines = [sentence]
    if turning_points:
        lines.append(turning_points[0]["summary"])
    if runner_up is not None:
        if treasury_margin == 0 and region_margin == 0:
            rival_line = (
                f"They would cast {_display_name(world, runner_up['faction'])} as the last serious rival, "
                f"one that matched them measure for measure but still never displaced {winner['display_name']} from the top line."
            )
        elif treasury_margin == 0 and region_margin > 0:
            rival_line = (
                f"They would cast {_display_name(world, runner_up['faction'])} as the last serious rival, "
                f"one that kept pace on treasury but never matched {winner['display_name']}'s territorial reach."
            )
        else:
            rival_line = (
                f"They would cast {_display_name(world, runner_up['faction'])} as the last serious rival, "
                f"one that never fully overturned {winner['display_name']}'s final treasury edge."
            )
        lines.append(rival_line)
    if drivers:
        lines.append(
            f"In that partisan telling, the decisive forces were {drivers[0].name}"
            + (f" and {drivers[1].name}." if len(drivers) > 1 else ".")
        )
    return lines


def summarize_place_name_strata(world) -> list[str]:
    entries: list[tuple[int, str]] = []
    for region in world.regions.values():
        layers = list(region.name_metadata.get("name_layers", []))
        if len(layers) <= 1:
            continue
        fragments: list[str] = []
        for layer in layers[:4]:
            name = layer.get("name")
            faction_name = layer.get("faction_name")
            layer_type = layer.get("type")
            if not name or not layer_type:
                continue
            if layer_type == "founding":
                fragments.append(f"founded as {name} by {faction_name}")
            elif layer_type == "conquest":
                fragments.append(f"renamed to {name} under {faction_name}")
            elif layer_type == "restoration":
                fragments.append(f"restored as {name} by {faction_name}")
        if not fragments:
            continue
        line = f"{region.name}: " + ", then ".join(fragments) + "."
        entries.append((len(layers), line))
    return [line for _score, line in sorted(entries, key=lambda item: (-item[0], item[1]))[:5]]


def build_chronicle(world, max_key_events: int = 10) -> str:
    key_event_limit = max(1, int(max_key_events))
    lines: list[str] = ["Simulation Chronicle"]

    sections = [
        ("Outcome Explanation", summarize_strategic_interpretation(world)),
    ]

    _phase_analyses, phase_summaries = summarize_phases(world)
    sections.append(("Phase Summaries", phase_summaries))
    sections.append(("Turning Points", [item["summary"] for item in _top_turning_points(world, limit=key_event_limit)]))
    sections.append(("Structural Drivers", summarize_structural_drivers(world)))
    sections.append(("Faction Epilogues", summarize_faction_epilogues(world)))
    sections.append(("Place-Name Strata", summarize_place_name_strata(world)))
    sections.append(("Final Standings", summarize_final_standings(world)))
    sections.append(("Victor's History", summarize_victor_history(world)))

    for title, content in sections:
        if not content:
            continue
        lines.append("")
        lines.append(title)
        lines.append("")
        lines.extend(content)

    return "\n".join(lines)
