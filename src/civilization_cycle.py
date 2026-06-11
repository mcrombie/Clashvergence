from __future__ import annotations

import random

from src.models import Event, Faction, WorldState


PHASE_PIONEERS = "pioneers"
PHASE_CONQUESTS = "conquests"
PHASE_COMMERCE = "commerce"
PHASE_AFFLUENCE = "affluence"
PHASE_INTELLECT = "intellect"
PHASE_DECADENCE = "decadence"
PHASE_DECLINE = "decline"

PHASE_ORDER = [
    PHASE_PIONEERS,
    PHASE_CONQUESTS,
    PHASE_COMMERCE,
    PHASE_AFFLUENCE,
    PHASE_INTELLECT,
    PHASE_DECADENCE,
    PHASE_DECLINE,
]

SOCIAL_ENERGY_EQUILIBRIUM = {
    PHASE_PIONEERS: 0.85,
    PHASE_CONQUESTS: 0.72,
    PHASE_COMMERCE: 0.52,
    PHASE_AFFLUENCE: 0.38,
    PHASE_INTELLECT: 0.28,
    PHASE_DECADENCE: 0.18,
    PHASE_DECLINE: 0.12,
}

SOCIAL_ENERGY_HARDSHIP_GAIN = 0.05
SOCIAL_ENERGY_PROSPERITY_LOSS = 0.04
SOCIAL_ENERGY_MEAN_REVERSION = 0.015

RELIGIOUS_VITALITY_REVERSION_RATE = 0.08
VITALITY_REFORM_PRESSURE_RATE = 0.04

INTELLECTUAL_REVERSION_RATE = 0.06
INTELLECTUAL_IDEOLOGY_PRESSURE = 0.03
INTELLECTUAL_RELIGION_PRESSURE = 0.025

MATERIAL_ACCUMULATION_SMOOTHING = 0.10

PHASE_BASE_CHANCE = {
    PHASE_PIONEERS: 0.07,
    PHASE_CONQUESTS: 0.06,
    PHASE_COMMERCE: 0.05,
    PHASE_AFFLUENCE: 0.05,
    PHASE_INTELLECT: 0.05,
    PHASE_DECADENCE: 0.04,
    PHASE_DECLINE: 0.09,
}

PHASE_MIN_TURNS = {
    PHASE_PIONEERS: 8,
    PHASE_CONQUESTS: 12,
    PHASE_COMMERCE: 18,
    PHASE_AFFLUENCE: 20,
    PHASE_INTELLECT: 15,
    PHASE_DECADENCE: 12,
    PHASE_DECLINE: 8,
}

# Condition relaxation begins once a phase has clearly exceeded its nominal
# historical window. Chance still controls the transition before this point.
PHASE_RELAXATION_TURNS = {
    PHASE_PIONEERS: 45,
    PHASE_CONQUESTS: 70,
    PHASE_COMMERCE: 80,
    PHASE_AFFLUENCE: 80,
    PHASE_INTELLECT: 65,
    PHASE_DECADENCE: 70,
    PHASE_DECLINE: 45,
}

REVIVAL_HARDSHIP_THRESHOLD = 0.50
REVIVAL_VITALITY_THRESHOLD = 0.65
REVIVAL_SURGE_REQUIRED = 5


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def initialize_rebel_civilization_cycle(faction: Faction) -> None:
    faction.civilizational_phase = PHASE_PIONEERS
    faction.civilizational_phase_turns = 0
    faction.social_energy = 0.82
    faction.religious_vitality = 0.72
    faction.material_accumulation = 0.12
    faction.intellectual_activity = 0.08
    faction.revival_surge_turns = 0


def infer_initial_phase(faction: Faction) -> str:
    if faction.administrative_overextension > 0.30:
        return PHASE_DECADENCE
    if faction.material_accumulation > 0.60:
        return PHASE_AFFLUENCE
    if faction.material_accumulation > 0.42:
        return PHASE_COMMERCE
    return PHASE_CONQUESTS


def initialize_established_civilization_cycle(faction: Faction) -> None:
    faction.civilizational_phase = infer_initial_phase(faction)
    faction.civilizational_phase_turns = 0
    faction.revival_surge_turns = 0


