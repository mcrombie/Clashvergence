from __future__ import annotations

from itertools import combinations

from src.config import (
    DIPLOMACY_ALLIANCE_ATTACK_PENALTY,
    DIPLOMACY_ALLIANCE_BREAK_THRESHOLD,
    DIPLOMACY_ALLIANCE_THRESHOLD,
    DIPLOMACY_ETHNIC_CLAIM_PRESSURE_MAX,
    DIPLOMACY_ETHNIC_CLAIM_PRESSURE_PER_REGION,
    DIPLOMACY_ATTACK_GRIEVANCE_FAILURE,
    DIPLOMACY_ATTACK_GRIEVANCE_SUCCESS,
    DIPLOMACY_ATTACK_TRUST_HIT_FAILURE,
    DIPLOMACY_ATTACK_TRUST_HIT_SUCCESS,
    DIPLOMACY_OVERLORD_ATTACK_PENALTY,
    DIPLOMACY_BORDER_FRICTION_MAX,
    DIPLOMACY_BORDER_FRICTION_PER_EDGE,
    DIPLOMACY_DISTANT_PEACE_GAIN,
    DIPLOMACY_EXISTING_ACCORD_PEACE_BONUS,
    DIPLOMACY_GRIEVANCE_DECAY,
    DIPLOMACY_GRIEVANCE_MAX,
    DIPLOMACY_REGIME_ACCORD_CIVIL_WAR_MULTIPLIER,
    DIPLOMACY_REGIME_ACCORD_PER_DIPLOMATIC_FORM,
    DIPLOMACY_REGIME_ACCORD_SHARED_FORM_BONUS,
    DIPLOMACY_REGIME_CIVIL_WAR_LEGITIMACY_TENSION,
    DIPLOMACY_REGIME_DIFFERENCE_TENSION,
    DIPLOMACY_POLITY_TIER_DISTANCE_PENALTY,
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
    DIPLOMACY_STATE_PEER_THREAT,
    DIPLOMACY_SUBORDINATION_BREAK_THRESHOLD,
    DIPLOMACY_SUBORDINATION_MIN_PEACE_YEARS,
    DIPLOMACY_SUBORDINATION_THRESHOLD,
    DIPLOMACY_TRIBUTARY_ATTACK_PENALTY,
    DIPLOMACY_TRIBUTARY_MIN_POWER_RATIO,
    DIPLOMACY_TRIBUTARY_TRIBUTE_SHARE,
    DIPLOMACY_TRUCE_ATTACK_PENALTY,
    DIPLOMACY_TRUCE_DURATION,
    DIPLOMACY_TRUST_MAX,
    DIPLOMACY_VASSAL_MIN_POWER_RATIO,
    DIPLOMACY_VASSAL_TRIBUTE_SHARE,
)
from src.models import Event, RelationshipState, WorldState
from src.visibility import faction_knows_faction

REGIME_ACCORD_DIPLOMATIC_FORMS = {"council", "assembly", "republic"}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _get_polity_rank(polity_tier: str) -> int:
    return {
        "band": 0,
        "tribe": 1,
        "chiefdom": 2,
        "state": 3,
    }.get(polity_tier, 1)


def _is_republican_form(government_form: str) -> bool:
    return government_form in {"council", "assembly", "republic"}


def _estimate_faction_power(world: WorldState, faction_name: str) -> float:
    faction = world.factions[faction_name]
    owned_regions = 0
    population = 0
    for region in world.regions.values():
        if region.owner != faction_name:
            continue
        owned_regions += 1
        population += region.population
    return round(
        (owned_regions * 3.4)
        + (population / 110.0)
        + (max(0.0, float(faction.treasury)) * 0.45)
        + (_get_polity_rank(faction.polity_tier) * 2.4),
        3,
    )


def _get_subordination_profile(
    world: WorldState,
    overlord_name: str,
    subordinate_name: str,
) -> tuple[str, float, float]:
    overlord = world.factions[overlord_name]
    subordinate = world.factions[subordinate_name]
    subordination_type = (
        "vassal"
        if overlord.government_form in {"leader", "monarchy", "oligarchy"}
        or overlord.polity_tier == "chiefdom"
        else "tributary"
    )
    min_power_ratio = (
        DIPLOMACY_VASSAL_MIN_POWER_RATIO
        if subordination_type == "vassal"
        else DIPLOMACY_TRIBUTARY_MIN_POWER_RATIO
    )
    tribute_share = (
        DIPLOMACY_VASSAL_TRIBUTE_SHARE
        if subordination_type == "vassal"
        else DIPLOMACY_TRIBUTARY_TRIBUTE_SHARE
    )
    if _is_republican_form(subordinate.government_form):
        min_power_ratio += 0.12
        tribute_share -= 0.02
    if _is_republican_form(overlord.government_form):
        min_power_ratio -= 0.05
        tribute_share -= 0.03
    return (
        subordination_type,
        round(max(0.06, tribute_share), 3),
        round(max(1.2, min_power_ratio), 3),
    )


