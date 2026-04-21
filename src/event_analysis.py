from src.maps import MAPS
from src.metrics import get_turn_metrics
from src.resource_economy import get_region_taxable_value

# EVENT IMPORTANCE WEIGHTS
IMPORTANCE_BASE_ATTACK = 3.0
IMPORTANCE_BASE_EXPANSION = 2.2
IMPORTANCE_BASE_DEVELOPMENT = 0.9

IMPORTANCE_OWNERSHIP_TRANSFER = 2.0
IMPORTANCE_TERRITORY_GAIN = 0.8
IMPORTANCE_STRATEGIC_JUNCTION = 1.5
IMPORTANCE_STRATEGIC_FRONTIER = 0.9
IMPORTANCE_RESOURCE_REGION = 0.5
IMPORTANCE_RANK_STEP = 0.75
IMPORTANCE_LEADER_CHANGE = 1.75
IMPORTANCE_CLOSE_CONTEST = 0.9
IMPORTANCE_COLLAPSE = 1.5
IMPORTANCE_ELIMINATION = 2.5
IMPORTANCE_LATE_DECISIVE_SWING = 1.25
IMPORTANCE_PHASE_EARLY = 0.35
IMPORTANCE_PHASE_MID = 0.7
IMPORTANCE_PHASE_LATE = 0.85

IMPORTANCE_LOW_IMPACT_DEVELOPMENT_PENALTY = -0.5
IMPORTANCE_REDUNDANT_EVENT_PENALTY = -0.3
IMPORTANCE_ALREADY_DECIDED_PENALTY = -0.6

DEVELOPMENT_EVENT_TYPES = {"develop", "invest"}
MAJOR_EVENT_TYPES = {"expand", "attack", "develop", "invest"}

IMPORTANCE_TIER_LOW = "LOW"
IMPORTANCE_TIER_MEDIUM = "MEDIUM"
IMPORTANCE_TIER_HIGH = "HIGH"
IMPORTANCE_TIER_VERY_HIGH = "VERY_HIGH"

IMPORTANCE_TIER_RANKS = {
    IMPORTANCE_TIER_LOW: 1,
    IMPORTANCE_TIER_MEDIUM: 2,
    IMPORTANCE_TIER_HIGH: 3,
    IMPORTANCE_TIER_VERY_HIGH: 4,
}


