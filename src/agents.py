from src.actions import (
    get_attack_target_score_components,
    get_attackable_regions,
    expand,
    get_expand_target_score_components,
    get_expandable_regions,
    get_investable_regions,
    invest,
)
from src.config import ATTACK_COST, EXPANSION_COST, MAX_RESOURCES


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _normalize_expand_score(score):
    return _clamp((score - 5) / 8, 0.0, 1.0)


def _normalize_attack_score(score):
    return _clamp((score - 45) / 30, 0.0, 1.0)

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

def choose_invest_target(faction_name, world):
    investable_regions = get_investable_regions(faction_name, world)

    if not investable_regions:
        return None

    # choose lowest-resource region (simple heuristic)
    best_region = min(
        investable_regions,
        key=lambda name: (
            world.regions[name].resources,
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

    attackable_regions = get_attackable_regions(faction_name, world)
    expandable_regions = get_expandable_regions(faction_name, world)
    investable_regions = get_investable_regions(faction_name, world)

    can_attack = bool(attackable_regions) and faction.treasury > 0
    can_expand = bool(expandable_regions) and faction.treasury >= EXPANSION_COST
    can_invest = bool(investable_regions)

    best_attack_target = None
    best_attack_score = 0
    best_expand_target = None
    best_expand_score = 0
    best_invest_target = None
    action_utilities = {}

    if can_attack:
        best_attack_target = choose_attack_target(faction_name, world)
        best_attack_score = score_attack_target(best_attack_target, faction_name, world)

    if can_expand:
        best_expand_target = choose_expand_target(faction_name, world)
        best_expand_score = score_expand_target_for_faction(
            best_expand_target,
            faction_name,
            world,
        )

    if can_invest:
        best_invest_target = choose_invest_target(faction_name, world)

    if can_attack:
        attack_utility = (
            _normalize_attack_score(best_attack_score)
            * (0.72 + (doctrine.war_posture * 0.42))
            + (doctrine.expansion_posture * 0.08)
            - (doctrine.insularity * 0.10)
        )
        if faction.treasury <= ATTACK_COST:
            attack_utility -= 0.04
        action_utilities["attack"] = attack_utility

    if can_expand:
        expand_utility = (
            _normalize_expand_score(best_expand_score)
            * (0.72 + (doctrine.expansion_posture * 0.42))
            + ((1.0 - doctrine.insularity) * 0.08)
        )
        if faction.treasury >= EXPANSION_COST * 2:
            expand_utility += 0.05
        action_utilities["expand"] = expand_utility

    if can_invest and best_invest_target is not None:
        invest_need = 1.0 - (
            world.regions[best_invest_target].resources / max(1, MAX_RESOURCES)
        )
        invest_utility = (
            invest_need * (0.68 + (doctrine.development_posture * 0.44))
            + (doctrine.insularity * 0.14)
            - (doctrine.expansion_posture * 0.06)
        )
        if faction.treasury < EXPANSION_COST:
            invest_utility += 0.03
        action_utilities["invest"] = invest_utility

    if action_utilities:
        best_action = max(
            action_utilities,
            key=lambda action_name: (action_utilities[action_name], action_name),
        )
        if best_action == "attack":
            return ("attack", best_attack_target)
        if best_action == "expand":
            return ("expand", best_expand_target)
        if best_action == "invest":
            return ("invest", best_invest_target)

    if can_expand:
        return ("expand", best_expand_target)
    if can_invest:
        return ("invest", best_invest_target)
    if can_attack:
        return ("attack", best_attack_target)

    return (None, None)