def canonical_relationship_pair(faction_a: str, faction_b: str) -> tuple[str, str]:
    return tuple(sorted((faction_a, faction_b)))


def initialize_relationships(world: WorldState) -> None:
    world.relationships = {}
    ensure_relationship_entries(world)


def _factions_have_diplomatic_contact(
    world: WorldState,
    faction_a: str,
    faction_b: str,
) -> bool:
    faction_a_state = world.factions.get(faction_a)
    faction_b_state = world.factions.get(faction_b)
    if faction_a_state is None or faction_b_state is None:
        return False
    if (
        not faction_a_state.known_factions
        and not faction_b_state.known_factions
        and not faction_a_state.known_regions
        and not faction_b_state.known_regions
    ):
        return True
    return (
        faction_knows_faction(world, faction_a, faction_b)
        and faction_knows_faction(world, faction_b, faction_a)
    )


def ensure_relationship_entries(world: WorldState) -> None:
    for faction_a, faction_b in combinations(sorted(world.factions), 2):
        if not _factions_have_diplomatic_contact(world, faction_a, faction_b):
            continue
        key = canonical_relationship_pair(faction_a, faction_b)
        world.relationships.setdefault(key, RelationshipState())


def get_relationship_state(
    world: WorldState,
    faction_a: str,
    faction_b: str,
) -> RelationshipState:
    key = canonical_relationship_pair(faction_a, faction_b)
    if key not in world.relationships:
        if not _factions_have_diplomatic_contact(world, faction_a, faction_b):
            return RelationshipState()
        world.relationships[key] = RelationshipState()
    return world.relationships[key]


def get_relationship_score(world: WorldState, faction_a: str, faction_b: str) -> float:
    if faction_a == faction_b:
        return 100.0
    return get_relationship_state(world, faction_a, faction_b).score


def get_relationship_status(world: WorldState, faction_a: str, faction_b: str) -> str:
    if faction_a == faction_b:
        return "self"
    key = canonical_relationship_pair(faction_a, faction_b)
    if key not in world.relationships and not _factions_have_diplomatic_contact(world, faction_a, faction_b):
        return "unknown"
    state = get_relationship_state(world, faction_a, faction_b)
    if state.status == "tributary" and state.subordinate_faction is not None:
        return "tributary" if state.subordinate_faction != faction_a else "overlord"
    return state.status


def get_faction_overlord(world: WorldState, faction_name: str) -> str | None:
    for (faction_a, faction_b), state in world.relationships.items():
        if state.status != "tributary" or state.subordinate_faction != faction_name:
            continue
        return faction_b if faction_a == faction_name else faction_a
    return None


def get_faction_tributaries(world: WorldState, faction_name: str) -> list[str]:
    tributaries: list[str] = []
    for (faction_a, faction_b), state in world.relationships.items():
        if state.status != "tributary" or state.subordinate_faction is None:
            continue
        overlord = faction_b if faction_a == state.subordinate_faction else faction_a
        if overlord == faction_name:
            tributaries.append(state.subordinate_faction)
    return sorted(tributaries)


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
        if rebel.rebel_conflict_type == "civil_war" and not rebel.proto_state:
            return -DIPLOMACY_REGIME_CIVIL_WAR_LEGITIMACY_TENSION
        return (
            DIPLOMACY_PROTO_REBEL_LINEAGE_BONUS
            if rebel.proto_state
            else DIPLOMACY_MATURE_REBEL_LINEAGE_BONUS
        )
    return 0.0


