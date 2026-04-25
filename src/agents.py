from src.actions import (
    get_attack_target_score_components,
    get_attackable_regions,
    get_developable_regions,
    get_development_target_score_components,
    expand,
    get_expand_target_score_components,
    get_expandable_regions,
)
from src.calendar import get_seasonal_action_modifier, get_turn_season_name
from src.config import (
    ATTACK_COST,
    EXPANSION_COST,
    REBEL_PROTO_ATTACK_UTILITY_PENALTY,
    REBEL_PROTO_INVEST_UTILITY_BONUS,
)
from src.doctrine import OPEN_TERRAIN_TAGS, ROUGH_TERRAIN_TAGS
from src.resources import CAPACITY_FOOD_SECURITY, CAPACITY_METAL, CAPACITY_MOBILITY


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _normalize_expand_score(score):
    return _clamp((score - 5) / 8, 0.0, 1.0)


def _normalize_attack_score(score):
    return _clamp((score - 45) / 30, 0.0, 1.0)


def _normalize_develop_score(score):
    return _clamp(score / 12, 0.0, 1.0)


def _get_owned_region_count(faction_name, world):
    return sum(1 for region in world.regions.values() if region.owner == faction_name)


def _get_expansion_personality(faction):
    doctrine = faction.doctrine_profile
    homeland_tags = set(faction.doctrine_state.homeland_terrain_tags or [])
    open_homeland = sum(1 for tag in homeland_tags if tag in OPEN_TERRAIN_TAGS)
    rough_homeland = sum(1 for tag in homeland_tags if tag in ROUGH_TERRAIN_TAGS)
    terrain_count = max(1, open_homeland + rough_homeland)
    open_ratio = open_homeland / terrain_count
    rough_ratio = rough_homeland / terrain_count

    climate = faction.doctrine_state.homeland_climate or "temperate"
    climate_modifier = {
        "steppe": 0.12,
        "oceanic": 0.06,
        "temperate": 0.03,
        "tropical": -0.02,
        "arid": -0.06,
        "cold": -0.1,
    }.get(climate, 0.0)
    terrain_personality = 0.72 + (open_ratio * 0.42) - (rough_ratio * 0.32) + climate_modifier
    doctrine_personality = (
        0.72
        + (doctrine.expansion_posture * 0.5)
        - (doctrine.insularity * 0.36)
        + (doctrine.war_posture * 0.12)
        - (doctrine.development_posture * 0.08)
    )
    return _clamp(terrain_personality * doctrine_personality, 0.28, 1.45)


def _get_frontier_pressure(
    faction_name,
    world,
    *,
    expandable_regions,
    best_expand_score,
):
    if not expandable_regions:
        return 0.0

    faction = world.factions[faction_name]
    owned_region_count = _get_owned_region_count(faction_name, world)
    pressure = 0.0

    if owned_region_count <= 1:
        pressure += 0.18
    elif owned_region_count <= 2:
        pressure += 0.1

    pressure += min(0.12, len(expandable_regions) * 0.018)
    pressure += min(0.14, max(0.0, best_expand_score - 11.0) * 0.014)

    if faction.treasury >= EXPANSION_COST:
        pressure += 0.06
    if faction.treasury >= EXPANSION_COST * 2:
        pressure += 0.05

    if faction.doctrine_state.expansions <= 0 and owned_region_count <= 2:
        pressure += 0.06

    pressure *= _get_expansion_personality(faction)

    return _clamp(pressure, 0.0, 0.52)


def _get_acute_development_need(faction):
    shortages = faction.resource_shortages
    return (
        shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 0.45
        + shortages.get(CAPACITY_MOBILITY, 0.0) * 0.3
        + shortages.get(CAPACITY_METAL, 0.0) * 0.3
        + faction.food_deficit * 0.35
        + faction.trade_import_dependency * 0.45
        + faction.trade_corridor_exposure * 0.4
    )

def score_expand_target(region_name, world):
    """Returns a numeric score representing the strategic value of expanding into a region."""
    return get_expand_target_score_components(region_name, world)["score"]


def score_expand_target_for_faction(region_name, faction_name, world):
    return get_expand_target_score_components(
        region_name,
        world,
        faction_name=faction_name,
    )["score"]

def choose_expand_target(faction_name, world):
    expandable_regions = get_expandable_regions(faction_name, world)

    if not expandable_regions:
        return None

    best_region = max(
        expandable_regions,
        key=lambda region_name: (
            score_expand_target_for_faction(region_name, faction_name, world),
            region_name,
        )
    )

    return best_region

def choose_develop_target(faction_name, world):
    developable_regions = get_developable_regions(faction_name, world)

    if not developable_regions:
        return None

    best_region = max(
        developable_regions,
        key=lambda name: (
            get_development_target_score_components(name, faction_name, world)["score"],
            name,
        )
    )

    return best_region


def score_attack_target(region_name, faction_name, world):
    """Returns a numeric score representing the value of an attack target."""
    return get_attack_target_score_components(region_name, faction_name, world)["score"]


