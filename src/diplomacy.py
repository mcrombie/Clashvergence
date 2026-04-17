from __future__ import annotations

from itertools import combinations

from src.config import (
    DIPLOMACY_ALLIANCE_ATTACK_PENALTY,
    DIPLOMACY_ALLIANCE_BREAK_THRESHOLD,
    DIPLOMACY_ALLIANCE_THRESHOLD,
    DIPLOMACY_ATTACK_GRIEVANCE_FAILURE,
    DIPLOMACY_ATTACK_GRIEVANCE_SUCCESS,
    DIPLOMACY_ATTACK_TRUST_HIT_FAILURE,
    DIPLOMACY_ATTACK_TRUST_HIT_SUCCESS,
    DIPLOMACY_BORDER_FRICTION_MAX,
    DIPLOMACY_BORDER_FRICTION_PER_EDGE,
    DIPLOMACY_DISTANT_PEACE_GAIN,
    DIPLOMACY_EXISTING_ACCORD_PEACE_BONUS,
    DIPLOMACY_GRIEVANCE_DECAY,
    DIPLOMACY_GRIEVANCE_MAX,
    DIPLOMACY_MATURE_REBEL_LINEAGE_BONUS,
    DIPLOMACY_PACT_ATTACK_PENALTY,
    DIPLOMACY_PACT_BREAK_THRESHOLD,
    DIPLOMACY_PACT_THRESHOLD,
    DIPLOMACY_PEACE_SCORE_MAX,
    DIPLOMACY_PEACE_SCORE_PER_TURN,
    DIPLOMACY_PROTO_REBEL_LINEAGE_BONUS,
    DIPLOMACY_REBEL_HOSTILITY_ON_ATTACK,
    DIPLOMACY_REBEL_SECESSION_INITIAL_GRIEVANCE,
    DIPLOMACY_REBEL_SECESSION_INITIAL_TRUST,
    DIPLOMACY_REBEL_SECESSION_TRUCE_DURATION,
    DIPLOMACY_RIVAL_ATTACK_BONUS,
    DIPLOMACY_RIVAL_BREAK_THRESHOLD,
    DIPLOMACY_RIVAL_THRESHOLD,
    DIPLOMACY_RUNAWAY_COALITION_BONUS,
    DIPLOMACY_RUNAWAY_TARGET_PENALTY,
    DIPLOMACY_SCORE_MAX,
    DIPLOMACY_SCORE_MIN,
    DIPLOMACY_SHARED_BORDER_PEACE_GAIN,
    DIPLOMACY_TRUCE_ATTACK_PENALTY,
    DIPLOMACY_TRUCE_DURATION,
    DIPLOMACY_TRUST_MAX,
)
from src.models import Event, RelationshipState, WorldState


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def canonical_relationship_pair(faction_a: str, faction_b: str) -> tuple[str, str]:
    return tuple(sorted((faction_a, faction_b)))


def initialize_relationships(world: WorldState) -> None:
    world.relationships = {}
    ensure_relationship_entries(world)


def ensure_relationship_entries(world: WorldState) -> None:
    for faction_a, faction_b in combinations(sorted(world.factions), 2):
        key = canonical_relationship_pair(faction_a, faction_b)
        world.relationships.setdefault(key, RelationshipState())


def get_relationship_state(
    world: WorldState,
    faction_a: str,
    faction_b: str,
) -> RelationshipState:
    key = canonical_relationship_pair(faction_a, faction_b)
    if key not in world.relationships:
        world.relationships[key] = RelationshipState()
    return world.relationships[key]


def get_relationship_score(world: WorldState, faction_a: str, faction_b: str) -> float:
    if faction_a == faction_b:
        return 100.0
    return get_relationship_state(world, faction_a, faction_b).score


def get_relationship_status(world: WorldState, faction_a: str, faction_b: str) -> str:
    if faction_a == faction_b:
        return "self"
    return get_relationship_state(world, faction_a, faction_b).status


def _count_shared_borders(world: WorldState, faction_a: str, faction_b: str) -> int:
    seen_edges: set[tuple[str, str]] = set()
    shared_edges = 0
    for region_name, region in world.regions.items():
        if region.owner != faction_a:
            continue
        for neighbor_name in region.neighbors:
            neighbor = world.regions[neighbor_name]
            if neighbor.owner != faction_b:
                continue
            edge = tuple(sorted((region_name, neighbor_name)))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            shared_edges += 1
    return shared_edges


