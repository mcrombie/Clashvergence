from src.metrics import get_turn_metrics
from src.factions import create_factions


def get_expand_event_importance(event):
    """Returns the importance score recorded on an expansion event."""
    if event.significance is not None:
        return event.significance
    return event.details.get("score", event.get("score", 0))


def get_short_term_follow_up(world, event, max_turn_gap=2):
    """Returns the next short-term expansion by the same faction, if any."""
    for candidate in world.events:
        if candidate.type != "expand":
            continue
        if candidate.faction != event.faction:
            continue
        if candidate.turn <= event.turn:
            continue
        if candidate.turn > event.turn + max_turn_gap:
            continue
        return {
            "follow_up_region": candidate.region,
            "follow_up_turn": candidate.turn,
        }

    return {
        "follow_up_region": None,
        "follow_up_turn": None,
    }


def summarize_expand_event(event, world=None):
    """Returns a normalized interpreted summary for an expansion event."""
    details = event.details
    context = event.context
    impact = event.impact
    follow_up = {
        "follow_up_region": impact.get("follow_up_region"),
        "follow_up_turn": impact.get("follow_up_turn"),
    }

    if world is not None and follow_up["follow_up_region"] is None:
        follow_up = get_short_term_follow_up(world, event)

    return {
        "turn": event.turn,
        "faction": event.faction,
        "region": event.region,
        "resources": details.get("resources", event.get("resources", 0)),
        "neighbors": details.get("neighbors", event.get("neighbors", 0)),
        "unclaimed_neighbors": details.get(
            "unclaimed_neighbors",
            event.get("unclaimed_neighbors", 0),
        ),
        "cost": details.get("cost", event.get("cost", 0)),
        "importance_score": get_expand_event_importance(event),
        "treasury_before": context.get("treasury_before"),
        "treasury_after": context.get("treasury_after", event.get("treasury_after")),
        "rank_before": context.get("rank_before"),
        "owner_before": context.get("owner_before"),
        "owner_after": impact.get("owner_after", event.faction),
        "treasury_change": impact.get("treasury_change"),
        "regions_gained": impact.get("regions_gained"),
        "strategic_role": impact.get("strategic_role"),
        "income_gain": impact.get("income_gain", details.get("resources", 0)),
        "rank_after": impact.get("rank_after"),
        "rank_change": impact.get("rank_change"),
        "future_expansion_opened": impact.get(
            "future_expansion_opened",
            details.get("unclaimed_neighbors", 0),
        ),
        "importance_tier": impact.get("importance_tier"),
        "is_turning_point": impact.get("is_turning_point", False),
        "momentum_effect": impact.get("momentum_effect"),
        "summary_reason": impact.get("summary_reason"),
        "narrative_tags": impact.get("narrative_tags", list(event.tags)),
        "tags": list(event.tags),
        "significance": event.significance,
        "follow_up_region": follow_up["follow_up_region"],
        "follow_up_turn": follow_up["follow_up_turn"],
    }


def get_event_log(world):
    """Returns the raw event log."""
    return world.events


def get_events_for_turn_range(world, start_turn=0, end_turn=None):
    """Returns events whose turn falls within the given range."""
    events = []

    for event in world.events:
        turn = event.turn
        if turn < start_turn:
            continue
        if end_turn is not None and turn > end_turn:
            continue
        events.append(event)

    return events


def get_events_by_faction(world):
    """Groups events by faction."""
    events_by_faction = {}

    for faction_name in world.factions:
        events_by_faction[faction_name] = []

    for event in world.events:
        faction_name = event.faction
        if faction_name in events_by_faction:
            events_by_faction[faction_name].append(event)

    return events_by_faction


def get_first_expansions(world):
    """Returns the first expansion event for each faction."""
    first_expansions = {}

    for event in world.events:
        if event.type == "expand":
            faction_name = event.faction
            if faction_name not in first_expansions:
                first_expansions[faction_name] = event

    return first_expansions