def _get_ethnic_claim_pressure(world: WorldState, faction_a: str, faction_b: str) -> float:
    faction_a_state = world.factions[faction_a]
    faction_b_state = world.factions[faction_b]
    if (
        faction_a_state.primary_ethnicity is None
        or faction_b_state.primary_ethnicity is None
        or faction_a_state.primary_ethnicity == faction_b_state.primary_ethnicity
    ):
        return 0.0

    from src.heartland import faction_has_ethnic_claim

    disputed_regions = 0
    for region in world.regions.values():
        if region.owner == faction_b and faction_has_ethnic_claim(world, region, faction_a):
            disputed_regions += 1
        elif region.owner == faction_a and faction_has_ethnic_claim(world, region, faction_b):
            disputed_regions += 1

    return min(
        DIPLOMACY_ETHNIC_CLAIM_PRESSURE_MAX,
        disputed_regions * DIPLOMACY_ETHNIC_CLAIM_PRESSURE_PER_REGION,
    )


def _get_polity_tier_modifier(world: WorldState, faction_a: str, faction_b: str) -> float:
    tier_order = {"band": 0, "tribe": 1, "chiefdom": 2, "state": 3}
    tier_a = world.factions[faction_a].polity_tier
    tier_b = world.factions[faction_b].polity_tier
    distance_penalty = abs(
        tier_order.get(tier_a, tier_order["tribe"])
        - tier_order.get(tier_b, tier_order["tribe"])
    ) * DIPLOMACY_POLITY_TIER_DISTANCE_PENALTY
    peer_threat = (
        DIPLOMACY_STATE_PEER_THREAT
        if tier_a == "state" and tier_b == "state"
        else 0.0
    )
    return distance_penalty + peer_threat


def _get_polity_tier_tension_reason(world: WorldState, faction_a: str, faction_b: str) -> str | None:
    tier_a = world.factions[faction_a].polity_tier
    tier_b = world.factions[faction_b].polity_tier
    if tier_a == "state" and tier_b == "state":
        return "peer_state_rivalry"
    if tier_a != tier_b:
        return "status_gap"
    return None


def _get_regime_tension(world: WorldState, faction_a: str, faction_b: str) -> tuple[float, str | None]:
    faction_a_state = world.factions[faction_a]
    faction_b_state = world.factions[faction_b]
    if (
        faction_a_state.primary_ethnicity is None
        or faction_b_state.primary_ethnicity is None
        or faction_a_state.primary_ethnicity != faction_b_state.primary_ethnicity
    ):
        return 0.0, None

    pressure = 0.0
    reason = None

    if faction_a_state.government_form != faction_b_state.government_form:
        pressure += DIPLOMACY_REGIME_DIFFERENCE_TENSION
        reason = "regime_difference"

    for claimant, other_name in ((faction_a_state, faction_b), (faction_b_state, faction_a)):
        if (
            claimant.rebel_conflict_type == "civil_war"
            and not claimant.proto_state
            and claimant.origin_faction == other_name
        ):
            pressure += DIPLOMACY_REGIME_CIVIL_WAR_LEGITIMACY_TENSION
            reason = "civil_war_legitimacy"
            break

    return pressure, reason


def _get_regime_accommodation(
    world: WorldState,
    faction_a: str,
    faction_b: str,
    state: RelationshipState | None = None,
) -> tuple[float, str | None]:
    faction_a_state = world.factions[faction_a]
    faction_b_state = world.factions[faction_b]
    if (
        faction_a_state.primary_ethnicity is None
        or faction_b_state.primary_ethnicity is None
        or faction_a_state.primary_ethnicity != faction_b_state.primary_ethnicity
    ):
        return 0.0, None

    if state is None:
        state = get_relationship_state(world, faction_a, faction_b)
    if state.status == "rival":
        return 0.0, None

    diplomatic_forms = sum(
        1
        for form in (faction_a_state.government_form, faction_b_state.government_form)
        if form in REGIME_ACCORD_DIPLOMATIC_FORMS
    )
    if diplomatic_forms == 0:
        return 0.0, None

    accommodation = diplomatic_forms * DIPLOMACY_REGIME_ACCORD_PER_DIPLOMATIC_FORM
    reason = "diplomatic_restraint"
    if faction_a_state.government_form == faction_b_state.government_form:
        accommodation += DIPLOMACY_REGIME_ACCORD_SHARED_FORM_BONUS
        reason = "same_people_accord"

    _regime_pressure, regime_reason = _get_regime_tension(world, faction_a, faction_b)
    if regime_reason == "civil_war_legitimacy":
        accommodation *= DIPLOMACY_REGIME_ACCORD_CIVIL_WAR_MULTIPLIER
        reason = "legitimacy_accommodation"

    return round(accommodation, 2), reason