def _update_material_accumulation(faction: Faction) -> None:
    food_consumption = max(faction.food_consumption, 1.0)
    food_signal = _clamp(faction.food_balance / food_consumption * 0.5 + 0.5, 0.0, 1.0)
    trade_signal = _clamp(faction.trade_income / 30.0, 0.0, 1.0)
    treasury_signal = _clamp(faction.treasury / 200.0, 0.0, 1.0)

    hardship_drag = _clamp(
        faction.famine_pressure * 0.40
        + faction.epidemic_pressure * 0.25
        + faction.shock_exposure * 0.20
        + _clamp(faction.food_deficit / food_consumption, 0.0, 1.0) * 0.15,
        0.0,
        1.0,
    )

    raw = _clamp(
        food_signal * 0.30
        + trade_signal * 0.30
        + treasury_signal * 0.25
        + (1.0 - hardship_drag) * 0.15,
        0.0,
        1.0,
    )

    faction.material_accumulation = round(
        faction.material_accumulation * (1.0 - MATERIAL_ACCUMULATION_SMOOTHING)
        + raw * MATERIAL_ACCUMULATION_SMOOTHING,
        3,
    )


def _update_social_energy(faction: Faction) -> None:
    food_consumption = max(faction.food_consumption, 1.0)

    hardship = _clamp(
        faction.famine_pressure * 0.35
        + faction.epidemic_pressure * 0.25
        + faction.shock_exposure * 0.20
        + _clamp(faction.food_deficit / food_consumption, 0.0, 1.0) * 0.20,
        0.0,
        1.0,
    )

    prosperity = _clamp(
        _clamp(faction.food_balance / food_consumption, 0.0, 1.0) * 0.35
        + _clamp(faction.trade_income / 30.0, 0.0, 1.0) * 0.30
        + _clamp(faction.treasury / 200.0, 0.0, 1.0) * 0.20
        + faction.material_accumulation * 0.15,
        0.0,
        1.0,
    )

    equilibrium = SOCIAL_ENERGY_EQUILIBRIUM.get(
        faction.civilizational_phase,
        SOCIAL_ENERGY_EQUILIBRIUM[PHASE_PIONEERS],
    )
    delta = (
        hardship * SOCIAL_ENERGY_HARDSHIP_GAIN
        - prosperity * SOCIAL_ENERGY_PROSPERITY_LOSS
        - (faction.social_energy - equilibrium) * SOCIAL_ENERGY_MEAN_REVERSION
    )
    faction.social_energy = round(_clamp(faction.social_energy + delta, 0.05, 1.0), 3)


def _update_religious_vitality(faction: Faction) -> None:
    target = _clamp(
        faction.social_energy * 0.55
        + (1.0 - faction.material_accumulation) * 0.30
        + (1.0 - faction.religion.state_cult_strength) * 0.15,
        0.05,
        0.95,
    )

    delta = (target - faction.religious_vitality) * RELIGIOUS_VITALITY_REVERSION_RATE
    faction.religious_vitality = round(
        _clamp(faction.religious_vitality + delta, 0.05, 1.0),
        3,
    )

    if faction.religious_vitality > 0.60:
        boost = (faction.religious_vitality - 0.60) * VITALITY_REFORM_PRESSURE_RATE
        faction.religion.reform_pressure = round(
            min(1.0, faction.religion.reform_pressure + boost),
            3,
        )


def _update_intellectual_activity(faction: Faction) -> None:
    wealth_driver = _clamp(
        faction.material_accumulation * 0.60
        + _clamp(faction.trade_income / 50.0, 0.0, 1.0) * 0.40,
        0.0,
        1.0,
    )
    admin_cap = _clamp(faction.administrative_capacity / 5.0, 0.0, 1.0)

    target = _clamp(
        wealth_driver * 0.60
        + admin_cap * 0.25
        + faction.intellectual_activity * 0.15,
        0.05,
        0.90,
    )

    delta = (target - faction.intellectual_activity) * INTELLECTUAL_REVERSION_RATE
    faction.intellectual_activity = round(
        _clamp(faction.intellectual_activity + delta, 0.05, 1.0),
        3,
    )

    if faction.intellectual_activity > 0.50:
        over = faction.intellectual_activity - 0.50
        faction.ideology.reform_pressure = round(
            min(1.0, faction.ideology.reform_pressure + over * INTELLECTUAL_IDEOLOGY_PRESSURE),
            3,
        )
        faction.religion.reform_pressure = round(
            min(1.0, faction.religion.reform_pressure + over * INTELLECTUAL_RELIGION_PRESSURE),
            3,
        )


