from src.event_analysis import (
    build_initial_opening_state,
    ensure_event_importance_scores,
    get_faction_event_counts,
    get_final_standings,
    get_key_events,
    get_opening_phase_summary,
    get_scored_major_events,
)
from src.metrics import get_faction_metrics_history


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
            rank_changes[faction_name] = start_ranks[faction_name] - end_ranks[faction_name]

    biggest_rise = None
    if rank_changes:
        biggest_rise = max(rank_changes, key=lambda name: rank_changes[name])
        if rank_changes[biggest_rise] <= 0:
            biggest_rise = None

    region_deltas = {
        faction_name: end_metrics[faction_name]["regions"] - start_metrics[faction_name]["regions"]
        for faction_name in world.factions
    }
    treasury_deltas = {
        faction_name: end_metrics[faction_name]["treasury"] - start_metrics[faction_name]["treasury"]
        for faction_name in world.factions
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
            f"The strongest early land grab was {highest_scoring_claim['faction']}'s claim of "
            f"{highest_scoring_claim['region']} on turn {format_turn(highest_scoring_claim['turn'])}, "
            f"{role_phrase} that stood out because {highest_scoring_claim['summary_reason']}."
        )

    expansion_leaders = opening["expansion_leaders"]
    if expansion_leaders["count"] > 0:
        lines.append(
            f"In the first {expansion_leaders['turns']} turns, "
            f"{format_faction_list(expansion_leaders['leaders'])} led expansion with "
            f"{expansion_leaders['count']} claim(s)."
        )

    investment_leaders = opening["investment_leaders"]
    if investment_leaders["count"] > 0:
        lines.append(
            f"Across the first {investment_leaders['turns']} turns, "
            f"{format_faction_list(investment_leaders['leaders'])} invested most often with "
            f"{investment_leaders['count']} investment(s)."
        )

    treasury_leaders = opening["treasury_leaders"]
    if treasury_leaders["leaders"]:
        lines.append(
            f"By the end of turn {format_turn(treasury_leaders['turn'])}, "
            f"{format_faction_list(treasury_leaders['leaders'])} held the opening treasury lead "
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
            f"{faction_name} expanded {expand_count} times and invested {invest_count} times, "
            f"and generally {style}."
        )

    return lines


def get_faction_trajectory_sentence(world, faction_name):
    """Returns one concise sentence describing a faction's arc."""
    history = get_faction_metrics_history(world, faction_name)
    standings = get_final_standings(world)

    if not history:
        return f"{faction_name} had too little recorded activity to describe a clear trajectory."

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
    return f"{faction_name} {early_posture}, {midgame}, {ending}."


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
            f"{winner['faction']} finished first with a treasury of {winner['treasury']} "
            f"and control of {format_count_noun(winner['owned_regions'], 'region')}."
        )

    for standing in standings[1:]:
        lines.append(
            f"{standing['faction']} ended with a treasury of {standing['treasury']} "
            f"and {format_count_noun(standing['owned_regions'], 'region')}."
        )

    return lines


def get_turning_point_event_line(event):
    """Returns a concise turning-point sentence for one scored event."""
    phase_name = event.get("phase_name", "mid").capitalize()
    reasons = set(event.get("importance_reasons", []))

    if event["type"] == "attack":
        defender = event.get("defender") or event.get("owner_before")

        if "triggered rival elimination" in reasons and defender:
            return (
                f"{phase_name} collapse: {event['faction']}'s capture of {event['region']} "
                f"eliminated {defender}'s last territorial hold."
            )

        if "shifted leaderboard" in reasons:
            return (
                f"{phase_name} lead swing: {event['faction']}'s attack on {event['region']} "
                f"shifted the leaderboard."
            )

        if event.get("success", False):
            return (
                f"{phase_name} border swing: {event['faction']}'s capture of {event['region']} "
                f"flipped an important frontline region."
            )

    if event["type"] == "expand":
        if "captured key junction" in reasons:
            return (
                f"{phase_name} corridor swing: {event['faction']}'s move into {event['region']} "
                f"secured a key junction and opened multiple follow-up routes."
            )

        return (
            f"{phase_name} expansion swing: {event['faction']}'s move into {event['region']} "
            f"created a meaningful territorial edge."
        )

    if event["type"] == "invest":
        if "strengthened economic lead" in reasons or "shifted leaderboard" in reasons:
            return (
                f"{phase_name} economic pivot: {event['faction']}'s investment in {event['region']} "
                f"strengthened a key holding and improved its overall position."
            )

        return (
            f"{phase_name} development swing: {event['faction']}'s investment in {event['region']} "
            f"reinforced an important region."
        )

    return None