def _get_doctrine_affinity(world: WorldState, faction_a: str, faction_b: str) -> float:
    faction_a_profile = world.factions[faction_a].doctrine_profile
    faction_b_profile = world.factions[faction_b].doctrine_profile
    average_difference = (
        abs(faction_a_profile.expansion_posture - faction_b_profile.expansion_posture)
        + abs(faction_a_profile.war_posture - faction_b_profile.war_posture)
        + abs(faction_a_profile.development_posture - faction_b_profile.development_posture)
        + abs(faction_a_profile.insularity - faction_b_profile.insularity)
    ) / 4
    return round((0.5 - average_difference) * 8, 2)


def _get_unique_leader(world: WorldState) -> str | None:
    standings = []
    owned_counts = {
        faction_name: 0
        for faction_name in world.factions
    }
    for region in world.regions.values():
        if region.owner in owned_counts:
            owned_counts[region.owner] += 1
    for faction_name, faction in world.factions.items():
        standings.append((faction_name, faction.treasury, owned_counts[faction_name]))
    standings.sort(key=lambda item: (item[1], item[2]), reverse=True)
    if len(standings) < 2:
        return standings[0][0] if standings else None
    leader_name, leader_treasury, leader_regions = standings[0]
    runner_name, runner_treasury, runner_regions = standings[1]
    if (leader_treasury, leader_regions) == (runner_treasury, runner_regions):
        return None
    if leader_treasury - runner_treasury >= 3 or leader_regions - runner_regions >= 2:
        return leader_name
    return None


def _get_runaway_modifier(world: WorldState, faction_a: str, faction_b: str) -> float:
    leader = _get_unique_leader(world)
    if leader is None:
        return 0.0
    if leader in {faction_a, faction_b}:
        return DIPLOMACY_RUNAWAY_TARGET_PENALTY
    return DIPLOMACY_RUNAWAY_COALITION_BONUS


def _get_lineage_modifier(world: WorldState, faction_a: str, faction_b: str) -> float:
    faction_a_state = world.factions[faction_a]
    faction_b_state = world.factions[faction_b]

    for rebel, other in ((faction_a_state, faction_b_state), (faction_b_state, faction_a_state)):
        if not rebel.is_rebel or rebel.origin_faction != other.name:
            continue
        return (
            DIPLOMACY_PROTO_REBEL_LINEAGE_BONUS
            if rebel.proto_state
            else DIPLOMACY_MATURE_REBEL_LINEAGE_BONUS
        )
    return 0.0


def _process_conflict_memory(world: WorldState) -> set[tuple[str, str]]:
    conflict_pairs: set[tuple[str, str]] = set()
    for event in world.events:
        if event.turn != world.turn or event.type != "attack":
            continue
        defender = event.get("defender")
        if defender is None or defender not in world.factions or event.faction not in world.factions:
            continue
        key = canonical_relationship_pair(event.faction, defender)
        conflict_pairs.add(key)
        relationship = get_relationship_state(world, event.faction, defender)
        grievance_gain = (
            DIPLOMACY_ATTACK_GRIEVANCE_SUCCESS
            if event.get("success", False)
            else DIPLOMACY_ATTACK_GRIEVANCE_FAILURE
        )
        attacker_faction = world.factions[event.faction]
        defender_faction = world.factions[defender]
        if (
            attacker_faction.origin_faction == defender
            or defender_faction.origin_faction == event.faction
        ):
            grievance_gain += DIPLOMACY_REBEL_HOSTILITY_ON_ATTACK
        relationship.grievance = _clamp(
            relationship.grievance + grievance_gain,
            0.0,
            DIPLOMACY_GRIEVANCE_MAX,
        )
        relationship.trust = _clamp(
            relationship.trust - (
                DIPLOMACY_ATTACK_TRUST_HIT_SUCCESS
                if event.get("success", False)
                else DIPLOMACY_ATTACK_TRUST_HIT_FAILURE
            ),
            0.0,
            DIPLOMACY_TRUST_MAX,
        )
        relationship.truce_turns_remaining = max(
            relationship.truce_turns_remaining,
            DIPLOMACY_TRUCE_DURATION,
        )
        relationship.years_at_peace = 0
        relationship.wars_fought += 1
        relationship.last_conflict_turn = world.turn
        previous_status = relationship.status
        relationship.status = "truce"
        if previous_status != "truce":
            world.events.append(Event(
                turn=world.turn,
                type="diplomacy_truce",
                faction=event.faction,
                details={
                    "counterpart": defender,
                    "duration": relationship.truce_turns_remaining,
                    "reason": "war_exhaustion",
                },
                tags=["diplomacy", "truce", "war"],
                significance=relationship.grievance,
            ))
    return conflict_pairs