def _check_revival_surge(faction: Faction) -> None:
    if faction.civilizational_phase not in (PHASE_DECADENCE, PHASE_DECLINE):
        faction.revival_surge_turns = 0
        return

    hardship_total = (
        faction.famine_pressure
        + faction.epidemic_pressure
        + faction.shock_exposure
    )
    qualifying = (
        hardship_total > REVIVAL_HARDSHIP_THRESHOLD
        and faction.religious_vitality > 0.50
    )

    if qualifying:
        faction.revival_surge_turns += 1
        faction.religious_vitality = round(
            min(1.0, faction.religious_vitality + 0.025),
            3,
        )
    else:
        faction.revival_surge_turns = max(0, faction.revival_surge_turns - 1)


def _check_phase_transitions(faction: Faction, world: WorldState) -> None:
    if faction.civilizational_phase not in PHASE_MIN_TURNS:
        faction.civilizational_phase = PHASE_PIONEERS

    faction.civilizational_phase_turns += 1
    phase = faction.civilizational_phase
    min_turns = PHASE_MIN_TURNS[phase]

    if faction.civilizational_phase_turns < min_turns:
        return

    overage = faction.civilizational_phase_turns - min_turns
    chance = _clamp(PHASE_BASE_CHANCE[phase] + overage * 0.01, 0.0, 1.0)
    overdue = overage >= PHASE_RELAXATION_TURNS[phase]

    if phase == PHASE_PIONEERS:
        ready = (
            faction.material_accumulation > 0.30
            and faction.social_energy > 0.65
        ) or (
            overdue
            and faction.social_energy > 0.55
        )
        if ready and random.random() < chance:
            _transition_to(faction, PHASE_CONQUESTS, world)

    elif phase == PHASE_CONQUESTS:
        ready = (
            faction.material_accumulation > 0.42
            and faction.social_energy < 0.70
            and faction.trade_income > 5.0
        ) or (
            overdue
            and faction.material_accumulation > 0.30
            and faction.social_energy < 0.75
        )
        if ready and random.random() < chance:
            _transition_to(faction, PHASE_COMMERCE, world)

    elif phase == PHASE_COMMERCE:
        ready = (
            faction.material_accumulation > 0.56
            and faction.social_energy < 0.52
            and faction.intellectual_activity > 0.22
        ) or (
            overdue
            and faction.material_accumulation > 0.40
            and faction.social_energy < 0.60
            and faction.intellectual_activity > 0.15
        )
        if ready and random.random() < chance:
            _transition_to(faction, PHASE_AFFLUENCE, world)

    elif phase == PHASE_AFFLUENCE:
        ready = (
            faction.material_accumulation > 0.65
            and faction.intellectual_activity > 0.45
            and faction.social_energy < 0.40
        ) or (
            overdue
            and faction.material_accumulation > 0.55
            and faction.intellectual_activity > 0.35
            and faction.social_energy < 0.50
        )
        if ready and random.random() < chance:
            _transition_to(faction, PHASE_INTELLECT, world)

    elif phase == PHASE_INTELLECT:
        decadence_ready = (
            faction.religious_vitality < 0.32
            and faction.social_energy < 0.28
        ) or (
            overdue
            and faction.religious_vitality < 0.42
            and faction.social_energy < 0.35
        )
        if decadence_ready and random.random() < chance:
            _transition_to(faction, PHASE_DECADENCE, world)
        elif (
            faction.religious_vitality > 0.68
            and faction.intellectual_activity > 0.55
            and random.random() < chance * 0.4
        ):
            _transition_to(faction, PHASE_COMMERCE, world)

    elif phase == PHASE_DECADENCE:
        decline_ready = (
            faction.administrative_overextension > 0.32
            and faction.social_energy < 0.20
            and faction.succession.claimant_pressure > 0.55
        ) or (
            overdue
            and faction.social_energy < 0.24
            and (
                faction.administrative_overextension > 0.28
                or faction.succession.claimant_pressure > 0.45
            )
        )
        if decline_ready and random.random() < chance:
            _transition_to(faction, PHASE_DECLINE, world)
        elif (
            faction.religious_vitality > REVIVAL_VITALITY_THRESHOLD
            and faction.revival_surge_turns >= REVIVAL_SURGE_REQUIRED
            and random.random() < chance * 0.6
        ):
            _transition_to(faction, PHASE_CONQUESTS, world)

    elif phase == PHASE_DECLINE:
        if (
            faction.religious_vitality > REVIVAL_VITALITY_THRESHOLD
            and faction.revival_surge_turns >= REVIVAL_SURGE_REQUIRED
            and random.random() < chance
        ):
            _transition_to(faction, PHASE_CONQUESTS, world)


