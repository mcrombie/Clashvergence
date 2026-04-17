from src.ai_interpretation import generate_ai_interpretation, generate_victor_history
from src.diplomacy import get_faction_diplomacy_summary
from src.event_analysis import (
    apply_event_to_replay_state,
    build_initial_opening_state,
    build_replay_state,
    clone_replay_state,
    ensure_event_importance_scores,
    get_faction_event_counts,
    get_final_standings,
    get_key_events,
    get_opening_phase_summary,
    get_scored_major_events,
    summarize_major_event,
)
from src.metrics import get_faction_metrics_history


def get_faction_display_name(world, faction_name):
    if faction_name is None:
        return "another faction"
    faction = world.factions.get(faction_name)
    if faction is None:
        return faction_name
    return faction.display_name


def format_turn(turn):
    """Formats zero-based turn indices for user-facing output."""
    return turn + 1


def format_score(value):
    """Formats score values without a trailing .0 when possible."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def format_count_noun(count, singular, plural=None):
    """Formats a count with the correct noun form."""
    plural = plural or f"{singular}s"
    noun = singular if count == 1 else plural
    return f"{count} {noun}"


def get_initial_region_counts(world):
    """Returns faction region counts before the first simulated turn."""
    counts = {faction_name: 0 for faction_name in world.factions}
    initial_state = build_initial_opening_state(world)

    for region in initial_state.values():
        owner = region["owner"]
        if owner in counts:
            counts[owner] += 1

    return counts


def get_phase_boundary_metrics(world, start_turn, end_turn):
    """Returns region/treasury snapshots at the start and end of a phase."""
    end_snapshot = next(
        snapshot for snapshot in world.metrics if snapshot["turn"] == end_turn
    )

    if start_turn == 1:
        start_regions = get_initial_region_counts(world)
        start_metrics = {
            faction_name: {
                "regions": start_regions[faction_name],
                "treasury": 1,
            }
            for faction_name in world.factions
        }
    else:
        start_snapshot = next(
            snapshot for snapshot in world.metrics if snapshot["turn"] == start_turn - 1
        )
        start_metrics = {
            faction_name: {
                "regions": faction_metrics["regions"],
                "treasury": faction_metrics["treasury"],
            }
            for faction_name, faction_metrics in start_snapshot["factions"].items()
        }

    end_metrics = {
        faction_name: {
            "regions": faction_metrics["regions"],
            "treasury": faction_metrics["treasury"],
        }
        for faction_name, faction_metrics in end_snapshot["factions"].items()
    }
    return start_metrics, end_metrics


def get_phase_ranges(total_turns):
    """Splits the simulation into early, mid, and late one-based turn ranges."""
    if total_turns <= 0:
        return []

    early_end = max(1, total_turns // 3)
    mid_end = max(early_end + 1, (2 * total_turns) // 3)
    mid_end = min(mid_end, total_turns)

    ranges = [
        ("Early", 1, early_end),
    ]

    if early_end + 1 <= mid_end:
        ranges.append(("Mid", early_end + 1, mid_end))

    if mid_end + 1 <= total_turns:
        ranges.append(("Late", mid_end + 1, total_turns))

    return ranges


def get_rankings_from_snapshot(snapshot):
    """Returns standings for one metrics snapshot using treasury then regions."""
    return sorted(
        snapshot["factions"].items(),
        key=lambda item: (item[1]["treasury"], item[1]["regions"]),
        reverse=True,
    )


def get_rank_map(snapshot):
    """Returns one-based ranks for all factions in one snapshot."""
    return {
        faction_name: index + 1
        for index, (faction_name, _metrics) in enumerate(get_rankings_from_snapshot(snapshot))
    }


def get_phase_dominant_action(event_counts):
    """Returns the action mix label for a phase."""
    ranked_actions = sorted(
        event_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    best_action, best_count = ranked_actions[0]
    second_count = ranked_actions[1][1]

    if best_count == 0:
        return "activity was limited"
    if best_count == second_count:
        return "activity was mixed across expansion, investment, and attacks"
    if best_action == "expand":
        return "expansion set the pace"
    if best_action == "invest":
        return "investment led the phase"
    return "attacks shaped the phase"


def get_alive_factions_from_metrics(snapshot):
    """Returns factions still holding territory in a metrics snapshot."""
    return [
        faction_name
        for faction_name, metrics in snapshot["factions"].items()
        if metrics["regions"] > 0
    ]


def analyze_phase(world, phase_name, start_turn, end_turn):
    """Builds structured phase analysis for later summary sections."""
    ensure_event_importance_scores(world)
    phase_snapshots = [snapshot for snapshot in world.metrics if start_turn <= snapshot["turn"] <= end_turn]

    if not phase_snapshots:
        return None

    phase_events = [
        event for event in world.events
        if start_turn - 1 <= event.turn <= end_turn - 1
    ]

    start_metrics, end_metrics = get_phase_boundary_metrics(world, start_turn, end_turn)
    event_counts = {"expand": 0, "invest": 0, "attack": 0}
    successful_attacks = 0
    attack_shifted_regions = set()
    expansion_regions = set()
    notable_expansions = []

    for event in phase_events:
        if event.type in event_counts:
            event_counts[event.type] += 1
        if event.type == "attack" and event.get("success", False):
            successful_attacks += 1
            if event.region is not None:
                attack_shifted_regions.add(event.region)
        if event.type == "expand" and event.region is not None:
            expansion_regions.add(event.region)
            if (
                event.get("strategic_role") == "junction"
                or event.get("is_turning_point", False)
                or event.get("importance_score", 0) >= 5
            ):
                notable_expansions.append(event)

    end_snapshot = phase_snapshots[-1]
    rankings = get_rankings_from_snapshot(end_snapshot)
    strongest = [rankings[0][0]]
    if len(rankings) > 1 and rankings[1][1]["treasury"] == rankings[0][1]["treasury"]:
        strongest.append(rankings[1][0])

    rank_changes = {}
    if len(phase_snapshots) >= 2:
        start_ranks = get_rank_map(phase_snapshots[0])
        end_ranks = get_rank_map(end_snapshot)
        for faction_name in end_snapshot["factions"]:
            start_rank = start_ranks.get(faction_name, len(start_ranks) + 1)
            end_rank = end_ranks.get(faction_name, len(end_ranks) + 1)
            rank_changes[faction_name] = start_rank - end_rank

    faction_names = set(world.factions) | set(start_metrics) | set(end_metrics)

    biggest_rise = None
    if rank_changes:
        biggest_rise = max(rank_changes, key=lambda name: rank_changes[name])
        if rank_changes[biggest_rise] <= 0:
            biggest_rise = None

    region_deltas = {
        faction_name: end_metrics.get(faction_name, {}).get("regions", 0)
        - start_metrics.get(faction_name, {}).get("regions", 0)
        for faction_name in faction_names
    }
    treasury_deltas = {
        faction_name: end_metrics.get(faction_name, {}).get("treasury", 0)
        - start_metrics.get(faction_name, {}).get("treasury", 0)
        for faction_name in faction_names
    }
    biggest_gain = max(region_deltas, key=lambda name: region_deltas[name])
    biggest_loss = min(region_deltas, key=lambda name: region_deltas[name])
    alive_factions = get_alive_factions_from_metrics(end_snapshot)
    end_regions = [metrics["regions"] for _name, metrics in rankings]
    top_regions = rankings[0][1]["regions"]
    second_regions = rankings[1][1]["regions"] if len(rankings) > 1 else top_regions
    region_spread = max(end_regions) - min(end_regions) if end_regions else 0
    close_contest = len(alive_factions) >= 3 and region_spread <= 2
    stable_board = (
        successful_attacks == 0
        and event_counts["expand"] == 0
        and max(abs(delta) for delta in region_deltas.values()) <= 1
    )

    return {
        "phase_name": phase_name,
        "start_turn": start_turn,
        "end_turn": end_turn,
        "events": phase_events,
        "rankings": rankings,
        "strongest": strongest,
        "end_snapshot": end_snapshot,
        "event_counts": event_counts,
        "successful_attacks": successful_attacks,
        "attack_shifted_regions": attack_shifted_regions,
        "expansion_regions": expansion_regions,
        "biggest_gain": biggest_gain,
        "biggest_loss": biggest_loss,
        "biggest_rise": biggest_rise,
        "region_deltas": region_deltas,
        "treasury_deltas": treasury_deltas,
        "alive_factions": alive_factions,
        "region_spread": region_spread,
        "lead_region_margin": top_regions - second_regions,
        "close_contest": close_contest,
        "stable_board": stable_board,
        "notable_expansion": max(
            notable_expansions,
            key=lambda event: event.get("importance_score", event.get("score", 0)),
            default=None,
        ),
    }


def summarize_phase_turns(phase_analysis):
    """Builds a concise strategic summary for one analyzed phase."""
    rankings = phase_analysis["rankings"]
    strongest = phase_analysis["strongest"]
    lead_name, lead_metrics = rankings[0]
    phase_name = phase_analysis["phase_name"]
    start_turn = phase_analysis["start_turn"]
    end_turn = phase_analysis["end_turn"]
    region_deltas = phase_analysis["region_deltas"]
    biggest_gain = phase_analysis["biggest_gain"]
    biggest_loss = phase_analysis["biggest_loss"]

    lead_summary = (
        f"{format_subject_verb(strongest, 'was', 'were')} strongest by the end of turns {start_turn}-{end_turn}, "
        f"with {lead_name} on {lead_metrics['treasury']} treasury and {format_count_noun(lead_metrics['regions'], 'region')}"
    )

    details = []
    if phase_analysis["stable_board"]:
        details.append(
            f"The board stabilized after turn {start_turn} with little territorial change"
        )
    else:
        if phase_analysis["close_contest"]:
            details.append(
                f"No faction pulled clear; {format_count_noun(len(phase_analysis['alive_factions']), 'faction')} remained within a {phase_analysis['region_spread']}-region spread"
            )
        if phase_analysis["successful_attacks"] > 0:
            details.append(
                f"{phase_analysis['successful_attacks']} successful attacks shifted control of {format_count_noun(len(phase_analysis['attack_shifted_regions']), 'region')}"
            )
        if phase_analysis["event_counts"]["expand"] > 0:
            details.append(
                f"{format_count_noun(phase_analysis['event_counts']['expand'], 'expansion')} added {format_count_noun(len(phase_analysis['expansion_regions']), 'new region')}"
            )
        if phase_analysis["event_counts"]["invest"] > 0:
            details.append(
                f"{format_count_noun(phase_analysis['event_counts']['invest'], 'investment')} improved existing holdings"
            )

    shifts = []
    if region_deltas[biggest_gain] > 0 and region_deltas[biggest_loss] < 0:
        shifts.append(
            f"{biggest_gain} gained {format_count_noun(region_deltas[biggest_gain], 'region')} while {biggest_loss} lost {format_count_noun(abs(region_deltas[biggest_loss]), 'region')}"
        )
    elif region_deltas[biggest_gain] > 0:
        shifts.append(
            f"{biggest_gain} gained {format_count_noun(region_deltas[biggest_gain], 'region')}"
        )

    if phase_analysis["biggest_rise"] is not None and phase_analysis["biggest_rise"] not in {biggest_gain, biggest_loss}:
        shifts.append(
            f"{phase_analysis['biggest_rise']} improved its standing most during the phase"
        )

    sentence = f"{phase_name} phase: {lead_summary}."
    if details:
        sentence += " " + ". ".join(details) + "."
    if shifts:
        sentence += " " + ". ".join(shifts) + "."
    return sentence


def summarize_phases(world):
    """Returns phase-based summaries for the full simulation."""
    analyses = []
    summaries = []
    for phase_name, start_turn, end_turn in get_phase_ranges(len(world.metrics)):
        phase_analysis = analyze_phase(world, phase_name, start_turn, end_turn)
        if phase_analysis is None:
            continue
        analyses.append(phase_analysis)
        summaries.append(summarize_phase_turns(phase_analysis))
    return analyses, summaries


def describe_early_posture(early_history):
    """Returns a concrete description of early faction behavior."""
    total_expansions = sum(entry["expansions"] for entry in early_history)
    total_attacks = sum(entry["attacks"] for entry in early_history)
    total_investments = sum(entry["investments"] for entry in early_history)
    final_regions = early_history[-1]["regions"]
    start_regions = early_history[0]["regions"] if early_history else 0
    region_gain = final_regions - start_regions

    if total_expansions > 0 and region_gain > 0:
        return (
            f"opened with {format_count_noun(total_expansions, 'claim')} and grew to "
            f"{format_count_noun(final_regions, 'region')} by the end of the opening phase"
        )
    if total_attacks > max(total_expansions, total_investments) and total_attacks > 0:
        return f"opened with {total_attacks} attack attempts and contested neighboring borders immediately"
    if total_investments > 0 and region_gain <= 0:
        return f"spent the opening consolidating its start with {format_count_noun(total_investments, 'investment')}"
    if final_regions <= 1:
        return "struggled to add territory in the opening turns"
    return f"opened quietly and held at {format_count_noun(final_regions, 'region')} through the first phase"


def describe_midgame(mid_history):
    """Returns a concrete mid-game trajectory phrase."""
    if not mid_history:
        return "had little mid-game activity"

    start_regions = mid_history[0]["regions"]
    end_regions = mid_history[-1]["regions"]
    total_attacks = sum(entry["attacks"] for entry in mid_history)
    treasury_change = mid_history[-1]["treasury"] - mid_history[0]["treasury"]
    attack_windows = sum(1 for entry in mid_history if entry["attacks"] > 0)

    if end_regions == start_regions and total_attacks == 0:
        return f"held steady at {format_count_noun(end_regions, 'region')} through the middle turns"
    if end_regions > start_regions and total_attacks >= len(mid_history):
        return (
            f"expanded under pressure, growing from {format_count_noun(start_regions, 'region')} "
            f"to {format_count_noun(end_regions, 'region')} while keeping attacks active"
        )
    if end_regions < start_regions:
        return (
            f"lost ground mid-game, falling from {format_count_noun(start_regions, 'region')} "
            f"to {format_count_noun(end_regions, 'region')}"
        )
    if treasury_change > 0 and attack_windows <= max(1, len(mid_history) // 3):
        return f"used the middle turns to scale economically, adding {treasury_change} treasury"
    if total_attacks > 0:
        return f"stayed active mid-game with {total_attacks} attack attempts while holding {format_count_noun(end_regions, 'region')}"
    return f"plateaued mid-game at {format_count_noun(end_regions, 'region')}"


def get_map_profile(world):
    """Returns grounded structural labels about the map."""
    region_count = len(world.regions)
    average_degree = sum(len(region.neighbors) for region in world.regions.values()) / region_count
    max_degree = max(len(region.neighbors) for region in world.regions.values())
    initial_counts = get_initial_region_counts(world)
    populated_counts = [count for count in initial_counts.values() if count > 0]
    symmetric_starts = len(set(populated_counts)) <= 1 if populated_counts else True

    if region_count <= 13:
        size_label = "compact"
    elif region_count >= 30:
        size_label = "large"
    else:
        size_label = "mid_size"

    if max_degree >= 8:
        topology_label = "central_hub"
    elif average_degree >= 4:
        topology_label = "well_connected"
    else:
        topology_label = "lane_driven"

    return {
        "region_count": region_count,
        "average_degree": average_degree,
        "max_degree": max_degree,
        "symmetric_starts": symmetric_starts,
        "size_label": size_label,
        "topology_label": topology_label,
    }


def get_map_structure_comment(world):
    """Returns a grounded comment about map scale and connectivity."""
    profile = get_map_profile(world)
    region_count = profile["region_count"]

    if profile["size_label"] == "compact":
        return f"On this compact {region_count}-region map, early contact came quickly"
    if profile["size_label"] == "large" and profile["symmetric_starts"]:
        return f"On this larger {region_count}-region layout, the wider front and multiple routes delayed a clean break"
    if profile["topology_label"] == "central_hub":
        return "A highly connected center kept several factions in contention before one side pulled clear"
    return f"On this {region_count}-region map, control of the best-connected routes mattered more than raw expansion count"


def describe_end_state(final_snapshot, final_rank, total_factions):
    """Returns a concrete ending-state phrase."""
    if final_rank == 1 and final_snapshot["regions"] == 0:
        return f"and finished first on treasury despite ending without territory at {final_snapshot['treasury']} treasury"
    if final_rank == 1:
        return (
            f"and finished dominant with {format_count_noun(final_snapshot['regions'], 'region')} and "
            f"{final_snapshot['treasury']} treasury"
        )
    if final_rank <= max(2, total_factions // 2):
        return (
            f"and closed competitive in rank {final_rank} with {format_count_noun(final_snapshot['regions'], 'region')} "
            f"and {final_snapshot['treasury']} treasury"
        )
    return (
        f"and ended weakened in rank {final_rank} with {format_count_noun(final_snapshot['regions'], 'region')} "
        f"and {final_snapshot['treasury']} treasury"
    )


def get_role_phrase(event):
    """Returns the strongest narrative framing for an expansion's role."""
    strategic_role = event.get("strategic_role")

    if strategic_role == "junction":
        return "a commanding junction"
    if strategic_role == "frontier":
        return "a frontier foothold"
    if strategic_role == "consolidation":
        return "a consolidating gain"
    if strategic_role == "gamble":
        return "a risky outpost"

    if event.get("importance_tier") in {"major", "high"}:
        return "a valuable prize"

    return "an important gain"