def _resolve_subordination(
    world: WorldState,
    faction_a: str,
    faction_b: str,
    state: RelationshipState,
    shared_borders: int,
) -> tuple[str | None, str, float]:
    if state.truce_turns_remaining > 0:
        return None, "tributary", 0.0

    prior_subordinate = state.subordinate_faction
    if prior_subordinate is not None:
        prior_overlord = faction_b if prior_subordinate == faction_a else faction_a
        _subordination_type, _tribute_share, min_power_ratio = _get_subordination_profile(
            world,
            prior_overlord,
            prior_subordinate,
        )
        subordinate_power = max(0.1, _estimate_faction_power(world, prior_subordinate))
        overlord_power = max(0.1, _estimate_faction_power(world, prior_overlord))
        if (
            state.score >= DIPLOMACY_SUBORDINATION_BREAK_THRESHOLD
            and (overlord_power / subordinate_power) >= (min_power_ratio * 0.8)
        ):
            return (
                prior_subordinate,
                state.subordination_type or "tributary",
                max(0.0, float(state.tribute_share or 0.0)),
            )

    if (
        shared_borders <= 0
        or state.years_at_peace < DIPLOMACY_SUBORDINATION_MIN_PEACE_YEARS
        or state.score < DIPLOMACY_SUBORDINATION_THRESHOLD
    ):
        return None, "tributary", 0.0

    power_a = max(0.1, _estimate_faction_power(world, faction_a))
    power_b = max(0.1, _estimate_faction_power(world, faction_b))
    if abs(power_a - power_b) < 0.01:
        return None, "tributary", 0.0

    overlord_name = faction_a if power_a > power_b else faction_b
    subordinate_name = faction_b if overlord_name == faction_a else faction_a
    subordination_type, tribute_share, min_power_ratio = _get_subordination_profile(
        world,
        overlord_name,
        subordinate_name,
    )

    if (max(power_a, power_b) / min(power_a, power_b)) < min_power_ratio:
        return None, subordination_type, 0.0

    if _get_polity_rank(world.factions[overlord_name].polity_tier) < _get_polity_rank(world.factions[subordinate_name].polity_tier):
        return None, subordination_type, 0.0

    return subordinate_name, subordination_type, tribute_share


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


def _emit_subordination_change_event(
    world: WorldState,
    faction_a: str,
    faction_b: str,
    previous_subordinate: str | None,
    new_subordinate: str | None,
    subordination_type: str,
    tribute_share: float,
    score: float,
) -> None:
    if previous_subordinate == new_subordinate:
        return

    if previous_subordinate is not None:
        previous_overlord = faction_b if previous_subordinate == faction_a else faction_a
        world.events.append(Event(
            turn=world.turn,
            type="diplomacy_tributary_break",
            faction=previous_overlord,
            details={
                "counterpart": previous_subordinate,
                "subordinate": previous_subordinate,
                "overlord": previous_overlord,
                "subordination_type": subordination_type,
                "score": round(score, 2),
            },
            tags=["diplomacy", "tributary_break"],
            significance=abs(score),
        ))

    if new_subordinate is None:
        return

    new_overlord = faction_b if new_subordinate == faction_a else faction_a
    world.events.append(Event(
        turn=world.turn,
        type="diplomacy_tributary",
        faction=new_overlord,
        details={
            "counterpart": new_subordinate,
            "subordinate": new_subordinate,
            "overlord": new_overlord,
            "subordination_type": subordination_type,
            "tribute_share": round(tribute_share, 3),
            "score": round(score, 2),
        },
        tags=["diplomacy", "tributary", subordination_type],
        significance=abs(score),
    ))