def get_turning_point_event_key(event):
    """Returns a dedupe key so turning points favor distinct decisive moments."""
    reasons = set(event.get("importance_reasons", []))

    if event["type"] == "attack":
        defender = event.get("defender") or event.get("owner_before")
        if "triggered rival elimination" in reasons:
            return ("elimination", defender)
        if "shifted leaderboard" in reasons:
            return ("leader_shift", event["faction"], event.get("phase_name"))
        return ("attack", event["faction"], event["region"])

    if event["type"] == "expand":
        if "captured key junction" in reasons:
            return ("junction", event["region"])
        return ("expand", event["faction"], event["region"])

    if event["type"] == "invest":
        return ("invest", event["faction"], event["region"])

    return ("event", event["faction"], event["region"], event["type"])


def get_phase_break_tier(analysis):
    """Returns a simple tier for a phase break candidate."""
    gain_value = analysis["region_deltas"][analysis["biggest_gain"]]
    loss_value = abs(analysis["region_deltas"][analysis["biggest_loss"]])

    if gain_value >= 6 or analysis["lead_region_margin"] >= 5:
        return "HIGH", 3
    if gain_value >= 3 or loss_value >= 3 or analysis["lead_region_margin"] >= 3:
        return "HIGH", 3
    return "MEDIUM", 2


def get_phase_break_entry(analysis):
    """Returns a ranked turning-point entry for one phase break."""
    biggest_gain = analysis["biggest_gain"]
    biggest_loss = analysis["biggest_loss"]
    gain_value = analysis["region_deltas"][biggest_gain]
    loss_value = analysis["region_deltas"][biggest_loss]
    tier_label, tier_rank = get_phase_break_tier(analysis)
    score = gain_value + max(0, -loss_value) + analysis["lead_region_margin"]

    return {
        "tier_label": tier_label,
        "tier_rank": tier_rank,
        "score": score,
        "line": (
            f"{analysis['phase_name']} phase break: {biggest_gain} gained {format_count_noun(gain_value, 'region')} while "
            f"{biggest_loss} lost {format_count_noun(abs(loss_value), 'region')}."
            if loss_value < 0 else
            f"{analysis['phase_name']} phase break: {biggest_gain} gained {format_count_noun(gain_value, 'region')}."
        ),
        "dedupe_key": ("phase_break", analysis["phase_name"], biggest_gain, biggest_loss),
        "kind": "phase_break",
        "phase_name": analysis["phase_name"],
        "winner": biggest_gain,
    }


def get_event_turning_point_entry(event):
    """Returns a ranked turning-point entry for one scored event."""
    line = get_turning_point_event_line(event)
    if line is None:
        return None

    tier_label = event.get("analysis_importance_tier", "LOW")
    tier_rank = event.get("analysis_importance_rank", 1)
    score = event["importance_score"]

    if event["type"] == "attack" and event.get("success", False):
        score += 1.0
    if "triggered rival elimination" in event.get("importance_reasons", []):
        score += 1.5
    if "shifted leaderboard" in event.get("importance_reasons", []):
        score += 0.8

    return {
        "tier_label": tier_label,
        "tier_rank": tier_rank,
        "score": score,
        "line": line,
        "dedupe_key": get_turning_point_event_key(event),
        "kind": "event",
        "event": event,
    }


