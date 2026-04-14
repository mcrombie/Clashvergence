from src.agents import choose_action
from src.actions import expand, invest
from src.config import REGION_MAINTENANCE_COST
from src.metrics import record_turn_metrics
from src.models import Event
import random


def get_faction_economy_snapshot(world):
    """Returns per-faction owned regions, income, maintenance, and net change."""
    snapshot = {
        faction_name: {
            "owned_regions": 0,
            "income": 0,
            "maintenance": 0,
            "net": 0,
        }
        for faction_name in world.factions
    }

    for region in world.regions.values():
        if region.owner is not None:
            snapshot[region.owner]["owned_regions"] += 1
            snapshot[region.owner]["income"] += region.resources

    for faction_name, data in snapshot.items():
        data["maintenance"] = data["owned_regions"] * REGION_MAINTENANCE_COST
        data["net"] = data["income"] - data["maintenance"]

    return snapshot


def apply_turn_economy(world):
    """Applies income and maintenance for each faction at end of turn."""
    economy_snapshot = get_faction_economy_snapshot(world)

    for faction_name, data in economy_snapshot.items():
        faction = world.factions[faction_name]
        treasury_before = faction.treasury

        faction.treasury += data["income"]
        world.events.append(Event(
            turn=world.turn,
            type="income",
            faction=faction_name,
            details={
                "income": data["income"],
                "owned_regions": data["owned_regions"],
            },
            context={
                "treasury_before": treasury_before,
            },
            impact={
                "treasury_after": faction.treasury,
                "treasury_change": data["income"],
            },
            tags=["economy", "income"],
            significance=float(data["income"]),
        ))

        treasury_before_maintenance = faction.treasury
        faction.treasury -= data["maintenance"]
        world.events.append(Event(
            turn=world.turn,
            type="maintenance",
            faction=faction_name,
            details={
                "maintenance_cost": REGION_MAINTENANCE_COST,
                "owned_regions": data["owned_regions"],
                "maintenance": data["maintenance"],
            },
            context={
                "treasury_before": treasury_before_maintenance,
            },
            impact={
                "treasury_after": faction.treasury,
                "treasury_change": -data["maintenance"],
                "net_income": data["net"],
            },
            tags=["economy", "maintenance"],
            significance=float(data["maintenance"]),
        ))

    return economy_snapshot


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

    economy_snapshot = apply_turn_economy(world)
    if verbose:
        for faction_name in turn_order:
            data = economy_snapshot[faction_name]
            print(
                f"{faction_name} economy: income={data['income']}, "
                f"maintenance={data['maintenance']}, net={data['net']}, "
                f"treasury={world.factions[faction_name].treasury}"
            )
    record_turn_metrics(world)
    world.turn += 1

def run_simulation(world, num_turns, faction_order=None, verbose=True):
    """Runs the simulation for the given number of turns."""

    for _ in range(num_turns):
        run_turn(world, faction_order=faction_order, verbose=verbose)

    return world