def update_relationships(world: WorldState) -> None:
    ensure_relationship_entries(world)
    conflict_pairs = _process_conflict_memory(world)

    for faction_a, faction_b in combinations(sorted(world.factions), 2):
        if not _factions_have_diplomatic_contact(world, faction_a, faction_b):
            continue
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
            if state.status in {"non_aggression_pact", "alliance", "tributary"}:
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
        ethnic_claim_pressure = _get_ethnic_claim_pressure(world, faction_a, faction_b)
        polity_tier_pressure = _get_polity_tier_modifier(world, faction_a, faction_b)
        regime_pressure, _regime_reason = _get_regime_tension(world, faction_a, faction_b)
        regime_accommodation, _regime_accommodation_reason = _get_regime_accommodation(
            world,
            faction_a,
            faction_b,
            state,
        )
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
                + regime_accommodation
                - state.grievance
                - state.border_friction
                - ethnic_claim_pressure
                - polity_tier_pressure
                - regime_pressure,
                DIPLOMACY_SCORE_MIN,
                DIPLOMACY_SCORE_MAX,
            ),
            2,
        )

        previous_status = state.status
        previous_subordinate = state.subordinate_faction
        previous_subordination_type = state.subordination_type
        previous_tribute_share = state.tribute_share
        base_status = _derive_status(state)
        subordinate_name, subordination_type, tribute_share = _resolve_subordination(
            world,
            faction_a,
            faction_b,
            state,
            shared_borders,
        )
        if subordinate_name is not None:
            state.status = "tributary"
            state.subordinate_faction = subordinate_name
            state.subordination_type = subordination_type
            state.tribute_share = tribute_share
            state.subordination_turns = (
                state.subordination_turns + 1
                if previous_subordinate == subordinate_name
                else 1
            )
        else:
            state.status = base_status
            state.subordinate_faction = None
            state.subordination_type = "tributary"
            state.tribute_share = 0.0
            state.subordination_turns = 0

        if previous_subordinate != state.subordinate_faction or (
            previous_status == "tributary" and state.status != "tributary"
        ):
            _emit_subordination_change_event(
                world,
                faction_a,
                faction_b,
                previous_subordinate,
                state.subordinate_faction,
                state.subordination_type if state.subordinate_faction is not None else previous_subordination_type,
                state.tribute_share if state.subordinate_faction is not None else previous_tribute_share,
                state.score,
            )
        elif state.status != "tributary":
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
    if status == "tributary":
        return (DIPLOMACY_TRIBUTARY_ATTACK_PENALTY, status)
    if status == "overlord":
        return (DIPLOMACY_OVERLORD_ATTACK_PENALTY, status)
    if status == "rival":
        return (DIPLOMACY_RIVAL_ATTACK_BONUS, status)
    return (0, status)


def apply_tributary_flows(
    world: WorldState,
    economy_snapshot: dict[str, dict[str, float | int]] | None = None,
) -> None:
    for faction in world.factions.values():
        faction.tribute_income = 0.0
        faction.tribute_paid = 0.0

    for (faction_a, faction_b), state in world.relationships.items():
        if state.status != "tributary" or state.subordinate_faction is None:
            continue
        subordinate_name = state.subordinate_faction
        overlord_name = faction_b if subordinate_name == faction_a else faction_a
        subordinate = world.factions.get(subordinate_name)
        overlord = world.factions.get(overlord_name)
        if subordinate is None or overlord is None:
            continue

        subordinate_income = float((economy_snapshot or {}).get(subordinate_name, {}).get("effective_income", 0.0) or 0.0)
        income_due = max(0.0, subordinate_income) * max(0.0, float(state.tribute_share or 0.0))
        treasury_buffer = max(0.0, float(subordinate.treasury) - 1.0)
        tribute_paid = round(min(treasury_buffer, income_due), 2)
        if tribute_paid <= 0.0:
            continue

        subordinate.treasury = round(float(subordinate.treasury) - tribute_paid, 2)
        overlord.treasury = round(float(overlord.treasury) + tribute_paid, 2)
        subordinate.tribute_paid = round(subordinate.tribute_paid + tribute_paid, 2)
        overlord.tribute_income = round(overlord.tribute_income + tribute_paid, 2)


