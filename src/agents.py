from src.actions import (
    expand,
    get_expand_target_score_components,
    get_expandable_regions,
    get_investable_regions,
    invest,
)
from src.config import EXPANSION_COST
import random

def score_expand_target(region_name, world):
    """Returns a numeric score representing the strategic value of expanding into a region."""
    return get_expand_target_score_components(region_name, world)["score"]

def choose_expand_target(faction_name, world):
    expandable_regions = get_expandable_regions(faction_name, world)

    if not expandable_regions:
        return None

    best_region = max(
        expandable_regions,
        key=lambda region_name: score_expand_target(region_name, world)
    )

    return best_region

def choose_invest_target(faction_name, world):
    investable_regions = get_investable_regions(faction_name, world)

    if not investable_regions:
        return None

    # choose lowest-resource region (simple heuristic)
    best_region = min(
        investable_regions,
        key=lambda name: world.regions[name].resources
    )

    return best_region


def choose_action(faction_name, world):
    faction = world.factions[faction_name]

    expandable_regions = get_expandable_regions(faction_name, world)
    investable_regions = get_investable_regions(faction_name, world)

    can_expand = bool(expandable_regions) and faction.treasury >= EXPANSION_COST
    can_invest = bool(investable_regions)

    best_expand_target = None
    best_expand_score = 0

    if can_expand:
        best_expand_target = choose_expand_target(faction_name, world)
        best_expand_score = score_expand_target(best_expand_target, world)

    if faction.strategy == "expansionist":
        expansion_score_threshold = 6

        if can_expand and best_expand_score >= expansion_score_threshold:
            return ("expand", best_expand_target)

        if can_invest:
            return ("invest", choose_invest_target(faction_name, world))

        if can_expand:
            return ("expand", best_expand_target)

    elif faction.strategy == "balanced":
        expansion_score_threshold = 8
        treasury_threshold = EXPANSION_COST * 1.5

        if can_expand:
            if (
                best_expand_score >= expansion_score_threshold
                or faction.treasury >= treasury_threshold
            ):
                return ("expand", best_expand_target)

        if can_invest:
            return ("invest", choose_invest_target(faction_name, world))

        if can_expand:
            return ("expand", best_expand_target)

    elif faction.strategy == "opportunist":
        expansion_score_threshold = 8
        treasury_threshold = EXPANSION_COST * 1.5

        if can_expand:
            if (
                best_expand_score >= expansion_score_threshold
                or faction.treasury >= treasury_threshold
            ):
                return ("expand", best_expand_target)

        # SAFETY: don't get stuck forever
        if can_expand and world.turn > 3:
            return ("expand", best_expand_target)

        if can_invest:
            return ("invest", choose_invest_target(faction_name, world))

        if can_expand:
            return ("expand", best_expand_target)

    elif faction.strategy == "economic":
        economic_treasury_threshold = EXPANSION_COST * 2
        economic_expand_score_threshold = 10

        if can_expand:
            if (
                best_expand_score >= economic_expand_score_threshold
                or faction.treasury >= economic_treasury_threshold
            ):
                return ("expand", best_expand_target)

        if can_invest:
            return ("invest", choose_invest_target(faction_name, world))

        if can_expand:
            return ("expand", best_expand_target)

    return (None, None)