def get_expansion_follow_up(event, used_outcome_clause=False):
    """Returns at most one short follow-up sentence for a key expansion."""
    if event.get("is_turning_point"):
        return "The move proved a genuine turning point in the opening contest."

    if event.get("rank_change") is not None and event.get("rank_change") > 0 and event.get("rank_after") is not None:
        return f"It lifted {event['faction']} to rank {event['rank_after']}."

    if event.get("momentum_effect") in {"surging", "accelerating"}:
        if used_outcome_clause:
            return None
        if event.get("future_expansion_opened", 0) >= 3:
            return f"It opened room for further expansion."
        if event.get("income_gain", 0) >= 3:
            return f"It strengthened {event['faction']}'s income position."

    return None


def get_outcome_clause(event):
    """Returns a short outcome-aware clause when it adds value."""
    if event.get("follow_up_region") is not None:
        return f" and later supported its expansion into {event['follow_up_region']}"
    if event.get("future_expansion_opened", 0) >= 4:
        return " and later opened the way for further expansion"
    if event.get("income_gain", 0) >= 3:
        return " and later strengthened its income base"
    return ""


def summarize_event(event):
    """Turns one analyzed event into a sentence."""
    if event["kind"] == "first_expansion":
        return (
            f"On turn {format_turn(event['turn'])}, {event['faction']} made its first expansion into "
            f"{event['region']}."
        )

    if event["kind"] == "high_value_expansion":
        role_phrase = get_role_phrase(event)
        reason_clause = event.get("summary_reason") or "it strengthened the faction's position"
        outcome_clause = get_outcome_clause(event)
        follow_up = get_expansion_follow_up(event, used_outcome_clause=bool(outcome_clause))

        sentence = (
            f"On turn {format_turn(event['turn'])}, {event['faction']} seized {event['region']}, "
            f"{role_phrase} that mattered because {reason_clause}{outcome_clause}."
        )

        if follow_up:
            sentence += f" {follow_up}"

        return sentence

    return None


def format_faction_list(faction_names):
    """Formats one or more faction names as readable prose."""
    if not faction_names:
        return "no faction"

    if len(faction_names) == 1:
        return faction_names[0]

    if len(faction_names) == 2:
        return f"{faction_names[0]} and {faction_names[1]}"

    return f"{', '.join(faction_names[:-1])}, and {faction_names[-1]}"