def _derive_status(state: RelationshipState) -> str:
    if state.truce_turns_remaining > 0:
        return "truce"

    score = state.score
    current = state.status

    if current == "alliance":
        if score >= DIPLOMACY_ALLIANCE_BREAK_THRESHOLD:
            return "alliance"
    if current == "non_aggression_pact":
        if score >= DIPLOMACY_PACT_BREAK_THRESHOLD:
            return "non_aggression_pact"
    if current == "rival":
        if score <= DIPLOMACY_RIVAL_BREAK_THRESHOLD:
            return "rival"

    if score >= DIPLOMACY_ALLIANCE_THRESHOLD and state.years_at_peace >= 2:
        return "alliance"
    if score >= DIPLOMACY_PACT_THRESHOLD and state.years_at_peace >= 1:
        return "non_aggression_pact"
    if score <= DIPLOMACY_RIVAL_THRESHOLD:
        return "rival"
    return "neutral"


def _emit_status_change_event(
    world: WorldState,
    faction_a: str,
    faction_b: str,
    previous_status: str,
    new_status: str,
    score: float,
) -> None:
    if previous_status == new_status:
        return

    if previous_status == "truce" and new_status != "truce":
        world.events.append(Event(
            turn=world.turn,
            type="diplomacy_truce_end",
            faction=faction_a,
            details={
                "counterpart": faction_b,
                "new_status": new_status,
                "score": round(score, 2),
            },
            tags=["diplomacy", "truce_end"],
            significance=abs(score),
        ))
        if new_status == "neutral":
            return

    if previous_status in {"alliance", "non_aggression_pact"} and new_status not in {
        "alliance",
        "non_aggression_pact",
    }:
        world.events.append(Event(
            turn=world.turn,
            type="diplomacy_break",
            faction=faction_a,
            details={
                "counterpart": faction_b,
                "previous_status": previous_status,
                "new_status": new_status,
                "score": round(score, 2),
            },
            tags=["diplomacy", "break"],
            significance=abs(score),
        ))
        return

    event_type = {
        "rival": "diplomacy_rivalry",
        "non_aggression_pact": "diplomacy_pact",
        "alliance": "diplomacy_alliance",
    }.get(new_status)
    if event_type is None:
        return

    world.events.append(Event(
        turn=world.turn,
        type=event_type,
        faction=faction_a,
        details={
            "counterpart": faction_b,
            "previous_status": previous_status,
            "new_status": new_status,
            "score": round(score, 2),
        },
        tags=["diplomacy", new_status],
        significance=abs(score),
    ))


def update_relationships(world: WorldState) -> None:
    ensure_relationship_entries(world)
    conflict_pairs = _process_conflict_memory(world)

    for faction_a, faction_b in combinations(sorted(world.factions), 2):
        state = get_relationship_state(world, faction_a, faction_b)
        shared_borders = _count_shared_borders(world, faction_a, faction_b)
        state.border_friction = min(
            DIPLOMACY_BORDER_FRICTION_MAX,
            shared_borders * DIPLOMACY_BORDER_FRICTION_PER_EDGE,
        )
        key = canonical_relationship_pair(faction_a, faction_b)

        if key not in conflict_pairs:
            if state.truce_turns_remaining > 0:
                state.truce_turns_remaining -= 1
            state.years_at_peace += 1
            peace_gain = (
                DIPLOMACY_DISTANT_PEACE_GAIN
                if shared_borders == 0
                else DIPLOMACY_SHARED_BORDER_PEACE_GAIN
            )
            if state.status in {"non_aggression_pact", "alliance"}:
                peace_gain += DIPLOMACY_EXISTING_ACCORD_PEACE_BONUS
            state.trust = _clamp(state.trust + peace_gain, 0.0, DIPLOMACY_TRUST_MAX)
            state.grievance = _clamp(
                state.grievance - DIPLOMACY_GRIEVANCE_DECAY,
                0.0,
                DIPLOMACY_GRIEVANCE_MAX,
            )

        doctrine_affinity = _get_doctrine_affinity(world, faction_a, faction_b)
        runaway_modifier = _get_runaway_modifier(world, faction_a, faction_b)
        lineage_modifier = _get_lineage_modifier(world, faction_a, faction_b)
        peace_modifier = min(
            DIPLOMACY_PEACE_SCORE_MAX,
            state.years_at_peace * DIPLOMACY_PEACE_SCORE_PER_TURN,
        )

        state.score = round(
            _clamp(
                state.trust
                + peace_modifier
                + doctrine_affinity
                + runaway_modifier
                + lineage_modifier
                - state.grievance
                - state.border_friction,
                DIPLOMACY_SCORE_MIN,
                DIPLOMACY_SCORE_MAX,
            ),
            2,
        )

        previous_status = state.status
        state.status = _derive_status(state)
        _emit_status_change_event(world, faction_a, faction_b, previous_status, state.status, state.score)


