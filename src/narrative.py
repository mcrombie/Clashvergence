from src.event_analysis import (
    get_faction_event_counts,
    get_final_standings,
    get_key_events,
    get_opening_phase_summary,
)


def summarize_event(event):
    """Turns one analyzed event into a sentence."""
    if event["kind"] == "first_expansion":
        return (
            f"On turn {event['turn']}, {event['faction']} made its first expansion into "
            f"{event['region']}."
        )

    if event["kind"] == "high_value_expansion":
        return (
            f"On turn {event['turn']}, {event['faction']} seized the strategically important "
            f"region {event['region']}, valued for its {event['resources']} resources, "
            f"{event['neighbors']} connections, and {event['unclaimed_neighbors']} unclaimed "
            f"neighboring regions that offered future expansion potential."
        )

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
        lines.append(
            f"The strongest early land grab was {highest_scoring_claim['faction']}'s claim of "
            f"{highest_scoring_claim['region']} on turn {highest_scoring_claim['turn']}, a "
            f"score-{highest_scoring_claim['importance_score']} region with "
            f"{highest_scoring_claim['resources']} resources, "
            f"{highest_scoring_claim['neighbors']} connections, and "
            f"{highest_scoring_claim['unclaimed_neighbors']} open neighbors."
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
            f"By the end of turn {treasury_leaders['turn'] + 1}, "
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