def format_subject_verb(faction_names, singular_verb, plural_verb):
    """Formats a faction list with the correct singular/plural verb."""
    names = format_faction_list(faction_names)
    verb = singular_verb if len(faction_names) == 1 else plural_verb
    return f"{names} {verb}"


def sentence_case(text):
    """Uppercases the first character without lowercasing the rest."""
    if not text:
        return text
    return text[0].upper() + text[1:]


def summarize_opening_phase(world):
    """Returns a short summary of opening-phase patterns."""
    opening = get_opening_phase_summary(world)
    lines = []

    highest_scoring_claim = opening["highest_scoring_claim"]
    if highest_scoring_claim is not None:
        role_phrase = get_role_phrase(highest_scoring_claim)
        lines.append(
            f"The strongest early land grab was {get_faction_display_name(world, highest_scoring_claim['faction'])}'s claim of "
            f"{highest_scoring_claim['region']} on turn {format_turn(highest_scoring_claim['turn'])}, "
            f"{role_phrase} that stood out because {highest_scoring_claim['summary_reason']}."
        )

    expansion_leaders = opening["expansion_leaders"]
    if expansion_leaders["count"] > 0:
        lines.append(
            f"In the first {expansion_leaders['turns']} turns, "
            f"{format_faction_list([get_faction_display_name(world, name) for name in expansion_leaders['leaders']])} led expansion with "
            f"{expansion_leaders['count']} claim(s)."
        )

    investment_leaders = opening["investment_leaders"]
    if investment_leaders["count"] > 0:
        lines.append(
            f"Across the first {investment_leaders['turns']} turns, "
            f"{format_faction_list([get_faction_display_name(world, name) for name in investment_leaders['leaders']])} invested most often with "
            f"{investment_leaders['count']} investment(s)."
        )

    treasury_leaders = opening["treasury_leaders"]
    if treasury_leaders["leaders"]:
        lines.append(
            f"By the end of turn {format_turn(treasury_leaders['turn'])}, "
            f"{format_faction_list([get_faction_display_name(world, name) for name in treasury_leaders['leaders']])} held the opening treasury lead "
            f"at {treasury_leaders['treasury']}."
        )

    return lines


def summarize_faction_behavior(world):
    """Returns one sentence per faction describing its overall behavior."""
    faction_event_counts = get_faction_event_counts(world)
    lines = []

    for faction_name, counts in faction_event_counts.items():
        expand_count = counts["expand"]
        invest_count = counts["invest"]

        if expand_count > invest_count:
            style = "favored expansion over development"
        elif invest_count > expand_count:
            style = "favored development over expansion"
        else:
            style = "balanced expansion and development evenly"

        lines.append(
            f"{get_faction_display_name(world, faction_name)} expanded {expand_count} times and invested {invest_count} times, "
            f"and generally {style}."
        )

    return lines


def get_faction_trajectory_sentence(world, faction_name):
    """Returns one concise sentence describing a faction's arc."""
    history = get_faction_metrics_history(world, faction_name)
    standings = get_final_standings(world)
    faction_display_name = get_faction_display_name(world, faction_name)

    if not history:
        return f"{faction_display_name} had too little recorded activity to describe a clear trajectory."

    phase_ranges = get_phase_ranges(len(history))
    early_start, early_end = phase_ranges[0][1], phase_ranges[0][2]
    early_history = history[early_start - 1:early_end]
    mid_history = []
    if len(phase_ranges) >= 2:
        mid_start, mid_end = phase_ranges[1][1], phase_ranges[1][2]
        mid_history = history[mid_start - 1:mid_end]
    final_snapshot = history[-1]
    peak_snapshot = max(history, key=lambda entry: (entry["regions"], entry["treasury"]))
    total_attacks = sum(entry["attacks"] for entry in history)
    treasury_gain = final_snapshot["treasury"] - history[0]["treasury"]

    final_rank = next(
        index + 1
        for index, standing in enumerate(standings)
        if standing["faction"] == faction_name
    )
    early_posture = describe_early_posture(early_history)
    if peak_snapshot["regions"] > final_snapshot["regions"] + 1:
        midgame = (
            f"peaked at {format_count_noun(peak_snapshot['regions'], 'region')} on turn {peak_snapshot['turn']} "
            f"before slipping to {format_count_noun(final_snapshot['regions'], 'region')}"
        )
    elif final_snapshot["regions"] > early_history[-1]["regions"]:
        midgame = (
            f"built steadily past the opening, reaching {format_count_noun(final_snapshot['regions'], 'region')} "
            f"by turn {final_snapshot['turn']}"
        )
    else:
        midgame = describe_midgame(mid_history)

    if final_rank == 1 and final_snapshot["regions"] > 0:
        ending = (
            f"and finished first with {format_count_noun(final_snapshot['regions'], 'region')}, "
            f"{final_snapshot['treasury']} treasury, and {total_attacks} total attacks"
        )
    elif final_snapshot["regions"] == 0:
        ending = (
            f"and closed on {final_snapshot['treasury']} treasury without territory after {total_attacks} attacks"
        )
    else:
        ending = (
            f"and finished rank {final_rank} on {final_snapshot['treasury']} treasury with "
            f"{format_count_noun(final_snapshot['regions'], 'region')}"
        )
        if treasury_gain > 0:
            ending += f" after gaining {treasury_gain} treasury overall"
    return f"{faction_display_name} {early_posture}, {midgame}, {ending}."


def summarize_faction_trajectories(world):
    """Returns one sentence per faction describing its overall arc."""
    return [
        get_faction_trajectory_sentence(world, faction_name)
        for faction_name in world.factions
    ]


def summarize_final_standings(world):
    """Returns a short standings summary."""
    standings = get_final_standings(world)
    lines = []

    if standings:
        winner = standings[0]
        lines.append(
            f"{get_faction_display_name(world, winner['faction'])} finished first with a treasury of {winner['treasury']} "
            f"and control of {format_count_noun(winner['owned_regions'], 'region')}."
        )

    for standing in standings[1:]:
        lines.append(
            f"{get_faction_display_name(world, standing['faction'])} ended with a treasury of {standing['treasury']} "
            f"and {format_count_noun(standing['owned_regions'], 'region')}."
        )

    return lines


TURNING_POINT_BASE_SCORE = {
    "collapse": 100,
    "phase_break": 80,
    "leader_change": 65,
    "economic_shift": 55,
    "border_swing": 35,
}

TURNING_POINT_MIN_THRESHOLD = {
    "full_domination": 70,
    "midgame_break": 65,
    "late_snowball": 65,
    "early_snowball": 65,
    "economic_win": 55,
    "balanced_contest": 60,
}

TURNING_POINT_NEAR_THRESHOLD_DELTA = 10
BALANCED_CONTEST_STRONG_THRESHOLD = 85
ECONOMIC_WIN_STRONG_THRESHOLD = 65


def get_state_rankings(state):
    """Returns faction standings for a replay state."""
    return sorted(
        state["treasuries"].items(),
        key=lambda item: (item[1], state["region_counts"].get(item[0], 0)),
        reverse=True,
    )


def get_active_faction_count_from_state(state):
    """Returns how many factions still hold territory in a replay state."""
    return sum(1 for regions in state["region_counts"].values() if regions > 0)


def get_unique_metric_leader(primary_values, secondary_values):
    """Returns the sole leader for one metric map, or None on ties."""
    rankings = sorted(
        primary_values.items(),
        key=lambda item: (item[1], secondary_values.get(item[0], 0)),
        reverse=True,
    )
    if not rankings:
        return None
    if len(rankings) == 1:
        return rankings[0][0]
    if rankings[0][1] == rankings[1][1]:
        return None
    return rankings[0][0]


def get_unique_treasury_leader_from_state(state):
    """Returns the sole treasury leader for a replay state."""
    return get_unique_metric_leader(state["treasuries"], state["region_counts"])


def get_unique_region_leader_from_state(state):
    """Returns the sole region leader for a replay state."""
    return get_unique_metric_leader(state["region_counts"], state["treasuries"])


def get_metric_margin(values):
    """Returns the top-two margin for one metric map."""
    ranked_values = sorted(values.values(), reverse=True)
    if not ranked_values:
        return 0
    if len(ranked_values) == 1:
        return ranked_values[0]
    return ranked_values[0] - ranked_values[1]


def get_snapshot_by_turn(world, turn_number):
    """Returns the metrics snapshot for one one-based turn, if present."""
    for snapshot in world.metrics:
        if snapshot["turn"] == turn_number:
            return snapshot
    return None


def get_metric_leader_from_snapshot(snapshot, metric_name):
    """Returns the sole leader for a snapshot metric, or None."""
    if snapshot is None:
        return None
    values = {
        faction_name: faction_metrics[metric_name]
        for faction_name, faction_metrics in snapshot["factions"].items()
    }
    if metric_name == "treasury":
        secondary = {
            faction_name: faction_metrics["regions"]
            for faction_name, faction_metrics in snapshot["factions"].items()
        }
    else:
        secondary = {
            faction_name: faction_metrics["treasury"]
            for faction_name, faction_metrics in snapshot["factions"].items()
        }
    return get_unique_metric_leader(values, secondary)


def leader_persists_for_two_turns(world, turn_number, faction_name, metric_name):
    """Returns whether a new leader remains clear for the next two turns."""
    future_turns = [turn_number + 1, turn_number + 2]
    checked = 0
    for future_turn in future_turns:
        snapshot = get_snapshot_by_turn(world, future_turn)
        if snapshot is None:
            continue
        checked += 1
        if get_metric_leader_from_snapshot(snapshot, metric_name) != faction_name:
            return False
    return checked > 0


def winner_never_led_in_regions(world, winner):
    """Returns whether the eventual winner never held a sole region lead."""
    for snapshot in world.metrics:
        if get_metric_leader_from_snapshot(snapshot, "regions") == winner:
            return False
    return True


def get_phase_name_for_turn(turn_number, phase_analyses):
    """Returns the phase containing one one-based turn number."""
    for analysis in phase_analyses:
        if analysis["start_turn"] <= turn_number <= analysis["end_turn"]:
            return analysis["phase_name"].lower()
    return "late"