def _transition_to(faction: Faction, new_phase: str, world: WorldState) -> None:
    old_phase = faction.civilizational_phase
    world.events.append(
        Event(
            turn=world.turn,
            type="civilizational_phase_transition",
            faction=faction.name,
            details={
                "from": old_phase,
                "to": new_phase,
            },
            tags=["civilization_cycle", old_phase, new_phase],
            significance=0.65,
        )
    )

    faction.civilizational_phase = new_phase
    faction.civilizational_phase_turns = 0

    if new_phase == PHASE_CONQUESTS:
        faction.military_tradition = round(min(1.0, faction.military_tradition + 0.05), 3)

    elif new_phase == PHASE_COMMERCE:
        faction.religion.religious_tolerance = round(
            min(0.95, faction.religion.religious_tolerance + 0.08),
            3,
        )

    elif new_phase == PHASE_AFFLUENCE:
        faction.religion.state_cult_strength = round(
            min(0.95, faction.religion.state_cult_strength + 0.10),
            3,
        )

    elif new_phase == PHASE_INTELLECT:
        faction.ideology.radicalism = round(min(1.0, faction.ideology.radicalism + 0.10), 3)

    elif new_phase == PHASE_DECADENCE:
        faction.military_tradition = round(max(0.0, faction.military_tradition - 0.12), 3)
        faction.succession.claimant_pressure = round(
            min(1.0, faction.succession.claimant_pressure + 0.18),
            3,
        )
        faction.shock_resilience = round(max(0.0, faction.shock_resilience - 0.12), 3)

    elif new_phase == PHASE_DECLINE:
        faction.military_tradition = round(max(0.0, faction.military_tradition - 0.10), 3)
        faction.succession.claimant_pressure = round(
            min(1.0, faction.succession.claimant_pressure + 0.20),
            3,
        )
        faction.shock_resilience = round(max(0.0, faction.shock_resilience - 0.15), 3)
        faction.administrative_overextension = round(
            min(1.0, faction.administrative_overextension + 0.08),
            3,
        )

    if new_phase == PHASE_CONQUESTS and old_phase in (PHASE_DECADENCE, PHASE_DECLINE):
        faction.social_energy = round(min(1.0, faction.social_energy + 0.25), 3)
        faction.religious_vitality = round(min(1.0, faction.religious_vitality + 0.20), 3)
        faction.religion.religious_zeal = round(
            min(0.95, faction.religion.religious_zeal + 0.20),
            3,
        )
        faction.religion.state_cult_strength = round(
            max(0.10, faction.religion.state_cult_strength - 0.25),
            3,
        )
        faction.religion.reform_pressure = round(
            min(1.0, faction.religion.reform_pressure + 0.45),
            3,
        )
        faction.revival_surge_turns = 0


