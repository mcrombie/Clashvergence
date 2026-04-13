from src.agents import choose_action
from src.actions import expand, invest
from src.metrics import record_turn_metrics
import random


def update_treasuries(world):
    """Adds each owned region's resources to its faction's treasury."""

    for region in world.regions.values():
        if region.owner is not None:
            world.factions[region.owner].treasury += region.resources


def run_turn(world, faction_order=None, randomize_order=True, verbose=True):
    """Runs one full turn of the simulation."""

    if verbose:
        print(f"\nTurn {world.turn + 1}")

    # shuffle turn order
    if faction_order is None:
        turn_order = list(world.factions.keys())
        if randomize_order: random.shuffle(turn_order)
    else:
        # if a fixed order is passed (for experiments), still shuffle a copy
        turn_order = faction_order.copy()
        if randomize_order: random.shuffle(turn_order)

    for faction_name in turn_order:
        action_name, target_region_name = choose_action(faction_name, world)

        if action_name == "expand":
            success = expand(faction_name, target_region_name, world)
            if verbose:
                if success:
                    print(f"{faction_name} expanded into {target_region_name}")
                else:
                    print(f"{faction_name} failed to expand into {target_region_name}")

        elif action_name == "invest":
            success = invest(faction_name, target_region_name, world)
            if verbose:
                if success:
                    print(f"{faction_name} invested in {target_region_name}")
                else:
                    print(f"{faction_name} failed to invest in {target_region_name}")

        else:
            if verbose:
                print(f"{faction_name} skipped its turn")

    update_treasuries(world)
    record_turn_metrics(world)
    world.turn += 1

def run_simulation(world, num_turns, faction_order=None, verbose=True):
    """Runs the simulation for the given number of turns."""

    for _ in range(num_turns):
        run_turn(world, faction_order=faction_order, verbose=verbose)

    return world