def get_phase_leader(analysis):
    """Returns the sole region leader at the end of a phase, if one exists."""
    return get_metric_leader_from_snapshot(analysis["end_snapshot"], "regions")


def get_phase_break_candidate(analysis, previous_analysis, final_winner, phase_analyses):
    """Builds one deterministic phase-break candidate when warranted."""
    biggest_gain = analysis["biggest_gain"]
    biggest_loss = analysis["biggest_loss"]
    gain_value = analysis["region_deltas"][biggest_gain]
    loss_value = abs(min(0, analysis["region_deltas"][biggest_loss]))
    region_swing = max(gain_value, loss_value)
    leader = get_phase_leader(analysis)

    if region_swing < 3 and analysis["lead_region_margin"] < 3:
        return None

    clear_leader_before = get_phase_leader(previous_analysis) if previous_analysis is not None else None
    created_new_clear_leader = leader is not None and leader != clear_leader_before
    lead_persisted = (
        leader is not None
        and leader == final_winner
        and all(
            get_phase_leader(later_analysis) in {None, leader}
            for later_analysis in phase_analyses
            if later_analysis["start_turn"] >= analysis["start_turn"]
        )
    )
    followed_close_early = previous_analysis is not None and previous_analysis["close_contest"]

    score = TURNING_POINT_BASE_SCORE["phase_break"] + (8 * region_swing)
    if created_new_clear_leader:
        score += 10
    if lead_persisted:
        score += 10
    if followed_close_early:
        score += 5

    if loss_value > 0:
        line = (
            f"{analysis['phase_name']} phase break: {biggest_gain} gained {format_count_noun(gain_value, 'region')} "
            f"while {biggest_loss} lost {format_count_noun(loss_value, 'region')}."
        )
    else:
        line = (
            f"{analysis['phase_name']} phase break: {biggest_gain} gained {format_count_noun(gain_value, 'region')} "
            f"and opened the clearest territorial swing of the run."
        )

    return {
        "turn": analysis["end_turn"],
        "faction": biggest_gain,
        "factions": tuple(dict.fromkeys([biggest_gain, biggest_loss])),
        "region": None,
        "event_class": "phase_break",
        "importance_score": score,
        "line": line,
        "phase_name": analysis["phase_name"].lower(),
        "kind": "phase_break",
        "winner": biggest_gain,
        "leader_metric": "regions",
        "created_new_clear_leader": created_new_clear_leader,
        "lead_persisted": lead_persisted,
    }


def get_turning_point_line(entry):
    """Returns the final user-facing line for a turning-point entry."""
    phase_name = entry.get("phase_name", "mid").capitalize()
    event_class = entry["event_class"]

    if event_class == "collapse":
        defender = entry.get("defender") or "a rival"
        return (
            f"{phase_name} collapse: {entry['faction']}'s capture of {entry['region']} "
            f"eliminated {defender}'s last territorial hold."
        )
    if event_class == "phase_break":
        return entry["line"]
    if event_class == "leader_change":
        if entry.get("leader_metric") == "treasury":
            return f"{phase_name} leader change: {entry['faction']} took the treasury lead."
        return f"{phase_name} leader change: {entry['faction']} took the territorial lead."
    if event_class == "economic_shift":
        return (
            f"{phase_name} economic shift: {entry['faction']} created a treasury edge "
            f"that became central to the finish."
        )
    if event_class == "border_swing":
        return (
            f"{phase_name} border swing: {entry['faction']}'s capture of {entry['region']} "
            f"flipped an important frontline region."
        )
    return None


def get_event_candidate(world, event, event_summary, before_state, after_state, final_winner, outcome_type, phase_analyses):
    """Classifies one major event into a deterministic turning-point candidate."""
    actor = event_summary["faction"]
    region = event_summary["region"]
    defender = event_summary.get("defender") or event_summary.get("owner_before")
    before_rankings = get_state_rankings(before_state)
    before_treasury_leader = get_unique_treasury_leader_from_state(before_state)
    after_treasury_leader = get_unique_treasury_leader_from_state(after_state)
    before_region_leader = get_unique_region_leader_from_state(before_state)
    after_region_leader = get_unique_region_leader_from_state(after_state)
    phase_name = event_summary.get("phase_name") or get_phase_name_for_turn(
        format_turn(event_summary["turn"]),
        phase_analyses,
    )
    event_class = None
    score = 0
    leader_metric = None
    triggered_leader_change = False
    defender_rank_before = None

    if (
        event_summary["type"] == "attack"
        and event_summary.get("success", False)
        and defender in before_state["region_counts"]
        and before_state["region_counts"][defender] > 0
        and after_state["region_counts"].get(defender, 0) == 0
    ):
        event_class = "collapse"
        score = TURNING_POINT_BASE_SCORE["collapse"]
        eliminated_regions = before_state["region_counts"][defender]
        score += 15 * eliminated_regions
        defender_rank_before = next(
            (
                index + 1
                for index, (faction_name, _treasury) in enumerate(before_rankings)
                if faction_name == defender
            ),
            None,
        )
        if defender_rank_before in {1, 2}:
            score += 10
        if get_active_faction_count_from_state(after_state) < get_active_faction_count_from_state(before_state):
            score += 8
        if actor == final_winner:
            score += 8
    else:
        if after_treasury_leader != before_treasury_leader and after_treasury_leader == actor:
            event_class = "leader_change"
            leader_metric = "treasury"
        elif after_region_leader != before_region_leader and after_region_leader == actor:
            event_class = "leader_change"
            leader_metric = "regions"
        else:
            before_treasury_margin = get_metric_margin(before_state["treasuries"])
            after_treasury_margin = get_metric_margin(after_state["treasuries"])
            if (
                after_treasury_leader == actor
                and after_treasury_margin > before_treasury_margin
                and (
                    event_summary["type"] == "invest"
                    or "strengthened economic lead" in event_summary.get("importance_reasons", [])
                    or after_treasury_margin >= 3
                )
            ):
                event_class = "economic_shift"

        if event_class == "leader_change":
            score = TURNING_POINT_BASE_SCORE["leader_change"]
            if actor == final_winner:
                score += 12
            if leader_persists_for_two_turns(world, format_turn(event_summary["turn"]), actor, leader_metric):
                score += 8
            triggered_leader_change = True
        elif event_class == "economic_shift":
            score = TURNING_POINT_BASE_SCORE["economic_shift"]
            if outcome_type == "economic_win":
                score += 10
            if actor == final_winner and after_treasury_leader == actor:
                score += 8
            if actor == final_winner and winner_never_led_in_regions(world, final_winner):
                score += 6
        elif event_summary["type"] == "attack" and event_summary.get("success", False):
            event_class = "border_swing"
            score = TURNING_POINT_BASE_SCORE["border_swing"]
            if region in world.regions and len(world.regions[region].neighbors) >= 4:
                score += 8
            if after_treasury_leader != before_treasury_leader or after_region_leader != before_region_leader:
                score += 8
                triggered_leader_change = True

    if event_class is None:
        return None

    line = get_turning_point_line(
        {
            "event_class": event_class,
            "phase_name": phase_name,
            "faction": actor,
            "defender": defender,
            "region": region,
            "leader_metric": leader_metric,
        }
    )

    return {
        "turn": format_turn(event_summary["turn"]),
        "faction": actor,
        "factions": tuple(dict.fromkeys(name for name in [actor, defender] if name)),
        "region": region,
        "event_class": event_class,
        "importance_score": score,
        "line": line,
        "phase_name": phase_name,
        "kind": event_class,
        "winner": actor,
        "defender": defender,
        "defender_rank_before": defender_rank_before if event_class == "collapse" else None,
        "leader_metric": leader_metric,
        "triggered_leader_change": triggered_leader_change,
    }


def get_turning_point_priority(entry, outcome_type, final_winner):
    """Returns the outcome-specific selection priority for one candidate."""
    event_class = entry["event_class"]
    phase_name = entry.get("phase_name")
    winner_aligned = entry.get("faction") == final_winner
    winner_bonus = 0 if winner_aligned else 2

    if outcome_type == "full_domination":
        order = {"collapse": 0, "phase_break": 1, "leader_change": 2, "economic_shift": 3, "border_swing": 4}
        return order[event_class] + winner_bonus

    if outcome_type == "midgame_break":
        if event_class == "phase_break" and phase_name == "mid":
            return 0 if winner_aligned else 2
        if event_class in {"collapse", "leader_change"}:
            return 1 if winner_aligned else 3
        if event_class == "phase_break":
            return 2 if winner_aligned else 4
        if event_class == "economic_shift":
            return 3 if winner_aligned else 5
        return 6

    if outcome_type == "late_snowball":
        if event_class == "phase_break" and phase_name == "late":
            return 0 if winner_aligned else 2
        if event_class in {"collapse", "leader_change"} and phase_name == "late":
            return 1 if winner_aligned else 3
        if event_class == "phase_break":
            return 2 if winner_aligned else 4
        if event_class in {"collapse", "leader_change"}:
            return 3 if winner_aligned else 5
        if event_class == "economic_shift":
            return 4 if winner_aligned else 6
        return 7

    if outcome_type == "economic_win":
        if event_class == "economic_shift":
            return 0 if winner_aligned else 2
        if event_class == "leader_change" and entry.get("leader_metric") == "treasury":
            return 1 if winner_aligned else 3
        if (
            event_class == "collapse"
            and entry["winner"] == entry["faction"]
            and entry.get("defender_rank_before") in {1, 2}
        ):
            return 2 if winner_aligned else 4
        return 6

    if outcome_type == "balanced_contest":
        if event_class in {"leader_change", "economic_shift"} and phase_name == "late":
            return 0 if winner_aligned else 1
        if event_class in {"leader_change", "economic_shift"}:
            return 1 if winner_aligned else 2
        if event_class == "collapse":
            return 2 if winner_aligned else 3
        if event_class == "phase_break":
            return 3 if winner_aligned else 4
        return 5

    return 6