def get_selected_turning_point_entries(world, phase_analyses):
    """Returns the top 1-2 distinct turning-point entries."""
    ensure_event_importance_scores(world)
    candidates = []

    for index, analysis in enumerate(phase_analyses):
        biggest_gain = analysis["biggest_gain"]
        biggest_loss = analysis["biggest_loss"]
        gain_value = analysis["region_deltas"][biggest_gain]
        loss_value = analysis["region_deltas"][biggest_loss]

        if gain_value >= 3:
            candidates.append(get_phase_break_entry(analysis))

        if analysis["notable_expansion"] is not None:
            event = analysis["notable_expansion"]
            role = event.get("strategic_role")
            if role == "junction":
                candidates.append({
                    "tier_label": "MEDIUM",
                    "tier_rank": 2,
                    "score": event.get("importance_score", event.get("score", 0)),
                    "line": f"{analysis['phase_name']} corridor swing: {event.faction}'s move into {event.region} secured a key junction and opened multiple follow-up routes.",
                    "dedupe_key": ("event", event.faction, event.region, analysis["phase_name"]),
                    "kind": "event",
                    "event": {
                        "type": "expand",
                        "faction": event.faction,
                        "region": event.region,
                        "phase_name": analysis["phase_name"].lower(),
                    },
                })

        if analysis["stable_board"] and index > 0:
            candidates.append({
                "tier_label": "LOW",
                "tier_rank": 1,
                "score": 2,
                "line": f"{analysis['phase_name']} stabilization: after turn {analysis['start_turn']}, territorial control changed very little.",
                "dedupe_key": ("stabilization", analysis["phase_name"], analysis["start_turn"]),
                "kind": "stabilization",
            })

        if index > 0:
            previous = phase_analyses[index - 1]
            if previous["close_contest"] and not analysis["close_contest"] and analysis["lead_region_margin"] >= 3:
                leader = analysis["rankings"][0][0]
                candidates.append({
                    "tier_label": "HIGH",
                    "tier_rank": 3,
                    "score": analysis["lead_region_margin"] + 2,
                    "line": f"{analysis['phase_name']} separation: a close board broke open when {leader} finished the phase {format_count_noun(analysis['lead_region_margin'], 'region')} clear of the next faction.",
                    "dedupe_key": ("separation", analysis["phase_name"], leader),
                    "kind": "phase_break",
                    "phase_name": analysis["phase_name"],
                    "winner": leader,
                })

    for event in get_scored_major_events(world, minimum_score=4.0):
        entry = get_event_turning_point_entry(event)
        if entry is not None:
            candidates.append(entry)

    ranked_candidates = sorted(
        candidates,
        key=lambda item: (item["tier_rank"], item["score"]),
        reverse=True,
    )

    very_high = [entry for entry in ranked_candidates if entry["tier_rank"] >= 4]
    high = [entry for entry in ranked_candidates if entry["tier_rank"] == 3]
    medium = [entry for entry in ranked_candidates if entry["tier_rank"] == 2]
    low = [entry for entry in ranked_candidates if entry["tier_rank"] <= 1]

    if very_high and high:
        candidate_pool = very_high + high
    elif very_high:
        candidate_pool = very_high
    elif high:
        candidate_pool = high
    elif medium:
        candidate_pool = medium
    else:
        candidate_pool = low

    selected = []
    used_keys = set()

    for entry in candidate_pool:
        if entry["dedupe_key"] in used_keys:
            continue
        if selected and selected[0]["tier_rank"] >= 3 and entry["tier_rank"] < 3:
            continue
        if (
            entry["kind"] == "event"
            and entry["tier_rank"] <= 2
            and any(existing["kind"] == "phase_break" for existing in selected)
        ):
            continue
        selected.append(entry)
        used_keys.add(entry["dedupe_key"])
        if len(selected) == 2:
            break

    return selected


