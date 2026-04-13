from src.config import EXPANSION_COST, MAX_RESOURCES, INVEST_AMOUNT


def get_expandable_regions(faction_name, world):
    """Returns a list of Regions the given faction is capable of expanding into."""

    expandable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner == faction_name:
            for neighbor_name in region.neighbors:
                neighbor = world.regions[neighbor_name]
                if neighbor.owner is None:
                    expandable_regions.add(neighbor_name)

    return list(expandable_regions)


def get_expand_target_score_components(region_name, world):
    """Returns the scoring breakdown for an expansion target."""

    region = world.regions[region_name]
    unclaimed_neighbors = 0

    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None:
            unclaimed_neighbors += 1

    score = (region.resources * 2) + len(region.neighbors) + (unclaimed_neighbors * 2)

    return {
        "resources": region.resources,
        "neighbors": len(region.neighbors),
        "unclaimed_neighbors": unclaimed_neighbors,
        "score": score,
    }


def expand(faction_name, target_region_name, world):
    """Returns whether the Faction successfully expanded into the target Region."""

    if target_region_name not in world.regions:
        return False

    faction = world.factions[faction_name]

    if faction.treasury < EXPANSION_COST:
        return False

    if target_region_name not in get_expandable_regions(faction_name, world):
        return False

    score_components = get_expand_target_score_components(target_region_name, world)
    faction.treasury -= EXPANSION_COST
    world.regions[target_region_name].owner = faction_name

    world.events.append({
        "turn": world.turn,
        "type": "expand",
        "faction": faction_name,
        "region": target_region_name,
        "cost": EXPANSION_COST,
        "treasury_after": faction.treasury,
        **score_components,
    })

    return True


def get_investable_regions(faction_name, world):
    """Returns a list of Regions the Faction owns and is capable of investing in."""

    investable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner == faction_name and region.resources < MAX_RESOURCES:
            investable_regions.add(region.name)

    return list(investable_regions)


def invest(faction_name, target_region_name, world):
    """Returns whether the Faction successfully invested in the target Region."""

    if target_region_name not in world.regions:
        return False

    if target_region_name not in get_investable_regions(faction_name, world):
        return False

    region = world.regions[target_region_name]

    if region.resources >= MAX_RESOURCES:
        return False

    region.resources += INVEST_AMOUNT

    if region.resources > MAX_RESOURCES:
        region.resources = MAX_RESOURCES

    world.events.append({
        "turn": world.turn,
        "type": "invest",
        "faction": faction_name,
        "region": target_region_name,
        "invest_amount": INVEST_AMOUNT,
        "new_resources": region.resources,
    })

    return True