def entries_conflict(entry, other_entry):
    """Returns whether two turning points are redundant or contradictory."""
    same_region = (
        entry.get("region") is not None
        and other_entry.get("region") is not None
        and entry.get("region") == other_entry.get("region")
    )
    turn_gap = abs(entry["turn"] - other_entry["turn"])
    same_class = entry["event_class"] == other_entry["event_class"]
    shared_factions = set(entry.get("factions", ())) & set(other_entry.get("factions", ()))

    if same_region and turn_gap <= 2:
        return True
    if turn_gap <= 2 and (same_region or shared_factions):
        return True
    if turn_gap <= 2 and same_class and shared_factions:
        return True
    return False


def select_non_conflicting_entries(entries):
    """Returns entries with lower-scoring conflicts removed."""
    selected = []
    for entry in sorted(
        entries,
        key=lambda item: (-item["importance_score"], item["turn"], item["event_class"], item["faction"]),
    ):
        if any(entries_conflict(entry, existing) for existing in selected):
            continue
        selected.append(entry)
    return selected


def dedupe_collapse_candidates(entries):
    """Keeps at most one collapse per eliminated faction."""
    best_by_defender = {}
    non_collapse_entries = []

    for entry in entries:
        if entry["event_class"] != "collapse" or not entry.get("defender"):
            non_collapse_entries.append(entry)
            continue

        defender = entry["defender"]
        current_best = best_by_defender.get(defender)
        if current_best is None or (
            entry["importance_score"],
            -entry["turn"],
            entry["faction"],
        ) > (
            current_best["importance_score"],
            -current_best["turn"],
            current_best["faction"],
        ):
            best_by_defender[defender] = entry

    return non_collapse_entries + list(best_by_defender.values())


def are_same_causal_chain(entry, other_entry):
    """Returns whether two entries are alternate versions of the same story beat."""
    if abs(entry["turn"] - other_entry["turn"]) > 2:
        return False

    same_winner = entry.get("faction") == other_entry.get("faction")
    same_defender = entry.get("defender") and entry.get("defender") == other_entry.get("defender")
    same_region = entry.get("region") and entry.get("region") == other_entry.get("region")
    shared_factions = set(entry.get("factions", ())) & set(other_entry.get("factions", ()))

    if entry["event_class"] == "collapse" and other_entry["event_class"] == "collapse":
        return same_defender or (same_winner and shared_factions)

    if same_winner and (same_defender or same_region):
        return True

    if (
        same_winner
        and entry["event_class"] in {"leader_change", "border_swing", "economic_shift"}
        and other_entry["event_class"] in {"leader_change", "border_swing", "economic_shift"}
    ):
        return True

    return False


def dedupe_same_chain_entries(entries):
    """Collapses nearby same-chain candidates down to one representative."""
    selected = []
    for entry in sorted(
        entries,
        key=lambda item: (-item["importance_score"], item["turn"], item["event_class"], item["faction"]),
    ):
        if any(are_same_causal_chain(entry, existing) for existing in selected):
            continue
        selected.append(entry)
    return selected


def is_treasury_relevant_entry(entry, final_winner):
    """Returns whether an entry materially helps explain an economic win."""
    if entry["event_class"] == "economic_shift":
        return True
    if entry["event_class"] == "leader_change":
        return entry.get("leader_metric") == "treasury"
    if entry["event_class"] == "collapse":
        return (
            entry.get("faction") == final_winner
            and entry.get("defender_rank_before") in {1, 2}
        )
    return False


def get_selected_turning_point_entries(world, phase_analyses):
    """Returns the top 0-2 deterministic turning-point entries."""
    ensure_event_importance_scores(world)
    standings = get_final_standings(world)
    if not standings:
        return []

    outcome_type = classify_outcome_type(world)
    final_winner = standings[0]["faction"]
    threshold = TURNING_POINT_MIN_THRESHOLD[outcome_type]
    candidates = []

    for index, analysis in enumerate(phase_analyses):
        previous_analysis = phase_analyses[index - 1] if index > 0 else None
        candidate = get_phase_break_candidate(
            analysis=analysis,
            previous_analysis=previous_analysis,
            final_winner=final_winner,
            phase_analyses=phase_analyses,
        )
        if candidate is not None:
            candidates.append(candidate)

    replay_state = build_replay_state(world)
    for event in world.events:
        before_state = clone_replay_state(replay_state)
        after_state = apply_event_to_replay_state(event, replay_state)
        if event.type in {"expand", "attack", "invest"}:
            event_summary = summarize_major_event(event, world=world)
            candidate = get_event_candidate(
                world=world,
                event=event,
                event_summary=event_summary,
                before_state=before_state,
                after_state=after_state,
                final_winner=final_winner,
                outcome_type=outcome_type,
                phase_analyses=phase_analyses,
            )
            if candidate is not None:
                candidates.append(candidate)
        replay_state = after_state

    collapse_candidates_all = [
        candidate for candidate in candidates
        if candidate["event_class"] == "collapse"
    ]
    for candidate in candidates:
        if candidate["event_class"] != "border_swing":
            continue
        if any(
            0 < collapse["turn"] - candidate["turn"] <= 1
            and (
                candidate.get("region") == collapse.get("region")
                or set(candidate.get("factions", ())) & set(collapse.get("factions", ()))
            )
            for collapse in collapse_candidates_all
        ):
            candidate["importance_score"] += 10

    thresholded_candidates = [
        candidate for candidate in candidates
        if candidate["importance_score"] >= threshold
    ]

    if not thresholded_candidates:
        if outcome_type in {"balanced_contest", "economic_win"}:
            return []
        if not candidates:
            return []
        best_candidate = max(
            candidates,
            key=lambda item: (item["importance_score"], -item["turn"]),
        )
        if threshold - best_candidate["importance_score"] > TURNING_POINT_NEAR_THRESHOLD_DELTA:
            return []
        thresholded_candidates = [best_candidate]

    thresholded_candidates = dedupe_collapse_candidates(thresholded_candidates)
    thresholded_candidates = dedupe_same_chain_entries(thresholded_candidates)

    if outcome_type == "balanced_contest":
        thresholded_candidates = [
            candidate for candidate in thresholded_candidates
            if candidate["importance_score"] >= BALANCED_CONTEST_STRONG_THRESHOLD
            and (
                candidate["event_class"] == "collapse"
                or (
                    candidate["event_class"] in {"leader_change", "economic_shift"}
                    and candidate.get("phase_name") == "late"
                )
            )
        ]
        if not thresholded_candidates:
            return []

    if outcome_type == "economic_win":
        treasury_relevant_candidates = [
            candidate for candidate in thresholded_candidates
            if is_treasury_relevant_entry(candidate, final_winner)
        ]
        if not treasury_relevant_candidates:
            return []
        thresholded_candidates = [
            candidate for candidate in treasury_relevant_candidates
            if candidate["importance_score"] >= ECONOMIC_WIN_STRONG_THRESHOLD
        ]
        if not thresholded_candidates:
            return []

    collapse_candidates = [
        candidate for candidate in thresholded_candidates
        if candidate["event_class"] == "collapse"
    ]
    filtered_candidates = []
    for candidate in thresholded_candidates:
        if (
            outcome_type == "economic_win"
            and candidate["event_class"] == "collapse"
            and candidate["faction"] != final_winner
        ):
            continue
        if (
            collapse_candidates
            and candidate["event_class"] == "border_swing"
            and not candidate.get("triggered_leader_change", False)
            and any(
                abs(candidate["turn"] - collapse["turn"]) <= 2
                and (
                    candidate.get("region") == collapse.get("region")
                    or set(candidate.get("factions", ())) & set(collapse.get("factions", ()))
                )
                for collapse in collapse_candidates
            )
        ):
            continue
        if outcome_type == "full_domination" and collapse_candidates and candidate["event_class"] == "border_swing":
            continue
        filtered_candidates.append(candidate)

    clustered_candidates = select_non_conflicting_entries(filtered_candidates)

    ranked_candidates = sorted(
        clustered_candidates,
        key=lambda item: (
            get_turning_point_priority(item, outcome_type, final_winner),
            -item["importance_score"],
            item["turn"],
            item["event_class"],
            item["faction"],
        ),
    )

    selected = []
    for candidate in ranked_candidates:
        if (
            outcome_type in {"full_domination", "midgame_break", "late_snowball"}
            and candidate["event_class"] == "phase_break"
            and candidate["faction"] != final_winner
            and any(
                existing["event_class"] in {"phase_break", "collapse", "leader_change"}
                and existing["faction"] == final_winner
                for existing in selected
            )
        ):
            continue
        if any(entries_conflict(candidate, existing) for existing in selected):
            continue
        selected.append(candidate)
        if len(selected) == 2:
            break

    return selected


def summarize_turning_points(world, phase_analyses):
    """Returns 0-2 concise lines describing decisive shifts in the run."""
    return [entry["line"] for entry in get_selected_turning_point_entries(world, phase_analyses)]


