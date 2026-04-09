from src.agents import choose_action
from src.actions import expand, invest


def update_treasuries(world):
    """Adds each owned Regions's resources to its Faction's treasury."""

    for region in world.regions.values():
        if region.owner is not None:
            world.factions[region.owner].treasury += region.resources


def run_turn(world):
    """Runs one full turn of the simulation."""

    print(f"\nTurn {world.turn + 1}")

    for faction_name in world.factions:
        action_name, target_region_name = choose_action(faction_name, world)

        if action_name == "expand":
            success = expand(faction_name, target_region_name, world)
            if success:
                print(f"{faction_name} expanded into {target_region_name}")
            else:
                print(f"{faction_name} failed to expand into {target_region_name}")

        elif action_name == "invest":
            success = invest(faction_name, target_region_name, world)
            if success:
                print(f"{faction_name} invested in {target_region_name}")
            else:
                print(f"{faction_name} failed to invest in {target_region_name}")

        else:
            print(f"{faction_name} skipped its turn")

    update_treasuries(world)
    world.turn += 1


def run_simulation(world, num_turns):
    """Runs the simulation for the given number of turns."""

    for _ in range(num_turns):
        run_turn(world)

    return world