def _apply_phase_effects(faction: Faction) -> None:
    phase = faction.civilizational_phase

    if phase == PHASE_PIONEERS:
        faction.military_tradition = round(min(1.0, faction.military_tradition + 0.012), 3)
        faction.shock_resilience = round(min(1.0, faction.shock_resilience + 0.008), 3)
        if faction.religion.religious_zeal < 0.78:
            faction.religion.religious_zeal = round(faction.religion.religious_zeal + 0.007, 3)
        if faction.religion.state_cult_strength > 0.35:
            faction.religion.state_cult_strength = round(
                faction.religion.state_cult_strength - 0.006,
                3,
            )

    elif phase == PHASE_CONQUESTS:
        faction.military_tradition = round(min(1.0, faction.military_tradition + 0.008), 3)
        faction.shock_resilience = round(min(1.0, faction.shock_resilience + 0.004), 3)
        if faction.religion.state_cult_strength < 0.55:
            faction.religion.state_cult_strength = round(
                faction.religion.state_cult_strength + 0.003,
                3,
            )

    elif phase == PHASE_COMMERCE:
        faction.merchant_capacity = round(min(1.0, faction.merchant_capacity + 0.005), 3)
        if faction.religion.religious_tolerance < 0.65:
            faction.religion.religious_tolerance = round(
                faction.religion.religious_tolerance + 0.005,
                3,
            )
        if faction.religion.religious_zeal > 0.35:
            faction.religion.religious_zeal = round(faction.religion.religious_zeal - 0.005, 3)
        if faction.religion.state_cult_strength < 0.65:
            faction.religion.state_cult_strength = round(
                faction.religion.state_cult_strength + 0.003,
                3,
            )

    elif phase == PHASE_AFFLUENCE:
        faction.merchant_capacity = round(min(1.0, faction.merchant_capacity + 0.003), 3)
        faction.military_tradition = round(max(0.05, faction.military_tradition - 0.004), 3)
        if faction.religion.religious_zeal > 0.25:
            faction.religion.religious_zeal = round(faction.religion.religious_zeal - 0.006, 3)
        if faction.religion.state_cult_strength < 0.80:
            faction.religion.state_cult_strength = round(
                faction.religion.state_cult_strength + 0.004,
                3,
            )
        faction.administrative_overextension = round(
            min(1.0, faction.administrative_overextension + 0.003),
            3,
        )

    elif phase == PHASE_INTELLECT:
        faction.military_tradition = round(max(0.05, faction.military_tradition - 0.006), 3)
        faction.shock_resilience = round(max(0.0, faction.shock_resilience - 0.005), 3)
        faction.succession.claimant_pressure = round(
            min(1.0, faction.succession.claimant_pressure + 0.006),
            3,
        )

    elif phase == PHASE_DECADENCE:
        faction.shock_resilience = round(max(0.0, faction.shock_resilience - 0.008), 3)
        faction.military_tradition = round(max(0.0, faction.military_tradition - 0.007), 3)
        faction.succession.claimant_pressure = round(
            min(1.0, faction.succession.claimant_pressure + 0.010),
            3,
        )
        faction.administrative_overextension = round(
            min(1.0, faction.administrative_overextension + 0.005),
            3,
        )
        if faction.religion.state_cult_strength > 0.30:
            faction.religion.state_cult_strength = round(
                faction.religion.state_cult_strength - 0.004,
                3,
            )

    elif phase == PHASE_DECLINE:
        faction.shock_resilience = round(max(0.0, faction.shock_resilience - 0.012), 3)
        faction.military_tradition = round(max(0.0, faction.military_tradition - 0.010), 3)
        faction.succession.claimant_pressure = round(
            min(1.0, faction.succession.claimant_pressure + 0.015),
            3,
        )
        faction.administrative_overextension = round(
            min(1.0, faction.administrative_overextension + 0.008),
            3,
        )
        if faction.religious_vitality < 0.50:
            faction.religious_vitality = round(min(1.0, faction.religious_vitality + 0.004), 3)


def update_civilization_cycle(world: WorldState) -> None:
    for faction in world.factions.values():
        if faction.is_rebel and faction.rebel_age < 3:
            continue
        _update_material_accumulation(faction)
        _update_social_energy(faction)
        _update_religious_vitality(faction)
        _update_intellectual_activity(faction)
        _check_revival_surge(faction)
        _check_phase_transitions(faction, world)
        _apply_phase_effects(faction)