def classify_outcome_type(world):
    """Classifies the completed simulation into one outcome type."""
    standings = get_final_standings(world)
    if not standings:
        return "balanced_contest"

    total_regions = len(world.regions)
    winner = standings[0]["faction"]
    winner_regions = standings[0]["owned_regions"]
    max_final_regions = max(standing["owned_regions"] for standing in standings)
    other_regions = [standing["owned_regions"] for standing in standings[1:]]
    alive_end = [standing for standing in standings if standing["owned_regions"] > 0]
    nonzero_regions = [standing["owned_regions"] for standing in standings if standing["owned_regions"] > 0]
    region_spread_alive = (
        max(nonzero_regions) - min(nonzero_regions) if len(nonzero_regions) >= 2 else 0
    )

    phase_analyses, _phase_summaries = summarize_phases(world)
    early_analysis = phase_analyses[0] if len(phase_analyses) > 0 else None
    mid_analysis = phase_analyses[1] if len(phase_analyses) > 1 else None
    late_analysis = phase_analyses[2] if len(phase_analyses) > 2 else None

    if (
        winner_regions >= max(1, int(total_regions * 0.9))
        and all(region_count == 0 for region_count in other_regions)
    ):
        return "full_domination"

    if winner_regions < max_final_regions:
        return "economic_win"

    if (
        len(alive_end) >= 3
        and region_spread_alive <= 3
        and all(
            analysis["lead_region_margin"] <= 2 and not analysis["stable_board"]
            for analysis in phase_analyses
            if analysis is not None
        )
    ):
        return "balanced_contest"

    if early_analysis is not None:
        early_winner = early_analysis["rankings"][0][0]
        early_runaway = (
            early_winner == winner
            and early_analysis["lead_region_margin"] >= 3
            and early_analysis["region_deltas"].get(winner, 0) >= 3
        )
        sustained_control = all(
            analysis is None
            or (
                analysis["rankings"][0][0] == winner
                and analysis["lead_region_margin"] >= 2
                and not analysis["close_contest"]
            )
            for analysis in (mid_analysis, late_analysis)
        )
        if early_runaway and sustained_control:
            return "early_snowball"

    if mid_analysis is not None and early_analysis is not None:
        early_balanced = early_analysis["close_contest"] or early_analysis["lead_region_margin"] <= 2
        mid_break = (
            mid_analysis["rankings"][0][0] == winner
            and (
                mid_analysis["lead_region_margin"] >= 3
                or mid_analysis["region_deltas"].get(winner, 0) >= 3
            )
        )
        late_confirmed = late_analysis is None or late_analysis["rankings"][0][0] == winner
        if early_balanced and mid_break and late_confirmed:
            return "midgame_break"

    if late_analysis is not None and early_analysis is not None:
        early_competitive = early_analysis["close_contest"] or early_analysis["lead_region_margin"] <= 2
        mid_competitive = (
            mid_analysis is None
            or mid_analysis["close_contest"]
            or mid_analysis["lead_region_margin"] <= 2
        )
        late_break = (
            late_analysis["rankings"][0][0] == winner
            and (
                late_analysis["lead_region_margin"] >= 3
                or late_analysis["region_deltas"].get(winner, 0) >= 3
            )
        )
        if early_competitive and mid_competitive and late_break:
            return "late_snowball"

    if len(alive_end) >= 3 and region_spread_alive <= 3:
        return "balanced_contest"

    if mid_analysis is not None and mid_analysis["rankings"][0][0] == winner:
        return "midgame_break"

    if early_analysis is not None and early_analysis["rankings"][0][0] == winner:
        return "early_snowball"

    return "late_snowball"


def summarize_outcome_type(world):
    """Returns a short outcome type line for the completed simulation."""
    return [f"Outcome type: {classify_outcome_type(world)}."]


def get_winner_decisive_events(winner_events):
    """Returns winner-linked collapse and break signals for interpretation."""
    collapse_events = [
        event
        for event in winner_events
        if event.get("analysis_importance_tier") == "VERY_HIGH"
        and any(
            reason in event.get("importance_reasons", [])
            for reason in ("triggered rival elimination", "triggered rival collapse")
        )
    ]
    return collapse_events


def get_outcome_specific_setup_line(
    outcome_type,
    winner,
    alive_end,
    final_region_spread,
    early_analysis,
    mid_analysis,
    late_analysis,
):
    """Returns the opening interpretation line for one outcome type."""
    if outcome_type == "full_domination":
        return "One faction eventually absorbed the board, turning the later stages into consolidation rather than continued competition."
    if outcome_type == "midgame_break" and mid_analysis is not None:
        return (
            f"The opening stayed contested, but {winner} broke the game open in the middle turns "
            f"and built a durable territorial edge."
        )
    if outcome_type == "late_snowball" and late_analysis is not None:
        return (
            f"No faction controlled the run early, but {winner} stayed close until the late phase "
            f"and then separated decisively."
        )
    if outcome_type == "economic_win":
        return (
            f"Territory alone did not decide this run; {winner} finished first on treasury "
            f"without holding the largest empire at the end."
        )
    if outcome_type == "balanced_contest":
        return (
            f"No faction broke the map open. The run stayed competitive to the end, with "
            f"{format_count_noun(len(alive_end), 'faction')} still alive and only {final_region_spread}-region variation across the final board."
        )
    if outcome_type == "early_snowball" and early_analysis is not None:
        return (
            f"The map tilted early when {winner} established an opening lead and never gave the field a clean chance to recover."
        )
    return None


def build_outcome_specific_driver_line(
    world,
    winner,
    outcome_type,
    phase_analyses,
    standings,
):
    """Builds an outcome-specific cause-and-effect explanation."""
    winner_name = get_faction_display_name(world, winner)
    winner_events = [
        event for event in get_scored_major_events(world, minimum_score=0.0)
        if event["faction"] == winner
    ]
    collapse_events = get_winner_decisive_events(winner_events)
    phase_breaks = [
        entry for entry in get_selected_turning_point_entries(world, phase_analyses)
        if entry.get("kind") == "phase_break" and entry.get("winner") == winner
    ]
    winner_regions = standings[0]["owned_regions"]
    winner_treasury = standings[0]["treasury"]
    runner_up = standings[1] if len(standings) > 1 else None
    max_regions = max(standing["owned_regions"] for standing in standings) if standings else 0
    larger_rivals = [
        get_faction_display_name(world, standing["faction"])
        for standing in standings[1:]
        if standing["owned_regions"] > winner_regions
    ]
    alive_end = [standing for standing in standings if standing["owned_regions"] > 0]
    mid_analysis = phase_analyses[1] if len(phase_analyses) > 1 else None
    late_analysis = phase_analyses[2] if len(phase_analyses) > 2 else None

    if outcome_type == "full_domination":
        if collapse_events:
            rival = collapse_events[0].get("defender") or collapse_events[0].get("owner_before") or "a key rival"
            rival = get_faction_display_name(world, rival)
            phase_name = collapse_events[0].get("phase_name", "mid")
            return (
                f"{winner_name} eliminated {rival} in the {phase_name} phase, reduced the competitive field, "
                f"converted that advantage into control of the board, and then consolidated into full domination."
            )
        if phase_breaks:
            phase_name = phase_breaks[0]["phase_name"].lower()
            return (
                f"{winner_name} created the decisive break in the {phase_name} phase, turned that lead into control of the board, "
                f"and then consolidated the map."
            )
        return (
            f"{winner_name} took control of the board, removed the remaining rivals from contention, "
            f"and finished on {format_count_noun(winner_regions, 'region')} with full domination."
        )

    if outcome_type == "midgame_break":
        if mid_analysis is not None:
            return (
                f"{winner_name} turned the contested opening into a decisive middle-phase swing, built a durable territorial lead, "
                f"and carried that edge to the finish."
            )
        if phase_breaks:
            return (
                f"{winner_name} created the decisive break after an even opening, built a durable lead, "
                f"and never let the field close the gap."
            )
        return (
            f"{winner_name} found the decisive break in the middle portion of the run and converted it into a stable winning position."
        )

    if outcome_type == "late_snowball":
        if late_analysis is not None:
            return (
                f"The board stayed crowded into the late phase, but {winner_name} separated only at the end, "
                f"opened a decisive lead, and closed out the run."
            )
        return (
            f"No early leader held control for long; {winner_name} stayed within reach and separated only in the closing turns."
        )

    if outcome_type == "economic_win":
        if larger_rivals:
            return (
                f"{winner_name} did not win on map share. It finished first on treasury while "
                f"{format_faction_list(larger_rivals)} held more territory but failed to turn that size into enough net income."
            )
        if runner_up is not None and runner_up["owned_regions"] >= winner_regions:
            return (
                f"{winner_name} won on treasury rather than territory, edging out rivals that matched or exceeded its map share."
            )
        return (
            f"{winner_name} kept the stronger treasury position, and the larger empires never converted their territory into a better economic finish."
        )

    if outcome_type == "balanced_contest":
        return (
            f"No decisive collapse or phase break separated the field. {winner_name} edged ahead in a finish that remained close across "
            f"{format_count_noun(len(alive_end), 'surviving faction')}."
        )

    if outcome_type == "early_snowball":
        return (
            f"{winner_name} established the early lead, denied the field a meaningful recovery window, and converted that start into a lasting win."
        )

    if runner_up is not None:
        return (
            f"{winner_name} finished ahead of {get_faction_display_name(world, runner_up['faction'])} by turning a narrow lead into the stronger final position on treasury and territory."
        )

    return None


def build_outcome_specific_result_line(world, outcome_type, standings):
    """Returns a concise outcome-specific result line."""
    if not standings:
        return None

    winner = standings[0]["faction"]
    winner_name = get_faction_display_name(world, winner)
    winner_regions = standings[0]["owned_regions"]
    winner_treasury = standings[0]["treasury"]
    runner_up = standings[1] if len(standings) > 1 else None

    if outcome_type == "full_domination":
        return (
            f"By the finish, {winner_name} held {format_count_noun(winner_regions, 'region')} and {winner_treasury} treasury while every rival had been reduced to zero territory."
        )
    if outcome_type == "economic_win":
        max_regions = max(standing["owned_regions"] for standing in standings)
        return (
            f"{winner_name} finished first on {winner_treasury} treasury with {format_count_noun(winner_regions, 'region')}, "
            f"while the largest empire finished on {format_count_noun(max_regions, 'region')}."
        )
    if outcome_type == "balanced_contest" and runner_up is not None:
        treasury_margin = winner_treasury - runner_up["treasury"]
        return (
            f"The final margin stayed narrow: {winner_name} beat {get_faction_display_name(world, runner_up['faction'])} by {treasury_margin} treasury."
        )
    if outcome_type in {"midgame_break", "late_snowball", "early_snowball"} and runner_up is not None:
        return (
            f"That break left {winner_name} ahead at the finish with {format_count_noun(winner_regions, 'region')} and {winner_treasury} treasury."
        )
    return None