def get_attack_diplomacy_modifier(
    world: WorldState,
    attacker_name: str,
    defender_name: str,
) -> tuple[int, str]:
    status = get_relationship_status(world, attacker_name, defender_name)
    if status == "alliance":
        return (DIPLOMACY_ALLIANCE_ATTACK_PENALTY, status)
    if status == "truce":
        return (DIPLOMACY_TRUCE_ATTACK_PENALTY, status)
    if status == "non_aggression_pact":
        return (DIPLOMACY_PACT_ATTACK_PENALTY, status)
    if status == "rival":
        return (DIPLOMACY_RIVAL_ATTACK_BONUS, status)
    return (0, status)


def seed_rebel_origin_relationship(
    world: WorldState,
    rebel_faction: str,
    origin_faction: str,
) -> None:
    state = get_relationship_state(world, rebel_faction, origin_faction)
    state.status = "truce"
    state.truce_turns_remaining = DIPLOMACY_REBEL_SECESSION_TRUCE_DURATION
    state.years_at_peace = 0
    state.trust = max(state.trust, DIPLOMACY_REBEL_SECESSION_INITIAL_TRUST)
    state.grievance = max(state.grievance, DIPLOMACY_REBEL_SECESSION_INITIAL_GRIEVANCE)
    state.score = round(
        _clamp(
            state.trust - state.grievance + DIPLOMACY_PROTO_REBEL_LINEAGE_BONUS,
            DIPLOMACY_SCORE_MIN,
            DIPLOMACY_SCORE_MAX,
        ),
        2,
    )
    world.events.append(Event(
        turn=world.turn,
        type="diplomacy_truce",
        faction=origin_faction,
        details={
            "counterpart": rebel_faction,
            "duration": state.truce_turns_remaining,
            "reason": "secession_settlement",
        },
        tags=["diplomacy", "truce", "secession"],
        significance=abs(state.score),
    ))


def get_faction_diplomacy_summary(world: WorldState, faction_name: str) -> dict[str, object]:
    counterpart_scores = []
    alliance_count = 0
    pact_count = 0
    truce_count = 0
    rival_count = 0

    for other_faction in world.factions:
        if other_faction == faction_name:
            continue
        state = get_relationship_state(world, faction_name, other_faction)
        counterpart_scores.append((other_faction, state.score, state.status))
        if state.status == "alliance":
            alliance_count += 1
        elif state.status == "truce":
            truce_count += 1
        elif state.status == "non_aggression_pact":
            pact_count += 1
        elif state.status == "rival":
            rival_count += 1

    top_ally = None
    allied_candidates = [item for item in counterpart_scores if item[1] > 0]
    if allied_candidates:
        allied_candidates.sort(key=lambda item: (item[1], item[0]), reverse=True)
        top_ally = allied_candidates[0][0]

    top_rival = None
    rival_candidates = [item for item in counterpart_scores if item[1] < 0]
    if rival_candidates:
        rival_candidates.sort(key=lambda item: (item[1], item[0]))
        top_rival = rival_candidates[0][0]

    return {
        "top_ally": top_ally,
        "top_rival": top_rival,
        "alliance_count": alliance_count,
        "truce_count": truce_count,
        "pact_count": pact_count,
        "rival_count": rival_count,
    }
