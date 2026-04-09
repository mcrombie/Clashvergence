from src.actions import get_expandable_regions, get_investable_regions, expand, invest
import random

def choose_expand_target(faction_name, world):
    expandable_regions = get_expandable_regions(faction_name, world)

    if not expandable_regions:
        return None

    # prioritize center if available
    if "M" in expandable_regions:
        return "M"

    # otherwise choose highest-resource region
    best_region = max(
        expandable_regions,
        key=lambda name: world.regions[name].resources
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

    can_expand = bool(expandable_regions)
    can_invest = bool(investable_regions)

    if faction.strategy == "expansionist":
        if can_expand:
            return ("expand", choose_expand_target(faction_name, world))
        elif can_invest:
            return ("invest", choose_invest_target(faction_name, world))

    elif faction.strategy == "economic":
        if can_invest:
            return ("invest", choose_invest_target(faction_name, world))
        elif can_expand:
            return ("expand", choose_expand_target(faction_name, world))

    elif faction.strategy == "balanced":
        if can_expand and can_invest:
            if random.random() < 0.5:
                return ("expand", choose_expand_target(faction_name, world))
            else:
                return ("invest", choose_invest_target(faction_name, world))
        elif can_expand:
            return ("expand", choose_expand_target(faction_name, world))
        elif can_invest:
            return ("invest", choose_invest_target(faction_name, world))

    return (None, None)