def build_causal_chain(world, winner, outcome_type, phase_analyses):
    """Builds a short cause-and-effect summary for the winner's path."""
    standings = get_final_standings(world)
    line = build_outcome_specific_driver_line(
        world=world,
        winner=winner,
        outcome_type=outcome_type,
        phase_analyses=phase_analyses,
        standings=standings,
    )
    if line is None:
        return None
    return sentence_case(line)


def build_ai_phase_summary(world, analysis):
    """Returns one compact phase summary string for the AI payload."""
    if analysis is None:
        return None

    leader = analysis["rankings"][0][0]
    leader_name = get_faction_display_name(world, leader)
    gain_name = analysis["biggest_gain"]
    gain_value = analysis["region_deltas"][gain_name]
    gain_display = get_faction_display_name(world, gain_name)
    loss_name = analysis["biggest_loss"]
    loss_value = analysis["region_deltas"][loss_name]
    loss_display = get_faction_display_name(world, loss_name)
    parts = [f"{leader_name} strongest"]

    if analysis["stable_board"]:
        parts.append("territorial control stabilized")
    elif analysis["close_contest"]:
        parts.append("the board remained contested")
    elif analysis["lead_region_margin"] >= 3:
        parts.append(
            f"{leader_name} finished {format_count_noun(analysis['lead_region_margin'], 'region')} clear"
        )

    if gain_value > 0:
        shift_text = f"{gain_display} gained {format_count_noun(gain_value, 'region')}"
        if loss_value < 0:
            shift_text += (
                f" while {loss_display} lost {format_count_noun(abs(loss_value), 'region')}"
            )
        parts.append(shift_text)

    return "; ".join(parts) + "."


def build_ai_interpretation_summary(world, phase_analyses, standings, outcome_type):
    """Builds the compact structured payload sent to the AI layer."""
    winner = standings[0]["faction"]
    winner_name = get_faction_display_name(world, winner)
    runner_up = standings[1] if len(standings) > 1 else None
    turning_points = summarize_turning_points(world, phase_analyses)

    summary = {
        "map": getattr(world, "map_name", "") or "unknown_map",
        "turns": len(world.metrics),
        "outcome_type": outcome_type,
        "winner": winner_name,
        "winner_strategy": world.factions[winner].doctrine_label,
        "turning_points": turning_points[:2],
        "phase_summary": {
            "early": build_ai_phase_summary(world, phase_analyses[0] if len(phase_analyses) > 0 else None),
            "mid": build_ai_phase_summary(world, phase_analyses[1] if len(phase_analyses) > 1 else None),
            "late": build_ai_phase_summary(world, phase_analyses[2] if len(phase_analyses) > 2 else None),
        },
        "final_margin": {
            "winner_treasury": standings[0]["treasury"],
            "winner_regions": standings[0]["owned_regions"],
            "runner_up": get_faction_display_name(world, runner_up["faction"]) if runner_up is not None else None,
            "runner_up_treasury": runner_up["treasury"] if runner_up is not None else None,
            "runner_up_regions": runner_up["owned_regions"] if runner_up is not None else None,
            "treasury_margin": (
                standings[0]["treasury"] - runner_up["treasury"]
                if runner_up is not None else None
            ),
            "region_margin": (
                standings[0]["owned_regions"] - runner_up["owned_regions"]
                if runner_up is not None else None
            ),
        },
    }
    return summary


def get_winner_doctrine_hint(strategy):
    """Returns a short doctrinal lens for victor-history framing."""
    return f"{strategy.lower()} habits shaped by geography"


def get_winner_path_to_victory(outcome_type, winner, winner_strategy, standings):
    """Returns a compact winner-path label for the victor-history payload."""
    winner_name = winner
    runner_up = standings[1] if len(standings) > 1 else None
    if outcome_type == "full_domination":
        return f"{winner}'s {winner_strategy} approach reduced the field and ended in complete territorial control"
    if outcome_type == "midgame_break":
        return f"{winner}'s {winner_strategy} approach created the decisive middle-phase break"
    if outcome_type == "late_snowball":
        return f"{winner}'s {winner_strategy} approach stayed close and separated late"
    if outcome_type == "economic_win":
        if runner_up is not None and runner_up["owned_regions"] > standings[0]["owned_regions"]:
            return f"{winner}'s {winner_strategy} approach finished first on treasury despite conceding map share"
        return f"{winner}'s {winner_strategy} approach turned superior economic conversion into the winning margin"
    if outcome_type == "balanced_contest":
        return f"{winner}'s {winner_strategy} approach held together best in a narrow multi-faction finish"
    return f"{winner}'s {winner_strategy} approach produced the strongest final position"


def get_claim_dispute_sentence(world, faction_name: str) -> str | None:
    summary = get_faction_diplomacy_summary(world, faction_name)
    counterpart = summary.get("top_claim_dispute")
    disputed_regions = summary.get("top_claim_dispute_regions", 0)
    disputed_ethnicity = summary.get("top_claim_dispute_ethnicity")
    if counterpart is None or disputed_regions <= 0:
        return None

    faction_display = get_faction_display_name(world, faction_name)
    counterpart_display = get_faction_display_name(world, counterpart)
    people_label = disputed_ethnicity or "local"
    return (
        f"{faction_display} remained locked in a claim dispute with {counterpart_display} over "
        f"{format_count_noun(disputed_regions, 'region')} dominated by {people_label} communities."
    )


def get_polity_tension_sentence(world, faction_name: str) -> str | None:
    summary = get_faction_diplomacy_summary(world, faction_name)
    counterpart = summary.get("top_polity_tension")
    if counterpart is None:
        return None

    reason = summary.get("top_polity_tension_reason")
    faction_display = get_faction_display_name(world, faction_name)
    counterpart_display = get_faction_display_name(world, counterpart)
    if reason == "peer_state_rivalry":
        return (
            f"{faction_display} treated {counterpart_display} as a peer-state rival, "
            f"with both polities reading each other as serious strategic threats."
        )
    if reason == "status_gap":
        return (
            f"{faction_display}'s dealings with {counterpart_display} were sharpened by a widening gap in political sophistication."
        )
    return None


def get_regime_tension_sentence(world, faction_name: str) -> str | None:
    summary = get_faction_diplomacy_summary(world, faction_name)
    counterpart = summary.get("top_regime_tension")
    if counterpart is None:
        return None

    reason = summary.get("top_regime_tension_reason")
    faction_display = get_faction_display_name(world, faction_name)
    counterpart_display = get_faction_display_name(world, counterpart)
    if reason == "civil_war_legitimacy":
        return (
            f"{faction_display} remained locked in a legitimacy struggle with {counterpart_display}, "
            f"with both regimes claiming to speak for the same people."
        )
    if reason == "regime_difference":
        return (
            f"{faction_display} and {counterpart_display} drew extra tension from rival forms of rule inside the same broader ethnicity."
        )
    return None


def get_regime_accommodation_sentence(world, faction_name: str) -> str | None:
    summary = get_faction_diplomacy_summary(world, faction_name)
    counterpart = summary.get("top_regime_accommodation")
    if counterpart is None:
        return None

    reason = summary.get("top_regime_accommodation_reason")
    faction_display = get_faction_display_name(world, faction_name)
    counterpart_display = get_faction_display_name(world, counterpart)
    if reason == "same_people_accord":
        return (
            f"{faction_display} and {counterpart_display} kept a same-people accord alive, "
            f"using calmer shared institutions to stop rivalry from hardening too quickly."
        )
    if reason == "legitimacy_accommodation":
        return (
            f"Even amid a legitimacy struggle, {faction_display} and {counterpart_display} still left some room for negotiation through calmer political channels."
        )
    if reason == "diplomatic_restraint":
        return (
            f"{faction_display} relied on diplomatic restraint in dealing with {counterpart_display}, "
            f"keeping a same-people rivalry inside political bounds longer than harsher regimes would."
        )
    return None


def build_victor_history_summary(world, phase_analyses, standings, outcome_type):
    """Builds the compact structured payload sent to the victor-history layer."""
    winner = standings[0]["faction"]
    winner_name = get_faction_display_name(world, winner)
    winner_strategy = world.factions[winner].doctrine_label
    runner_up = standings[1] if len(standings) > 1 else None
    turning_points = summarize_turning_points(world, phase_analyses)

    return {
        "map": getattr(world, "map_name", "") or "unknown_map",
        "turns": len(world.metrics),
        "outcome_type": outcome_type,
        "winner": winner_name,
        "winner_strategy": winner_strategy,
        "winner_doctrine": get_winner_doctrine_hint(winner_strategy),
        "winner_path_to_victory": get_winner_path_to_victory(
            outcome_type=outcome_type,
            winner=winner_name,
            winner_strategy=winner_strategy,
            standings=standings,
        ),
        "turning_points": turning_points[:2],
        "phase_summary": {
            "early": build_ai_phase_summary(world, phase_analyses[0] if len(phase_analyses) > 0 else None),
            "mid": build_ai_phase_summary(world, phase_analyses[1] if len(phase_analyses) > 1 else None),
            "late": build_ai_phase_summary(world, phase_analyses[2] if len(phase_analyses) > 2 else None),
        },
        "winner_trajectory": get_faction_trajectory_sentence(world, winner),
        "runner_up_summary": (
            {
                "faction": runner_up["faction"],
                "faction_display": get_faction_display_name(world, runner_up["faction"]),
                "strategy": world.factions[runner_up["faction"]].doctrine_label,
                "treasury": runner_up["treasury"],
                "regions": runner_up["owned_regions"],
                "trajectory": get_faction_trajectory_sentence(world, runner_up["faction"]),
            }
            if runner_up is not None else None
        ),
        "final_standings": [
            {
                "rank": index + 1,
                "faction": standing["faction"],
                "faction_display": get_faction_display_name(world, standing["faction"]),
                "strategy": world.factions[standing["faction"]].doctrine_label,
                "treasury": standing["treasury"],
                "regions": standing["owned_regions"],
            }
            for index, standing in enumerate(standings)
        ],
    }