def get_high_value_expansions(world, minimum_score=10):
    """Returns expansion events into strategically important regions."""
    important_expansions = []

    for event in world.events:
        if event.type == "expand":
            importance_score = get_expand_event_importance(event)

            if importance_score >= minimum_score:
                important_expansions.append(summarize_expand_event(event, world=world))

    return important_expansions


def get_top_scoring_opening_claim(world):
    """Returns the first claim of the highest-scoring region in the opening events."""
    expansion_events = [event for event in world.events if event.type == "expand"]

    if not expansion_events:
        return None

    best_event = max(expansion_events, key=get_expand_event_importance)

    return summarize_expand_event(best_event, world=world)


def get_opening_expansion_leaders(world, opening_turns=3):
    """Returns the factions with the most expansions in the opening turns."""
    counts = {faction_name: 0 for faction_name in world.factions}

    for event in get_events_for_turn_range(world, end_turn=opening_turns - 1):
        if event.type == "expand":
            counts[event.faction] += 1

    best_count = max(counts.values(), default=0)
    leaders = [
        faction_name
        for faction_name, count in counts.items()
        if count == best_count and best_count > 0
    ]

    return {
        "leaders": leaders,
        "count": best_count,
        "turns": opening_turns,
    }


def get_opening_investment_leaders(world, opening_turns=5):
    """Returns the factions with the most investments in the opening turns."""
    counts = {faction_name: 0 for faction_name in world.factions}

    for event in get_events_for_turn_range(world, end_turn=opening_turns - 1):
        if event.type == "invest":
            counts[event.faction] += 1

    best_count = max(counts.values(), default=0)
    leaders = [
        faction_name
        for faction_name, count in counts.items()
        if count == best_count and best_count > 0
    ]

    return {
        "leaders": leaders,
        "count": best_count,
        "turns": opening_turns,
    }


def build_initial_opening_state(world):
    """Infers initial ownership and resource values from the final world and event log."""
    expanded_regions = {event.region for event in world.events if event.type == "expand"}
    region_state = {}

    for region_name, region in world.regions.items():
        initial_resources = region.resources

        for event in world.events:
            if event.type == "invest" and event.region == region_name:
                initial_resources -= event.get("invest_amount", 0)

        if initial_resources < 0:
            initial_resources = 0

        initial_owner = None if region_name in expanded_regions else region.owner

        region_state[region_name] = {
            "owner": initial_owner,
            "resources": initial_resources,
        }

    return region_state


def replay_opening_treasury_snapshots(world, opening_turns=5):
    """Replays the opening turns and returns treasury snapshots after each turn."""
    region_state = build_initial_opening_state(world)
    num_factions = len(world.factions)
    treasuries = {
        faction_name: faction.treasury
        for faction_name, faction in create_factions(num_factions=num_factions).items()
        if faction_name in world.factions
    }
    snapshots = []

    for turn in range(opening_turns):
        turn_events = [event for event in world.events if event.turn == turn]

        for event in turn_events:
            faction_name = event.faction

            if event.type == "expand":
                treasuries[faction_name] -= event.details.get("cost", event.get("cost", 0))
                region_state[event.region]["owner"] = faction_name
            elif event.type == "invest":
                region_state[event.region]["resources"] = event.get(
                    "new_resources",
                    region_state[event.region]["resources"] + event.get("invest_amount", 0),
                )

        for region in region_state.values():
            if region["owner"] is not None:
                treasuries[region["owner"]] += region["resources"]

        snapshots.append({
            "turn": turn,
            "treasuries": treasuries.copy(),
        })

    return snapshots


