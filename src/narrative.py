from src.event_analysis import (
    get_faction_event_counts,
    get_final_standings,
    get_first_expansions,
    get_key_events,
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
            f"region {event['region']}."
        )

    return None


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