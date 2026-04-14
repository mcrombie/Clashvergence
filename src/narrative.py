from src.event_analysis import (
    build_initial_opening_state,
    get_faction_event_counts,
    get_final_standings,
    get_key_events,
    get_opening_phase_summary,
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


def summarize_phase_turns(world, phase_name, start_turn, end_turn):
    """Builds a concise strategic summary for one simulation phase."""
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
    turning_points = []

    for event in phase_events:
        if event.type in event_counts:
            event_counts[event.type] += 1
        if event.type == "attack" and event.get("success", False):
            successful_attacks += 1
            if event.region is not None:
                attack_shifted_regions.add(event.region)
        if event.type == "expand" and event.region is not None:
            expansion_regions.add(event.region)
        if event.type == "expand" and event.get("is_turning_point", False):
            turning_points.append(event)

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

    lead_name, lead_metrics = rankings[0]
    lead_summary = (
        f"{format_subject_verb(strongest, 'was', 'were')} strongest by the end of turns {start_turn}-{end_turn}, "
        f"with {lead_name} on {lead_metrics['treasury']} treasury and {format_count_noun(lead_metrics['regions'], 'region')}"
    )

    action_details = []
    if successful_attacks or event_counts["expand"] or event_counts["invest"]:
        if successful_attacks:
            action_details.append(
                f"{successful_attacks} successful attacks flipped {format_count_noun(len(attack_shifted_regions), 'region')}"
            )
        if event_counts["expand"]:
            action_details.append(
                f"{format_count_noun(event_counts['expand'], 'expansion')} added {format_count_noun(len(expansion_regions), 'new region')}"
            )
        if event_counts["invest"]:
            action_details.append(f"{format_count_noun(event_counts['invest'], 'investment')} improved existing holdings")
    else:
        action_details.append("the board stayed stable with no expansions, investments, or successful attacks")

    shift_details = []
    if region_deltas[biggest_gain] > 0:
        shift_details.append(
            f"{biggest_gain} gained {format_count_noun(region_deltas[biggest_gain], 'region')}"
        )
    if region_deltas[biggest_loss] < 0:
        shift_details.append(
            f"{biggest_loss} lost {format_count_noun(abs(region_deltas[biggest_loss]), 'region')}"
        )

    if turning_points:
        notable = max(turning_points, key=lambda event: event.get("score", 0))
        shift_details.append(
            f"{notable.faction}'s push into {notable.region} was the phase's clearest turning point"
        )
    elif biggest_rise is not None:
        shift_details.append(
            f"{biggest_rise} improved its standing most during the phase"
        )

    sentence = f"{phase_name} phase: {lead_summary}. " + "; ".join(action_details).capitalize() + "."
    if shift_details:
        sentence += " " + ". ".join(shift_details) + "."

    return sentence


def summarize_phases(world):
    """Returns phase-based summaries for the full simulation."""
    return [
        summary
        for phase in get_phase_ranges(len(world.metrics))
        if (summary := summarize_phase_turns(world, *phase)) is not None
    ]


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


def get_map_structure_comment(world):
    """Returns a grounded comment about map scale and connectivity."""
    region_count = len(world.regions)
    average_degree = sum(len(region.neighbors) for region in world.regions.values()) / region_count
    max_degree = max(len(region.neighbors) for region in world.regions.values())

    if region_count <= 13:
        return f"On this compact {region_count}-region map, early contact came quickly"
    if region_count >= 30 and average_degree >= 4:
        return f"On this larger {region_count}-region layout, the wider front and multiple routes delayed a clean break"
    if max_degree >= 8:
        return "A highly connected center kept several factions in contention before one side pulled clear"
    return f"On this {region_count}-region map, control of the best-connected routes mattered more than raw expansion count"


def describe_end_state(final_snapshot, final_rank, total_factions):
    """Returns a concrete ending-state phrase."""
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

    final_rank = next(
        index + 1
        for index, standing in enumerate(standings)
        if standing["faction"] == faction_name
    )
    early_posture = describe_early_posture(early_history)
    midgame = describe_midgame(mid_history)
    end_state = describe_end_state(final_snapshot, final_rank, len(world.factions))
    return f"{faction_name} {early_posture}, {midgame}, {end_state}."


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
            f"and control of {winner['owned_regions']} regions."
        )

    for standing in standings[1:]:
        lines.append(
            f"{standing['faction']} ended with a treasury of {standing['treasury']} "
            f"and {standing['owned_regions']} regions."
        )

    return lines