def get_phase_ranges(total_turns):
    """Splits a run into one-based early/mid/late turn ranges."""
    if total_turns <= 0:
        return []

    early_end = max(1, total_turns // 3)
    mid_end = max(early_end + 1, (2 * total_turns) // 3)
    mid_end = min(mid_end, total_turns)

    ranges = [("early", 1, early_end)]

    if early_end + 1 <= mid_end:
        ranges.append(("mid", early_end + 1, mid_end))

    if mid_end + 1 <= total_turns:
        ranges.append(("late", mid_end + 1, total_turns))

    return ranges


def _is_development_event(event) -> bool:
    return event.type in DEVELOPMENT_EVENT_TYPES


def get_event_phase_name(event, total_turns):
    """Returns the phase label for a zero-based event turn."""
    one_based_turn = event.turn + 1

    for phase_name, start_turn, end_turn in get_phase_ranges(total_turns):
        if start_turn <= one_based_turn <= end_turn:
            return phase_name

    return "late"


def get_region_counts_from_owners(owners, factions):
    """Returns owned-region counts from an owner map."""
    counts = {faction_name: 0 for faction_name in factions}

    for owner in owners.values():
        if owner in counts:
            counts[owner] += 1

    return counts


def get_rankings(treasuries, region_counts):
    """Returns standings ordered by treasury first and regions second."""
    return sorted(
        treasuries.items(),
        key=lambda item: (item[1], region_counts.get(item[0], 0)),
        reverse=True,
    )


def get_rank_map(treasuries, region_counts):
    """Returns one-based faction ranks for the current replay state."""
    return {
        faction_name: index + 1
        for index, (faction_name, _treasury) in enumerate(get_rankings(treasuries, region_counts))
    }


def get_unique_leader(treasuries, region_counts):
    """Returns the sole leader when one exists, otherwise None."""
    rankings = get_rankings(treasuries, region_counts)

    if not rankings:
        return None

    leader_name, leader_treasury = rankings[0]
    leader_regions = region_counts.get(leader_name, 0)

    if len(rankings) == 1:
        return leader_name

    runner_name, runner_treasury = rankings[1]
    runner_regions = region_counts.get(runner_name, 0)

    if (leader_treasury, leader_regions) == (runner_treasury, runner_regions):
        return None

    return leader_name


def get_region_margin(region_counts):
    """Returns the current top-two region margin."""
    values = sorted(region_counts.values(), reverse=True)

    if not values:
        return 0
    if len(values) == 1:
        return values[0]
    return values[0] - values[1]


def is_close_contest(region_counts):
    """Returns whether multiple factions remain close on the board."""
    alive_counts = [count for count in region_counts.values() if count > 0]

    if len(alive_counts) < 3:
        return False

    return max(alive_counts) - min(alive_counts) <= 3


def clone_replay_state(state):
    """Returns a shallow copy of the replay state."""
    return {
        "owners": state["owners"].copy(),
        "resources": state["resources"].copy(),
        "taxable_values": state["taxable_values"].copy(),
        "treasuries": state["treasuries"].copy(),
        "region_counts": state["region_counts"].copy(),
    }


def apply_event_to_replay_state(event, state):
    """Applies one event to a replay state and returns the resulting copy."""
    new_state = clone_replay_state(state)
    faction_name = event.faction

    if event.type in {"expand", "attack"} and event.region is not None:
        owner_before = new_state["owners"].get(event.region)
        owner_after = event.get("owner_after", owner_before)

        if owner_after != owner_before:
            if owner_before in new_state["region_counts"]:
                new_state["region_counts"][owner_before] = max(
                    0,
                    new_state["region_counts"][owner_before] - 1,
                )
            if owner_after in new_state["region_counts"]:
                new_state["region_counts"][owner_after] += 1
            new_state["owners"][event.region] = owner_after

    if _is_development_event(event) and event.region is not None:
        new_state["resources"][event.region] = event.get(
            "new_resources",
            new_state["resources"].get(event.region, 0) + event.get("resource_change", 0),
        )
        new_state["taxable_values"][event.region] = event.get(
            "new_taxable_value",
            new_state["taxable_values"].get(event.region, 0.0) + event.get("taxable_change", 0.0),
        )

    treasury_after = event.get("treasury_after")
    treasury_change = event.get("treasury_change")

    if faction_name in new_state["treasuries"]:
        if treasury_after is not None:
            new_state["treasuries"][faction_name] = treasury_after
        elif treasury_change is not None:
            new_state["treasuries"][faction_name] += treasury_change

    return new_state


def build_replay_state(world):
    """Builds the initial replay state used for event-level analysis."""
    initial_state = build_initial_opening_state(world)
    treasuries = {
        faction_name: faction.starting_treasury
        for faction_name, faction in world.factions.items()
    }
    owners = {
        region_name: data["owner"]
        for region_name, data in initial_state.items()
    }
    resources = {
        region_name: data["resources"]
        for region_name, data in initial_state.items()
    }
    taxable_values = {
        region_name: data["taxable_value"]
        for region_name, data in initial_state.items()
    }

    return {
        "owners": owners,
        "resources": resources,
        "taxable_values": taxable_values,
        "treasuries": treasuries,
        "region_counts": get_region_counts_from_owners(owners, world.factions),
    }


def get_region_profile(world, event):
    """Returns strategic metadata for the event's target region."""
    if event.region is None or event.region not in world.regions:
        return {
            "resources": 0,
            "economic_value": 0.0,
            "neighbors": 0,
            "is_junction": False,
            "is_frontier": False,
        }

    region = world.regions[event.region]
    resources = event.get(
        "taxable_value",
        event.get("target_taxable_value", event.get("resources", get_region_taxable_value(region, world))),
    )
    neighbors = event.get("neighbors", len(region.neighbors))
    strategic_role = event.get("strategic_role")

    return {
        "resources": resources,
        "economic_value": resources,
        "neighbors": neighbors,
        "is_junction": strategic_role == "junction" or neighbors >= 4,
        "is_frontier": strategic_role == "frontier" or event.get("future_expansion_opened", 0) >= 2,
    }


def score_event_importance(event, simulation_context):
    """Returns an additive importance score plus supporting explanations."""
    before_state = simulation_context["before_state"]
    after_state = simulation_context["after_state"]
    total_turns = simulation_context["total_turns"]
    previous_related_event = simulation_context.get("previous_related_event")

    components = {}
    reasons = []

    if event.type == "attack":
        components["base_attack"] = IMPORTANCE_BASE_ATTACK
    elif event.type == "expand":
        components["base_expansion"] = IMPORTANCE_BASE_EXPANSION
    elif _is_development_event(event):
        components["base_development"] = IMPORTANCE_BASE_DEVELOPMENT
    else:
        return {
            "importance_score": 0.0,
            "importance_components": {},
            "importance_reasons": [],
        }

    phase_name = get_event_phase_name(event, total_turns)
    phase_bonus = {
        "early": IMPORTANCE_PHASE_EARLY,
        "mid": IMPORTANCE_PHASE_MID,
        "late": IMPORTANCE_PHASE_LATE,
    }[phase_name]
    components[f"{phase_name}_phase"] = phase_bonus

    before_counts = before_state["region_counts"]
    after_counts = after_state["region_counts"]
    faction_name = event.faction
    actor_regions_before = before_counts.get(faction_name, 0)
    actor_regions_after = after_counts.get(faction_name, 0)
    actor_region_delta = actor_regions_after - actor_regions_before

    if actor_region_delta > 0:
        components["territory_gain"] = actor_region_delta * IMPORTANCE_TERRITORY_GAIN
        reasons.append("gained territory")

    if event.type == "attack" and event.get("success", False):
        components["ownership_transfer"] = IMPORTANCE_OWNERSHIP_TRANSFER
        reasons.append("changed ownership")

    region_profile = get_region_profile(world=simulation_context["world"], event=event)
    if region_profile["is_junction"]:
        components["strategic_junction"] = IMPORTANCE_STRATEGIC_JUNCTION
        reasons.append("captured key junction")
    elif region_profile["is_frontier"]:
        components["strategic_frontier"] = IMPORTANCE_STRATEGIC_FRONTIER
        reasons.append("opened new routes")

    if region_profile["economic_value"] >= 2.5:
        components["resource_value"] = IMPORTANCE_RESOURCE_REGION
        reasons.append("high-resource region")

    rank_before = get_rank_map(before_state["treasuries"], before_counts)
    rank_after = get_rank_map(after_state["treasuries"], after_counts)
    rank_delta = rank_before.get(faction_name, 0) - rank_after.get(faction_name, 0)

    if rank_delta > 0:
        components["rank_shift"] = rank_delta * IMPORTANCE_RANK_STEP
        reasons.append("shifted leaderboard")

    leader_before = get_unique_leader(before_state["treasuries"], before_counts)
    leader_after = get_unique_leader(after_state["treasuries"], after_counts)
    if leader_after == faction_name and leader_after != leader_before:
        components["leader_change"] = IMPORTANCE_LEADER_CHANGE
        if "shifted leaderboard" not in reasons:
            reasons.append("shifted leaderboard")

    if is_close_contest(before_counts):
        components["close_contest"] = IMPORTANCE_CLOSE_CONTEST
        reasons.append("landed in a close contest")

    owner_before = event.get("owner_before")
    if event.type == "attack" and event.get("success", False) and owner_before in before_counts:
        defender_before = before_counts[owner_before]
        defender_after = after_counts.get(owner_before, 0)
        if defender_before > 0 and defender_after == 0:
            components["elimination"] = IMPORTANCE_ELIMINATION
            reasons.append("triggered rival elimination")
        elif defender_before >= 3 and defender_after <= 1:
            components["collapse"] = IMPORTANCE_COLLAPSE
            reasons.append("triggered rival collapse")

    late_decisive = (
        phase_name == "late"
        and is_close_contest(before_counts)
        and get_region_margin(after_counts) >= 3
    )
    if late_decisive:
        components["late_decisive_swing"] = IMPORTANCE_LATE_DECISIVE_SWING
        reasons.append("broke a close late game")

    if _is_development_event(event):
        taxable_change = event.get("taxable_change", event.get("resource_change", 0))
        if taxable_change <= 0.6 and actor_region_delta <= 0 and rank_delta <= 0:
            components["routine_development_penalty"] = IMPORTANCE_LOW_IMPACT_DEVELOPMENT_PENALTY
        elif rank_delta > 0 or leader_after == faction_name:
            reasons.append("strengthened economic lead")

    if previous_related_event is not None:
        if event.turn - previous_related_event.turn <= 2:
            components["redundancy_penalty"] = IMPORTANCE_REDUNDANT_EVENT_PENALTY

    if not is_close_contest(before_counts) and get_region_margin(before_counts) >= 5:
        leader = get_unique_leader(before_state["treasuries"], before_counts)
        if leader == faction_name and _is_development_event(event):
            components["already_decided_penalty"] = IMPORTANCE_ALREADY_DECIDED_PENALTY

    score = round(max(0.0, sum(components.values())), 2)
    importance_tier = get_event_importance_tier(event, score, reasons)

    return {
        "importance_score": score,
        "analysis_importance_tier": importance_tier,
        "analysis_importance_rank": IMPORTANCE_TIER_RANKS[importance_tier],
        "importance_components": components,
        "importance_reasons": list(dict.fromkeys(reasons)),
    }


def get_event_importance_tier(event, importance_score, reasons):
    """Returns a simple turning-point tier for one analyzed event."""
    reason_set = set(reasons)

    if "triggered rival elimination" in reason_set or "triggered rival collapse" in reason_set:
        return IMPORTANCE_TIER_VERY_HIGH

    if "shifted leaderboard" in reason_set or "broke a close late game" in reason_set:
        return IMPORTANCE_TIER_HIGH

    if event.type == "attack" and event.get("success", False):
        if importance_score >= 8.5 or "captured key junction" in reason_set:
            return IMPORTANCE_TIER_HIGH
        return IMPORTANCE_TIER_MEDIUM

    if event.type == "expand":
        if importance_score >= 7.5 or "captured key junction" in reason_set:
            return IMPORTANCE_TIER_MEDIUM
        return IMPORTANCE_TIER_LOW

    if _is_development_event(event):
        if "strengthened economic lead" in reason_set or importance_score >= 4.0:
            return IMPORTANCE_TIER_MEDIUM
        return IMPORTANCE_TIER_LOW

    return IMPORTANCE_TIER_LOW


def ensure_event_importance_scores(world):
    """Scores major events once and attaches analysis metadata to each event."""
    if getattr(world, "_importance_scores_ready", False):
        return

    replay_state = build_replay_state(world)
    previous_major_events = {}
    total_turns = len(world.metrics)

    for event in world.events:
        before_state = clone_replay_state(replay_state)
        after_state = apply_event_to_replay_state(event, replay_state)

        if event.type in MAJOR_EVENT_TYPES:
            previous_related_event = previous_major_events.get(
                (event.faction, event.type, event.region)
            )
            result = score_event_importance(
                event,
                {
                    "world": world,
                    "before_state": before_state,
                    "after_state": after_state,
                    "total_turns": total_turns,
                    "previous_related_event": previous_related_event,
                },
            )
            event.impact["importance_score"] = result["importance_score"]
            event.impact["analysis_importance_tier"] = result["analysis_importance_tier"]
            event.impact["analysis_importance_rank"] = result["analysis_importance_rank"]
            event.impact["importance_components"] = result["importance_components"]
            event.impact["importance_reasons"] = result["importance_reasons"]
            event.impact["phase_name"] = get_event_phase_name(event, total_turns)
            previous_major_events[(event.faction, event.type, event.region)] = event

        replay_state = after_state

    world._importance_scores_ready = True


def get_expand_event_importance(event):
    """Returns the importance score recorded on an expansion event."""
    if event.get("importance_score") is not None:
        return event.get("importance_score")
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
    if world is not None:
        ensure_event_importance_scores(world)

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
        "taxable_value": details.get("taxable_value", event.get("taxable_value", 0)),
        "neighbors": details.get("neighbors", event.get("neighbors", 0)),
        "unclaimed_neighbors": details.get(
            "unclaimed_neighbors",
            event.get("unclaimed_neighbors", 0),
        ),
        "cost": details.get("cost", event.get("cost", 0)),
        "importance_score": get_expand_event_importance(event),
        "analysis_importance_tier": impact.get("analysis_importance_tier", IMPORTANCE_TIER_LOW),
        "analysis_importance_rank": impact.get("analysis_importance_rank", 1),
        "importance_components": impact.get("importance_components", {}),
        "importance_reasons": impact.get("importance_reasons", []),
        "treasury_before": context.get("treasury_before"),
        "treasury_after": context.get("treasury_after", event.get("treasury_after")),
        "rank_before": context.get("rank_before"),
        "owner_before": context.get("owner_before"),
        "owner_after": impact.get("owner_after", event.faction),
        "treasury_change": impact.get("treasury_change"),
        "regions_gained": impact.get("regions_gained"),
        "strategic_role": impact.get("strategic_role"),
        "income_gain": impact.get("income_gain", details.get("taxable_value", details.get("resources", 0))),
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


def summarize_major_event(event, world=None):
    """Returns a normalized summary for a scored major event."""
    if world is not None:
        ensure_event_importance_scores(world)

    summary = {
        "turn": event.turn,
        "phase_name": event.impact.get("phase_name"),
        "type": event.type,
        "faction": event.faction,
        "region": event.region,
        "importance_score": event.get("importance_score", 0.0),
        "analysis_importance_tier": event.get("analysis_importance_tier", IMPORTANCE_TIER_LOW),
        "analysis_importance_rank": event.get("analysis_importance_rank", 1),
        "importance_components": event.get("importance_components", {}),
        "importance_reasons": event.get("importance_reasons", []),
        "owner_before": event.get("owner_before"),
        "owner_after": event.get("owner_after"),
        "treasury_before": event.get("treasury_before"),
        "treasury_after": event.get("treasury_after"),
        "treasury_change": event.get("treasury_change", 0),
        "success": event.get("success", False),
        "tags": list(event.tags),
    }

    if event.type == "expand":
        summary.update(summarize_expand_event(event, world=world))
    elif event.type == "attack":
        summary.update({
            "defender": event.get("defender"),
            "success_chance": event.get("success_chance"),
            "attack_strength": event.get("attack_strength"),
            "defense_strength": event.get("defense_strength"),
        })
    elif _is_development_event(event):
        summary.update({
            "resource_change": event.get("resource_change", 0),
            "new_resources": event.get("new_resources"),
            "taxable_change": event.get("taxable_change", 0),
            "new_taxable_value": event.get("new_taxable_value"),
        })

    return summary


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
    ensure_event_importance_scores(world)
    important_expansions = []

    for event in world.events:
        if event.type == "expand":
            importance_score = get_expand_event_importance(event)

            if importance_score >= minimum_score:
                important_expansions.append(summarize_expand_event(event, world=world))

    return important_expansions


def get_top_scoring_opening_claim(world, opening_turns=3):
    """Returns the first claim of the highest-scoring region in the opening events."""
    ensure_event_importance_scores(world)
    expansion_events = [
        event
        for event in world.events
        if event.type == "expand" and event.turn < opening_turns
    ]

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


def get_opening_development_leaders(world, opening_turns=5):
    """Returns the factions with the most development actions in the opening turns."""
    counts = {faction_name: 0 for faction_name in world.factions}

    for event in get_events_for_turn_range(world, end_turn=opening_turns - 1):
        if _is_development_event(event):
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
    """Returns initial ownership and native economic values for replay analysis."""
    owner_name_map = {
        faction.internal_id: faction_name
        for faction_name, faction in world.factions.items()
    }
    opening_region_history = world.region_history[0] if world.region_history else {}
    region_state = {}

    for region_name, region in world.regions.items():
        opening_region = opening_region_history.get(region_name, {})
        opening_owner = opening_region.get("owner", region.owner)
        region_state[region_name] = {
            "owner": owner_name_map.get(opening_owner, opening_owner),
            "resources": opening_region.get("resources", region.resources),
            "taxable_value": opening_region.get("taxable_value", get_region_taxable_value(region, world)),
        }

    return region_state


def replay_opening_treasury_snapshots(world, opening_turns=5):
    """Replays the opening turns and returns treasury snapshots after each turn."""
    region_state = build_initial_opening_state(world)
    treasuries = {
        faction_name: faction.starting_treasury
        for faction_name, faction in world.factions.items()
    }
    snapshots = []

    for turn in range(opening_turns):
        turn_events = [event for event in world.events if event.turn == turn]

        for event in turn_events:
            faction_name = event.faction

            if event.type == "expand":
                treasuries[faction_name] -= event.details.get("cost", event.get("cost", 0))
                region_state[event.region]["owner"] = faction_name
            elif _is_development_event(event):
                region_state[event.region]["resources"] = event.get(
                    "new_resources",
                    region_state[event.region]["resources"] + event.get("development_amount", event.get("invest_amount", 0)),
                )
                region_state[event.region]["taxable_value"] = event.get(
                    "new_taxable_value",
                    region_state[event.region]["taxable_value"] + event.get("taxable_change", 0.0),
                )

        for region in region_state.values():
            if region["owner"] is not None:
                treasuries[region["owner"]] += int(round(region["taxable_value"]))

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
    ensure_event_importance_scores(world)
    return {
        "highest_scoring_claim": get_top_scoring_opening_claim(world, opening_turns=3),
        "expansion_leaders": get_opening_expansion_leaders(world, opening_turns=3),
        "development_leaders": get_opening_development_leaders(world, opening_turns=5),
        "investment_leaders": get_opening_development_leaders(world, opening_turns=5),
        "treasury_leaders": get_opening_treasury_leaders(world, opening_turns=5),
    }


def get_opening_investment_leaders(world, opening_turns=5):
    """Backward-compatible alias for opening development leaders."""
    return get_opening_development_leaders(world, opening_turns=opening_turns)


def get_faction_event_counts(world):
    """Returns counts of expand and develop actions by faction."""
    faction_event_counts = {}

    for faction_name in world.factions:
        faction_event_counts[faction_name] = {
            "expand": 0,
            "develop": 0,
            "invest": 0,
        }

    for event in world.events:
        faction_name = event.faction
        event_type = event.type

        if faction_name not in faction_event_counts:
            continue
        if event_type in faction_event_counts[faction_name]:
            faction_event_counts[faction_name][event_type] += 1
        if event_type == "invest":
            faction_event_counts[faction_name]["develop"] += 1

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


def get_scored_major_events(world, minimum_score=0.0, allowed_types=None):
    """Returns scored major events ordered by descending importance."""
    ensure_event_importance_scores(world)
    allowed_types = allowed_types or MAJOR_EVENT_TYPES
    scored_events = []

    for event in world.events:
        if event.type not in allowed_types:
            continue
        if event.get("importance_score", 0.0) < minimum_score:
            continue
        scored_events.append(summarize_major_event(event, world=world))

    scored_events.sort(
        key=lambda event: (
            event["analysis_importance_rank"],
            event["importance_score"],
            -event["turn"],
        ),
        reverse=True,
    )
    return scored_events


def get_key_events(world):
    """Returns a curated set of important events for summary purposes."""
    ensure_event_importance_scores(world)
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