def summarize_turning_points(world, phase_analyses):
    """Returns 1-2 concise lines describing decisive shifts in the run."""
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
        standing["faction"]
        for standing in standings[1:]
        if standing["owned_regions"] > winner_regions
    ]
    alive_end = [standing for standing in standings if standing["owned_regions"] > 0]
    mid_analysis = phase_analyses[1] if len(phase_analyses) > 1 else None
    late_analysis = phase_analyses[2] if len(phase_analyses) > 2 else None

    if outcome_type == "full_domination":
        if collapse_events:
            rival = collapse_events[0].get("defender") or collapse_events[0].get("owner_before") or "a key rival"
            phase_name = collapse_events[0].get("phase_name", "mid")
            return (
                f"{winner} eliminated {rival} in the {phase_name} phase, reduced the competitive field, "
                f"converted that advantage into control of the board, and then consolidated into full domination."
            )
        if phase_breaks:
            phase_name = phase_breaks[0]["phase_name"].lower()
            return (
                f"{winner} created the decisive break in the {phase_name} phase, turned that lead into control of the board, "
                f"and then consolidated the map."
            )
        return (
            f"{winner} took control of the board, removed the remaining rivals from contention, "
            f"and finished on {format_count_noun(winner_regions, 'region')} with full domination."
        )

    if outcome_type == "midgame_break":
        if mid_analysis is not None:
            return (
                f"{winner} turned the contested opening into a decisive middle-phase swing, built a durable territorial lead, "
                f"and carried that edge to the finish."
            )
        if phase_breaks:
            return (
                f"{winner} created the decisive break after an even opening, built a durable lead, "
                f"and never let the field close the gap."
            )
        return (
            f"{winner} found the decisive break in the middle portion of the run and converted it into a stable winning position."
        )

    if outcome_type == "late_snowball":
        if late_analysis is not None:
            return (
                f"The board stayed crowded into the late phase, but {winner} separated only at the end, "
                f"opened a decisive lead, and closed out the run."
            )
        return (
            f"No early leader held control for long; {winner} stayed within reach and separated only in the closing turns."
        )

    if outcome_type == "economic_win":
        if larger_rivals:
            return (
                f"{winner} did not win on map share. It finished first on treasury while "
                f"{format_faction_list(larger_rivals)} held more territory but failed to turn that size into enough net income."
            )
        if runner_up is not None and runner_up["owned_regions"] >= winner_regions:
            return (
                f"{winner} won on treasury rather than territory, edging out rivals that matched or exceeded its map share."
            )
        return (
            f"{winner} kept the stronger treasury position, and the larger empires never converted their territory into a better economic finish."
        )

    if outcome_type == "balanced_contest":
        return (
            f"No decisive collapse or phase break separated the field. {winner} edged ahead in a finish that remained close across "
            f"{format_count_noun(len(alive_end), 'surviving faction')}."
        )

    if outcome_type == "early_snowball":
        return (
            f"{winner} established the early lead, denied the field a meaningful recovery window, and converted that start into a lasting win."
        )

    if runner_up is not None:
        return (
            f"{winner} finished ahead of {runner_up['faction']} by turning a narrow lead into the stronger final position on treasury and territory."
        )

    return None


def build_outcome_specific_result_line(outcome_type, standings):
    """Returns a concise outcome-specific result line."""
    if not standings:
        return None

    winner = standings[0]["faction"]
    winner_regions = standings[0]["owned_regions"]
    winner_treasury = standings[0]["treasury"]
    runner_up = standings[1] if len(standings) > 1 else None

    if outcome_type == "full_domination":
        return (
            f"By the finish, {winner} held {format_count_noun(winner_regions, 'region')} and {winner_treasury} treasury while every rival had been reduced to zero territory."
        )
    if outcome_type == "economic_win":
        max_regions = max(standing["owned_regions"] for standing in standings)
        return (
            f"{winner} finished first on {winner_treasury} treasury with {format_count_noun(winner_regions, 'region')}, "
            f"while the largest empire finished on {format_count_noun(max_regions, 'region')}."
        )
    if outcome_type == "balanced_contest" and runner_up is not None:
        treasury_margin = winner_treasury - runner_up["treasury"]
        return (
            f"The final margin stayed narrow: {winner} beat {runner_up['faction']} by {treasury_margin} treasury."
        )
    if outcome_type in {"midgame_break", "late_snowball", "early_snowball"} and runner_up is not None:
        return (
            f"That break left {winner} ahead at the finish with {format_count_noun(winner_regions, 'region')} and {winner_treasury} treasury."
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

    result_line = build_outcome_specific_result_line(outcome_type, standings)
    if result_line is not None:
        lines.append(result_line)

    standings_by_strategy = [
        f"{standing['faction']} ({world.factions[standing['faction']].strategy})"
        for standing in standings[: min(2, len(standings))]
    ]
    if runner_up is not None:
        lines.append(
            f"The closest challenger was {runner_up['faction']} ({world.factions[runner_up['faction']].strategy}) at "
            f"{runner_up['treasury']} treasury and {format_count_noun(runner_up['owned_regions'], 'region')}."
        )
    else:
        lines.append(
            f"The strongest finishing strategy in this run was {standings_by_strategy[0]}."
        )

    return lines


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

    return "\n".join(lines)