def summarize_strategic_interpretation(world):
    """Returns a short interpretation of why the simulation ended as it did."""
    standings = get_final_standings(world)
    if not standings:
        return []

    winner = standings[0]["faction"]
    phase_analyses, _phase_summaries = summarize_phases(world)
    runner_up = standings[1] if len(standings) > 1 else None
    outcome_type = classify_outcome_type(world)
    alive_end = [standing for standing in standings if standing["owned_regions"] > 0]
    final_region_values = [standing["owned_regions"] for standing in standings]
    final_region_spread = max(final_region_values) - min(final_region_values) if final_region_values else 0
    early_analysis = phase_analyses[0] if len(phase_analyses) > 0 else None
    mid_analysis = phase_analyses[1] if len(phase_analyses) > 1 else None
    late_analysis = phase_analyses[2] if len(phase_analyses) > 2 else None
    causal_chain = build_causal_chain(world, winner, outcome_type, phase_analyses)
    ai_summary = build_ai_interpretation_summary(
        world=world,
        phase_analyses=phase_analyses,
        standings=standings,
        outcome_type=outcome_type,
    )
    ai_paragraph = generate_ai_interpretation(ai_summary)

    if ai_paragraph is not None:
        lines = [ai_paragraph]
        standings_by_strategy = [
            f"{get_faction_display_name(world, standing['faction'])} ({world.factions[standing['faction']].doctrine_label})"
            for standing in standings[: min(2, len(standings))]
        ]
        if runner_up is not None:
            lines.append(
                f"The closest challenger was {get_faction_display_name(world, runner_up['faction'])} ({world.factions[runner_up['faction']].doctrine_label}) at "
                f"{runner_up['treasury']} treasury and {format_count_noun(runner_up['owned_regions'], 'region')}."
            )
        else:
            lines.append(
                f"The strongest finishing doctrine in this run was {standings_by_strategy[0]}."
            )
        claim_dispute_line = (
            get_claim_dispute_sentence(world, winner)
            or (
                get_claim_dispute_sentence(world, runner_up["faction"])
                if runner_up is not None
                else None
            )
        )
        if claim_dispute_line is not None:
            lines.append(claim_dispute_line)
        polity_tension_line = (
            get_polity_tension_sentence(world, winner)
            or (
                get_polity_tension_sentence(world, runner_up["faction"])
                if runner_up is not None
                else None
            )
        )
        if polity_tension_line is not None:
            lines.append(polity_tension_line)
        regime_tension_line = (
            get_regime_tension_sentence(world, winner)
            or (
                get_regime_tension_sentence(world, runner_up["faction"])
                if runner_up is not None
                else None
            )
        )
        if regime_tension_line is not None:
            lines.append(regime_tension_line)
        regime_accommodation_line = (
            get_regime_accommodation_sentence(world, winner)
            or (
                get_regime_accommodation_sentence(world, runner_up["faction"])
                if runner_up is not None
                else None
            )
        )
        if regime_accommodation_line is not None:
            lines.append(regime_accommodation_line)
        return lines

    lines = []
    lines.append(get_map_structure_comment(world) + ".")

    setup_line = get_outcome_specific_setup_line(
        outcome_type=outcome_type,
        winner=winner,
        alive_end=alive_end,
        final_region_spread=final_region_spread,
        early_analysis=early_analysis,
        mid_analysis=mid_analysis,
        late_analysis=late_analysis,
    )
    if setup_line is not None:
        lines.append(setup_line)

    if causal_chain is not None:
        driver_line = causal_chain
    else:
        driver_line = build_outcome_specific_driver_line(
            world=world,
            winner=winner,
            outcome_type=outcome_type,
            phase_analyses=phase_analyses,
            standings=standings,
        )
    lines.append(driver_line)

    result_line = build_outcome_specific_result_line(world, outcome_type, standings)
    if result_line is not None:
        lines.append(result_line)

    standings_by_strategy = [
        f"{get_faction_display_name(world, standing['faction'])} ({world.factions[standing['faction']].doctrine_label})"
        for standing in standings[: min(2, len(standings))]
    ]
    if runner_up is not None:
        lines.append(
            f"The closest challenger was {get_faction_display_name(world, runner_up['faction'])} ({world.factions[runner_up['faction']].doctrine_label}) at "
            f"{runner_up['treasury']} treasury and {format_count_noun(runner_up['owned_regions'], 'region')}."
        )
    else:
        lines.append(
            f"The strongest finishing doctrine in this run was {standings_by_strategy[0]}."
        )

    claim_dispute_line = (
        get_claim_dispute_sentence(world, winner)
        or (
            get_claim_dispute_sentence(world, runner_up["faction"])
            if runner_up is not None
            else None
        )
    )
    if claim_dispute_line is not None:
        lines.append(claim_dispute_line)

    polity_tension_line = (
        get_polity_tension_sentence(world, winner)
        or (
            get_polity_tension_sentence(world, runner_up["faction"])
            if runner_up is not None
            else None
        )
    )
    if polity_tension_line is not None:
        lines.append(polity_tension_line)

    regime_tension_line = (
        get_regime_tension_sentence(world, winner)
        or (
            get_regime_tension_sentence(world, runner_up["faction"])
            if runner_up is not None
            else None
        )
    )
    if regime_tension_line is not None:
        lines.append(regime_tension_line)

    regime_accommodation_line = (
        get_regime_accommodation_sentence(world, winner)
        or (
            get_regime_accommodation_sentence(world, runner_up["faction"])
            if runner_up is not None
            else None
        )
    )
    if regime_accommodation_line is not None:
        lines.append(regime_accommodation_line)

    return lines


def build_victor_history_fallback(world, standings, outcome_type, phase_analyses):
    """Returns a short biased but fact-grounded victor-history paragraph."""
    winner = standings[0]["faction"]
    winner_name = get_faction_display_name(world, winner)
    winner_strategy = world.factions[winner].doctrine_label
    runner_up = standings[1] if len(standings) > 1 else None
    doctrine_line = (
        f"their {winner_strategy.lower()} habits, forged by geography, proved stronger than the field's scattered efforts"
    )
    turning_points = summarize_turning_points(world, phase_analyses)
    turning_point_line = turning_points[0] if turning_points else None
    result_line = build_outcome_specific_result_line(world, outcome_type, standings)

    sentences = [
        f"{winner_name}'s historians would treat this run as evidence that {doctrine_line}.",
    ]
    if turning_point_line is not None:
        sentences.append(
            f"They would point first to the decisive shift: {turning_point_line[0].lower() + turning_point_line[1:]}"
        )
    if outcome_type == "economic_win" and runner_up is not None:
        sentences.append(
            f"In their telling, rivals mistook sheer map share for strength, while {winner_name} finished ahead on treasury with {standings[0]['treasury']} against {get_faction_display_name(world, runner_up['faction'])}'s {runner_up['treasury']}."
        )
    elif outcome_type == "full_domination":
        sentences.append(
            f"Once the field narrowed, recovery paths disappeared, which left {winner_name} to finish with {format_count_noun(standings[0]['owned_regions'], 'region')} under its control."
        )
    elif result_line is not None:
        sentences.append(result_line)

    if runner_up is not None:
        sentences.append(
            f"From that partisan view, {get_faction_display_name(world, runner_up['faction'])}'s resistance was real but never as durable as {winner_name}'s final position."
        )

    return " ".join(sentences[:4])


def summarize_victor_history(world):
    """Returns one biased coda paragraph from the winner's perspective."""
    standings = get_final_standings(world)
    if not standings:
        return []

    phase_analyses, _phase_summaries = summarize_phases(world)
    outcome_type = classify_outcome_type(world)
    victor_summary = build_victor_history_summary(
        world=world,
        phase_analyses=phase_analyses,
        standings=standings,
        outcome_type=outcome_type,
    )
    paragraph = generate_victor_history(victor_summary)
    if paragraph is not None:
        return [paragraph]
    return [build_victor_history_fallback(world, standings, outcome_type, phase_analyses)]


def build_chronicle(world, max_key_events=10):
    """Builds a readable chronicle of the simulation."""
    lines = []

    lines.append("Simulation Chronicle")
    lines.append("")

    key_events = get_key_events(world)[:max_key_events]
    for event in key_events:
        sentence = summarize_event(event)
        if sentence:
            lines.append(sentence)

    opening_phase_lines = summarize_opening_phase(world)
    if opening_phase_lines:
        lines.append("")
        lines.append("Opening Phase")
        lines.append("")

        for line in opening_phase_lines:
            lines.append(line)

    phase_analyses, phase_lines = summarize_phases(world)
    if phase_lines:
        lines.append("")
        lines.append("Phase Summaries")
        lines.append("")

        for line in phase_lines:
            lines.append(line)

    turning_point_lines = summarize_turning_points(world, phase_analyses)
    if turning_point_lines:
        lines.append("")
        lines.append("Turning Points")
        lines.append("")

        for line in turning_point_lines:
            lines.append(line)

    outcome_type_lines = summarize_outcome_type(world)
    if outcome_type_lines:
        lines.append("")
        lines.append("Outcome Type")
        lines.append("")

        for line in outcome_type_lines:
            lines.append(line)

    trajectory_lines = summarize_faction_trajectories(world)
    if trajectory_lines:
        lines.append("")
        lines.append("Faction Trajectories")
        lines.append("")

        for line in trajectory_lines:
            lines.append(line)

    strategic_lines = summarize_strategic_interpretation(world)
    if strategic_lines:
        lines.append("")
        lines.append("Strategic Interpretation")
        lines.append("")

        for line in strategic_lines:
            lines.append(line)

    lines.append("")
    lines.append("Final Standings")
    lines.append("")

    for line in summarize_final_standings(world):
        lines.append(line)

    victor_history_lines = summarize_victor_history(world)
    if victor_history_lines:
        lines.append("")
        lines.append("Victor's History")
        lines.append("")

        for line in victor_history_lines:
            lines.append(line)

    return "\n".join(lines)