def get_opening_treasury_leaders(world, opening_turns=5):
    """Returns the faction or factions leading in treasury after the opening turns."""
    metrics_snapshot = get_turn_metrics(world, opening_turns)

    if metrics_snapshot is not None:
        best_treasury = max(
            (
                faction_metrics["treasury"]
                for faction_metrics in metrics_snapshot["factions"].values()
            ),
            default=0,
        )
        leaders = [
            faction_name
            for faction_name, faction_metrics in metrics_snapshot["factions"].items()
            if faction_metrics["treasury"] == best_treasury
        ]

        return {
            "leaders": leaders,
            "treasury": best_treasury,
            "turn": metrics_snapshot["turn"] - 1,
            "turns": opening_turns,
        }

    snapshots = replay_opening_treasury_snapshots(world, opening_turns=opening_turns)

    if not snapshots:
        return {
            "leaders": [],
            "treasury": 0,
            "turn": opening_turns - 1,
            "turns": opening_turns,
        }

    final_snapshot = snapshots[-1]
    best_treasury = max(final_snapshot["treasuries"].values(), default=0)
    leaders = [
        faction_name
        for faction_name, treasury in final_snapshot["treasuries"].items()
        if treasury == best_treasury
    ]

    return {
        "leaders": leaders,
        "treasury": best_treasury,
        "turn": final_snapshot["turn"],
        "turns": opening_turns,
    }


def get_opening_phase_summary(world):
    """Returns a summary of major opening-phase patterns."""
    return {
        "highest_scoring_claim": get_top_scoring_opening_claim(world),
        "expansion_leaders": get_opening_expansion_leaders(world, opening_turns=3),
        "investment_leaders": get_opening_investment_leaders(world, opening_turns=5),
        "treasury_leaders": get_opening_treasury_leaders(world, opening_turns=5),
    }


def get_faction_event_counts(world):
    """Returns counts of expand and invest actions by faction."""
    faction_event_counts = {}

    for faction_name in world.factions:
        faction_event_counts[faction_name] = {
            "expand": 0,
            "invest": 0,
        }

    for event in world.events:
        faction_name = event.faction
        event_type = event.type

        if faction_name in faction_event_counts and event_type in faction_event_counts[faction_name]:
            faction_event_counts[faction_name][event_type] += 1

    return faction_event_counts


def get_final_standings(world):
    """Returns sorted faction standings by treasury."""
    standings = []

    for faction_name, faction in world.factions.items():
        owned_regions = 0
        for region in world.regions.values():
            if region.owner == faction_name:
                owned_regions += 1

        standings.append({
            "faction": faction_name,
            "treasury": faction.treasury,
            "owned_regions": owned_regions,
        })

    standings.sort(key=lambda entry: entry["treasury"], reverse=True)
    return standings


def get_key_events(world):
    """Returns a curated set of important events for summary purposes."""
    key_events = []

    first_expansions = get_first_expansions(world)
    for event in first_expansions.values():
        key_events.append({
            "kind": "first_expansion",
            "turn": event.turn,
            "faction": event.faction,
            "region": event.region,
        })

    for event in get_high_value_expansions(world):
        key_events.append({
            "kind": "high_value_expansion",
            "turn": event["turn"],
            "faction": event["faction"],
            "region": event["region"],
            "resources": event["resources"],
            "neighbors": event["neighbors"],
            "unclaimed_neighbors": event["unclaimed_neighbors"],
            "importance_score": event["importance_score"],
            "treasury_after": event["treasury_after"],
            "rank_before": event["rank_before"],
            "rank_after": event["rank_after"],
            "rank_change": event["rank_change"],
            "income_gain": event["income_gain"],
            "future_expansion_opened": event["future_expansion_opened"],
            "importance_tier": event["importance_tier"],
            "is_turning_point": event["is_turning_point"],
            "momentum_effect": event["momentum_effect"],
            "strategic_role": event["strategic_role"],
            "summary_reason": event["summary_reason"],
            "narrative_tags": event["narrative_tags"],
            "tags": event["tags"],
            "regions_gained": event["regions_gained"],
            "follow_up_region": event["follow_up_region"],
            "follow_up_turn": event["follow_up_turn"],
        })

    key_events.sort(key=lambda event: event["turn"])
    return key_events
