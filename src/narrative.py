from src.event_analysis import (
    get_faction_event_counts,
    get_final_standings,
    get_key_events,
    get_opening_phase_summary,
)


def format_turn(turn):
    """Formats zero-based turn indices for user-facing output."""
    return turn + 1


def format_score(value):
    """Formats score values without a trailing .0 when possible."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


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
        outcome_clause = ""
        if event.get("future_expansion_opened", 0) >= 4:
            outcome_clause = " and later opened the way for further expansion"
        elif event.get("income_gain", 0) >= 3:
            outcome_clause = " and later strengthened its income base"
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

    lines.append("")
    lines.append("Faction Behavior")
    lines.append("")

    for line in summarize_faction_behavior(world):
        lines.append(line)

    lines.append("")
    lines.append("Final Standings")
    lines.append("")

    for line in summarize_final_standings(world):
        lines.append(line)

    return "\n".join(lines)