def choose_attack_target(faction_name, world):
    attackable_regions = get_attackable_regions(faction_name, world)

    if not attackable_regions:
        return None

    return max(
        attackable_regions,
        key=lambda region_name: (
            score_attack_target(region_name, faction_name, world),
            region_name,
        )
    )


def choose_action(faction_name, world):
    faction = world.factions[faction_name]
    doctrine = faction.doctrine_profile
    is_proto_state = faction.is_rebel and faction.proto_state
    season_name = get_turn_season_name(world.turn)

    attackable_regions = get_attackable_regions(faction_name, world)
    expandable_regions = get_expandable_regions(faction_name, world)
    developable_regions = get_developable_regions(faction_name, world)

    can_attack = bool(attackable_regions) and faction.treasury >= ATTACK_COST
    can_expand = bool(expandable_regions) and faction.treasury >= EXPANSION_COST
    can_develop = bool(developable_regions)

    best_attack_target = None
    best_attack_score = 0
    best_expand_target = None
    best_expand_score = 0
    best_develop_target = None
    action_utilities = {}

    if can_attack:
        best_attack_target = choose_attack_target(faction_name, world)
        best_attack_score = score_attack_target(best_attack_target, faction_name, world)
        best_attack_components = get_attack_target_score_components(
            best_attack_target,
            faction_name,
            world,
        )
    else:
        best_attack_components = None

    if can_expand:
        best_expand_target = choose_expand_target(faction_name, world)
        best_expand_score = score_expand_target_for_faction(
            best_expand_target,
            faction_name,
            world,
        )

    frontier_pressure = _get_frontier_pressure(
        faction_name,
        world,
        expandable_regions=expandable_regions,
        best_expand_score=best_expand_score,
    )

    if can_develop:
        best_develop_target = choose_develop_target(faction_name, world)
        best_develop_components = get_development_target_score_components(
            best_develop_target,
            faction_name,
            world,
        ) if best_develop_target is not None else None
    else:
        best_develop_components = None

    if can_attack:
        attack_utility = (
            _normalize_attack_score(best_attack_score)
            * (0.72 + (doctrine.war_posture * 0.42))
            + (doctrine.expansion_posture * 0.08)
            - (doctrine.insularity * 0.10)
        )
        if faction.treasury <= ATTACK_COST:
            attack_utility -= 0.04
        if is_proto_state:
            attack_utility -= REBEL_PROTO_ATTACK_UTILITY_PENALTY
        if best_attack_components is not None:
            if best_attack_components["diplomacy_status"] == "non_aggression_pact":
                attack_utility -= 0.45
            elif best_attack_components["diplomacy_status"] == "overlord":
                attack_utility -= 0.48
            elif best_attack_components["diplomacy_status"] == "tributary":
                attack_utility -= 0.36
            elif best_attack_components["diplomacy_status"] == "rival":
                attack_utility += 0.08
        attack_utility += get_seasonal_action_modifier("attack", season_name)
        action_utilities["attack"] = attack_utility

    if can_expand:
        expansion_personality = _get_expansion_personality(faction)
        expand_utility = (
            _normalize_expand_score(best_expand_score)
            * (0.72 + (doctrine.expansion_posture * 0.42))
            * expansion_personality
            + ((1.0 - doctrine.insularity) * 0.08)
            + frontier_pressure
        )
        if faction.treasury >= EXPANSION_COST * 2:
            expand_utility += 0.05
        expand_utility += get_seasonal_action_modifier("expand", season_name)
        action_utilities["expand"] = expand_utility

    if can_develop and best_develop_target is not None:
        acute_development_need = _get_acute_development_need(faction)
        develop_need = acute_development_need
        if best_develop_components is not None:
            develop_need += _normalize_develop_score(best_develop_components["score"])
        develop_utility = (
            develop_need * (0.4 + (doctrine.development_posture * 0.32))
            + (doctrine.insularity * 0.14)
            - (doctrine.expansion_posture * 0.06)
        )
        if faction.treasury < EXPANSION_COST:
            develop_utility += 0.03
        elif can_expand and acute_development_need < 0.45:
            develop_utility -= frontier_pressure * 0.4
        if is_proto_state:
            develop_utility += REBEL_PROTO_INVEST_UTILITY_BONUS
        develop_utility += get_seasonal_action_modifier("develop", season_name)
        action_utilities["develop"] = develop_utility

    if action_utilities:
        best_action = max(
            action_utilities,
            key=lambda action_name: (action_utilities[action_name], action_name),
        )
        if best_action == "attack":
            return ("attack", best_attack_target)
        if best_action == "expand":
            return ("expand", best_expand_target)
        if best_action == "develop":
            return ("develop", best_develop_target)

    if can_expand:
        return ("expand", best_expand_target)
    if can_develop:
        return ("develop", best_develop_target)
    if can_attack:
        return ("attack", best_attack_target)

    return (None, None)


def choose_invest_target(faction_name, world):
    """Backward-compatible alias for development target selection."""
    return choose_develop_target(faction_name, world)