def seed_rebel_origin_relationship(
    world: WorldState,
    rebel_faction: str,
    origin_faction: str,
) -> None:
    state = get_relationship_state(world, rebel_faction, origin_faction)
    state.status = "truce"
    state.subordinate_faction = None
    state.subordination_type = "tributary"
    state.tribute_share = 0.0
    state.subordination_turns = 0
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
    from src.heartland import faction_has_ethnic_claim

    counterpart_scores = []
    alliance_count = 0
    pact_count = 0
    truce_count = 0
    rival_count = 0
    tributary_count = 0
    vassal_count = 0
    claim_disputes: dict[str, int] = {}
    polity_tensions: list[tuple[str, float, str | None]] = []
    regime_tensions: list[tuple[str, float, str | None]] = []
    regime_accommodations: list[tuple[str, float, str | None]] = []
    tributaries: list[tuple[str, float, str]] = []
    overlord_name = None
    overlord_type = None

    for other_faction in world.factions:
        if other_faction == faction_name:
            continue
        if not _factions_have_diplomatic_contact(world, faction_name, other_faction):
            continue
        state = get_relationship_state(world, faction_name, other_faction)
        status = get_relationship_status(world, faction_name, other_faction)
        counterpart_scores.append((other_faction, state.score, status))
        polity_tension = _get_polity_tier_modifier(world, faction_name, other_faction)
        if polity_tension > 0:
            polity_tensions.append((
                other_faction,
                polity_tension,
                _get_polity_tier_tension_reason(world, faction_name, other_faction),
            ))
        regime_tension, regime_reason = _get_regime_tension(world, faction_name, other_faction)
        if regime_tension > 0:
            regime_tensions.append((other_faction, regime_tension, regime_reason))
        regime_accommodation, regime_accommodation_reason = _get_regime_accommodation(
            world,
            faction_name,
            other_faction,
            state,
        )
        if regime_accommodation > 0:
            regime_accommodations.append((
                other_faction,
                regime_accommodation,
                regime_accommodation_reason,
            ))
        if status == "tributary":
            tributary_count += 1
            tributaries.append((
                other_faction,
                max(0.0, float(state.tribute_share or 0.0)),
                state.subordination_type or "tributary",
            ))
            if (state.subordination_type or "tributary") == "vassal":
                vassal_count += 1
        elif status == "overlord":
            overlord_name = other_faction
            overlord_type = state.subordination_type or "tributary"
        elif state.status == "alliance":
            alliance_count += 1
        elif state.status == "truce":
            truce_count += 1
        elif state.status == "non_aggression_pact":
            pact_count += 1
        elif state.status == "rival":
            rival_count += 1

    for region in world.regions.values():
        if region.owner is None or region.owner == faction_name:
            continue
        if not _factions_have_diplomatic_contact(world, faction_name, region.owner):
            continue
        if faction_has_ethnic_claim(world, region, faction_name):
            claim_disputes[region.owner] = claim_disputes.get(region.owner, 0) + 1

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

    top_claim_dispute = None
    top_claim_dispute_regions = 0
    if claim_disputes:
        top_claim_dispute, top_claim_dispute_regions = max(
            claim_disputes.items(),
            key=lambda item: (item[1], item[0]),
        )

    top_polity_tension = None
    top_polity_tension_value = 0.0
    top_polity_tension_reason = None
    if polity_tensions:
        top_polity_tension, top_polity_tension_value, top_polity_tension_reason = max(
            polity_tensions,
            key=lambda item: (item[1], item[0]),
        )

    top_regime_tension = None
    top_regime_tension_value = 0.0
    top_regime_tension_reason = None
    if regime_tensions:
        top_regime_tension, top_regime_tension_value, top_regime_tension_reason = max(
            regime_tensions,
            key=lambda item: (item[1], item[0]),
        )

    top_regime_accommodation = None
    top_regime_accommodation_value = 0.0
    top_regime_accommodation_reason = None
    if regime_accommodations:
        top_regime_accommodation, top_regime_accommodation_value, top_regime_accommodation_reason = max(
            regime_accommodations,
            key=lambda item: (item[1], item[0]),
        )

    top_tributary = None
    top_tributary_share = 0.0
    top_tributary_type = None
    if tributaries:
        top_tributary, top_tributary_share, top_tributary_type = max(
            tributaries,
            key=lambda item: (item[1], item[0]),
        )

    return {
        "top_ally": top_ally,
        "top_rival": top_rival,
        "overlord": overlord_name,
        "overlord_type": overlord_type,
        "top_tributary": top_tributary,
        "top_tributary_share": round(top_tributary_share, 3),
        "top_tributary_type": top_tributary_type,
        "top_claim_dispute": top_claim_dispute,
        "top_claim_dispute_ethnicity": world.factions[faction_name].primary_ethnicity,
        "top_claim_dispute_regions": top_claim_dispute_regions,
        "claim_dispute_count": len(claim_disputes),
        "top_polity_tension": top_polity_tension,
        "top_polity_tension_value": round(top_polity_tension_value, 2),
        "top_polity_tension_reason": top_polity_tension_reason,
        "top_regime_tension": top_regime_tension,
        "top_regime_tension_value": round(top_regime_tension_value, 2),
        "top_regime_tension_reason": top_regime_tension_reason,
        "regime_tension_count": len(regime_tensions),
        "top_regime_accommodation": top_regime_accommodation,
        "top_regime_accommodation_value": round(top_regime_accommodation_value, 2),
        "top_regime_accommodation_reason": top_regime_accommodation_reason,
        "regime_accommodation_count": len(regime_accommodations),
        "alliance_count": alliance_count,
        "truce_count": truce_count,
        "pact_count": pact_count,
        "rival_count": rival_count,
        "tributary_count": tributary_count,
        "vassal_count": vassal_count,
    }