def summarize_strategic_interpretation(world):
    """Returns a short interpretation of why the simulation ended as it did."""
    standings = get_final_standings(world)
    if not standings:
        return []

    winner = standings[0]["faction"]
    winner_history = get_faction_metrics_history(world, winner)
    total_events = {"expand": 0, "invest": 0, "attack": 0}
    successful_attacks = 0
    expanded_regions = set()
    collapsed_factions = [
        standing["faction"] for standing in standings[1:]
        if standing["owned_regions"] == 0
    ]

    for event in world.events:
        if event.type in total_events:
            total_events[event.type] += 1
        if event.type == "attack" and event.get("success", False):
            successful_attacks += 1
        if event.type == "expand" and event.region is not None:
            expanded_regions.add(event.region)

    opening = get_opening_phase_summary(world)
    winner_attacks = sum(entry["attacks"] for entry in winner_history)
    winner_expansions = sum(entry["expansions"] for entry in winner_history)
    winner_investments = sum(entry["investments"] for entry in winner_history)
    winner_final = winner_history[-1]
    winner_opening_regions = winner_history[min(max(0, len(winner_history) // 3 - 1), len(winner_history) - 1)]["regions"]
    runner_up = standings[1] if len(standings) > 1 else None

    lines = []
    lines.append(get_map_structure_comment(world) + ".")

    driver_line = None
    if collapsed_factions and winner_final["regions"] >= max(1, len(world.regions) // 2):
        driver_line = (
            f"The decisive shift was rival collapse: {format_faction_list(collapsed_factions)} finished without territory while "
            f"{winner} expanded to {format_count_noun(winner_final['regions'], 'region')}."
        )
    elif winner in opening["treasury_leaders"]["leaders"] or winner_opening_regions >= 3:
        driver_line = (
            f"The outcome was heavily shaped by early position: {winner} carried its opening foothold into "
            f"{format_count_noun(winner_final['regions'], 'region')} and never surrendered the economic lead for long."
        )
    elif winner_investments >= winner_attacks and winner_final["treasury"] > winner_history[0]["treasury"] * 5:
        driver_line = (
            f"Economic scaling was the key difference: {winner} turned development and income into a late treasury climb, "
            f"finishing on {winner_final['treasury']}."
        )
    elif successful_attacks >= max(6, total_events["expand"]):
        driver_line = (
            f"Combat was the main driver: {successful_attacks} successful attacks changed control, compared with "
            f"{total_events['expand']} expansion actions over the run."
        )
    else:
        driver_line = (
            f"Expansion and upkeep balance decided the result more than raw combat volume, with {len(expanded_regions)} regions claimed by expansion over the run."
        )
    lines.append(driver_line)

    if winner_attacks > winner_expansions and winner_attacks > winner_investments:
        winner_style = (
            f"won through repeated border contests, recording {winner_attacks} attack attempts"
        )
    elif winner_expansions > winner_attacks and winner_expansions >= winner_investments:
        winner_style = (
            f"won by securing space early and holding {format_count_noun(winner_final['regions'], 'region')}"
        )
    else:
        winner_style = (
            f"won by compounding income and finishing with {winner_final['treasury']} treasury"
        )
    lines.append(
        f"{winner} succeeded because it {winner_style}, finishing with {format_count_noun(winner_final['regions'], 'region')}, {winner_final['treasury']} treasury, and rank 1."
    )

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

    phase_lines = summarize_phases(world)
    if phase_lines:
        lines.append("")
        lines.append("Phase Summaries")
        lines.append("")

        for line in phase_lines:
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
