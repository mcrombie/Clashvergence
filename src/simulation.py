from src.agents import choose_action
from src.actions import attack, expand, invest
from src.config import (
    EMPIRE_FREE_REGIONS,
    EMPIRE_SCALE_COST,
)
from src.diplomacy import update_relationships
from src.doctrine import update_faction_doctrines
from src.heartland import (
    get_region_surplus,
    get_region_effective_income,
    get_region_maintenance_cost,
    get_region_core_status,
    get_region_taxable_value,
    record_region_history,
    resolve_unrest_events,
    update_faction_polity_tiers,
    update_faction_resource_economy,
    update_region_settlement_levels,
    update_region_populations,
    update_rebel_faction_status,
    update_region_integration,
)
from src.metrics import record_turn_metrics
import random


def get_faction_economy_snapshot(world):
    """Returns per-faction owned regions, income, penalties, and net change."""
    snapshot = {
        faction_name: {
            "owned_regions": 0,
            "population": 0,
            "total_surplus": 0.0,
            "base_income": 0,
            "nominal_income": 0,
            "empire_penalty": 0,
            "effective_income": 0,
            "maintenance": 0,
            "net": 0,
            "homeland_regions": 0,
            "core_regions": 0,
            "frontier_regions": 0,
        }
        for faction_name in world.factions
    }

    for region in world.regions.values():
        if region.owner is not None:
            snapshot[region.owner]["owned_regions"] += 1
            snapshot[region.owner]["population"] += region.population
            snapshot[region.owner]["total_surplus"] += get_region_surplus(region, world)
            snapshot[region.owner]["nominal_income"] += get_region_taxable_value(region, world)
            snapshot[region.owner]["base_income"] += get_region_effective_income(region, world)
            snapshot[region.owner]["maintenance"] += get_region_maintenance_cost(region, world)
            core_status = get_region_core_status(region)
            if core_status == "homeland":
                snapshot[region.owner]["homeland_regions"] += 1
            elif core_status == "core":
                snapshot[region.owner]["core_regions"] += 1
            else:
                snapshot[region.owner]["frontier_regions"] += 1

    for faction_name, data in snapshot.items():
        data["total_surplus"] = round(data["total_surplus"], 2)
        data["empire_penalty"] = max(
            0,
            data["owned_regions"] - EMPIRE_FREE_REGIONS,
        ) * EMPIRE_SCALE_COST
        data["effective_income"] = data["base_income"] - data["empire_penalty"]
        data["net"] = data["effective_income"] - data["maintenance"]

    return snapshot


def apply_turn_economy(world):
    """Applies income and maintenance for each faction at end of turn."""
    economy_snapshot = get_faction_economy_snapshot(world)

    for faction_name, data in economy_snapshot.items():
        faction = world.factions[faction_name]
        faction.treasury += data["base_income"]
        faction.treasury -= data["empire_penalty"]
        faction.treasury -= data["maintenance"]

    return economy_snapshot


def run_turn(world, faction_order=None, randomize_order=True, verbose=True):
    """Runs one full turn of the simulation."""

    if verbose:
        print(f"\nTurn {world.turn + 1}")

    update_faction_resource_economy(world, advance_resources=True)

    # shuffle turn order
    if faction_order is None:
        turn_order = list(world.factions.keys())
        if randomize_order: random.shuffle(turn_order)
    else:
        # if a fixed order is passed (for experiments), still shuffle a copy
        turn_order = faction_order.copy()
        if randomize_order: random.shuffle(turn_order)

    for faction_name in turn_order:
        update_faction_resource_economy(world, advance_resources=False)
        action_name, target_region_name = choose_action(faction_name, world)

        if action_name == "expand":
            success = expand(faction_name, target_region_name, world)
            if verbose:
                if success:
                    print(f"{faction_name} expanded into {target_region_name}")
                else:
                    print(f"{faction_name} failed to expand into {target_region_name}")

        elif action_name == "attack":
            success = attack(faction_name, target_region_name, world)
            if verbose:
                if success:
                    print(f"{faction_name} attacked and captured {target_region_name}")
                else:
                    print(f"{faction_name} attacked {target_region_name} but failed")

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

    update_faction_resource_economy(world, advance_resources=False)
    resolve_unrest_events(world)
    update_faction_resource_economy(world, advance_resources=False)
    economy_snapshot = apply_turn_economy(world)
    update_region_integration(world)
    update_region_populations(world)
    update_region_settlement_levels(world)
    update_faction_resource_economy(world, advance_resources=False)
    update_rebel_faction_status(world)
    update_faction_polity_tiers(world)
    update_relationships(world)
    update_faction_doctrines(world)
    if verbose:
        for faction_name in turn_order:
            data = economy_snapshot[faction_name]
            print(
                f"{faction_name} economy: base_income={data['base_income']}, "
                f"scale_penalty={data['empire_penalty']}, "
                f"effective_income={data['effective_income']}, "
                f"maintenance={data['maintenance']}, net={data['net']}, "
                f"treasury={world.factions[faction_name].treasury}"
            )
    record_turn_metrics(world, economy_snapshot=economy_snapshot)
    record_region_history(world)
    world.turn += 1

def run_simulation(world, num_turns, faction_order=None, verbose=True):
    """Runs the simulation for the given number of turns."""

    for _ in range(num_turns):
        run_turn(world, faction_order=faction_order, verbose=verbose)

    return world
