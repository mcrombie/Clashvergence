

def get_expandable_regions(faction_name, world):

    '''Returns a list of Regions the given faction is capable of expanding into'''

    expandable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner == faction_name:
            for neighbor_name in region.neighbors:
                neighbor = world.regions[neighbor_name]
                if neighbor.owner is None:
                    expandable_regions.add(neighbor_name)

    return list(expandable_regions)

def expand(faction_name, target_region_name, world):
    '''Returns whether the Faction successfully expanded into the target Region'''

    if target_region_name not in world.regions:
        return False

    if target_region_name in get_expandable_regions(faction_name, world):
        world.regions[target_region_name].owner = faction_name
        return True

    return False

def get_investable_regions(faction_name, world, max_resources=5):
    '''Returns a list of Regions the Faction owns and is capable of investing in'''

    investable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner == faction_name and region.resources < max_resources:
            investable_regions.add(region.name)

    return list(investable_regions)

def invest(faction_name, target_region_name, world, max_resources=5):
    '''Returns whether the Faction successfully invested in the target Region'''

    if target_region_name not in world.regions:
        return False

    if target_region_name not in get_investable_regions(faction_name, world):
        return False

    region = world.regions[target_region_name]

    if region.resources >= max_resources:
        return False

    region.resources += 2
    return True