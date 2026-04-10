from src.actions import get_expandable_regions, get_investable_regions, expand, invest
from src.config import EXPANSION_COST
import random

def score_expand_target(region_name, world):
    """Returns a numeric score representing the strategic value of expanding into a region."""

    region = world.regions[region_name]

    # Immediate value
    resource_score = region.resources * 2

    # Connectivity (how many total neighbors)
    neighbor_score = len(region.neighbors)

    # Future expansion potential (unclaimed neighbors)
    future_expansion_score = 0
    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None:
            future_expansion_score += 2

    # Total score
    total_score = resource_score + neighbor_score + future_expansion_score

    return total_score

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