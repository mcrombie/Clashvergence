import random

from src.administration import refresh_administrative_state
from src.agents import choose_action, choose_actions, choose_standing_orders, evaluate_action_diagnostics
from src.actions import (
    attack,
    complete_develop_project,
    complete_expansion_project,
    complete_siege_project,
    develop,
    expand,
    explore,
)
from src.diplomacy import (
    demand_tribute,
    propose_alliance,
    resolve_diplomacy_project,
    send_envoy,
)
from src.calendar import (
    SEASONAL_TIME_STEP_YEARS,
    format_turn_label,
    is_year_end,
)
from src.civilization_cycle import update_civilization_cycle
from src.config import (
    EMPIRE_FREE_REGIONS,
    EMPIRE_SCALE_COST,
    EMPIRE_QUADRATIC_THRESHOLD,
    EMPIRE_QUADRATIC_COST,
)
from src.diplomacy import apply_tributary_flows, update_relationships
from src.doctrine import update_faction_doctrines
from src.ethnicity import apply_language_contact_borrowing
from src.faction_arrivals import apply_due_faction_arrivals, get_active_faction_names
from src.integration import record_region_history, update_region_integration
from src.internal_politics import update_elite_blocs
from src.ideology import update_ideologies
from src.migration import resolve_population_migration
from src.military import refresh_military_state
from src.population import (
    get_region_surplus,
    update_faction_polity_tiers,
    update_region_populations,
    update_region_settlement_levels,
)
from src.rebellion import update_rebel_faction_status
from src.religion import update_religious_legitimacy
from src.region_state import get_region_core_status
from src.resource_economy import (
    advance_trade_warfare_state,
    advance_long_run_economic_dynamics,
    apply_turn_food_economy,
    get_region_effective_income,
    get_region_maintenance_cost,
    get_region_taxable_value,
    update_faction_resource_economy,
)
from src.shocks import (
    apply_shock_population_losses,
    refresh_long_cycle_shocks,
    resolve_food_and_disease_shocks,
    resolve_trade_network_shocks,
    update_shock_rollups,
)
from src.social_forms import is_band_faction, update_nomadic_social_forms
from src.subfactions import run_subfaction_phase
from src.visibility import refresh_all_faction_visibility, refresh_faction_visibility
from src.metrics import record_turn_metrics
from src.player_actions import ActionOption, apply_action_option
from src.succession import resolve_dynastic_succession
from src.technology import update_technology_diffusion
from src.urban import update_urban_specializations
from src.unrest import resolve_unrest_events


def get_faction_economy_snapshot(world):
    """Returns per-faction owned regions, income, penalties, and net change."""
    refresh_administrative_state(world)
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
        data["maintenance"] += float(world.factions[faction_name].military_upkeep or 0.0)
        data["total_surplus"] = round(data["total_surplus"], 2)
        excess = max(0, data["owned_regions"] - EMPIRE_FREE_REGIONS)
        linear_penalty = min(excess, EMPIRE_QUADRATIC_THRESHOLD) * EMPIRE_SCALE_COST
        quadratic_excess = max(0, excess - EMPIRE_QUADRATIC_THRESHOLD)
        quadratic_penalty = quadratic_excess * (quadratic_excess + 1) / 2 * EMPIRE_QUADRATIC_COST
        data["empire_penalty"] = linear_penalty + quadratic_penalty
        data["empire_penalty"] += float(
            world.factions[faction_name].administrative_overextension_penalty or 0.0
        )
        data["effective_income"] = data["base_income"] - data["empire_penalty"]
        data["net"] = data["effective_income"] - data["maintenance"]

    return snapshot


def apply_turn_economy(world, *, share: float = 1.0):
    """Applies income and maintenance for each faction at end of turn."""
    economy_snapshot = get_faction_economy_snapshot(world)

    for faction_name, data in economy_snapshot.items():
        faction = world.factions[faction_name]
        base_income = round(float(data["base_income"]) * share, 3)
        empire_penalty = round(float(data["empire_penalty"]) * share, 3)
        effective_income = round(float(data["effective_income"]) * share, 3)
        maintenance = round(float(data["maintenance"]) * share, 3)
        net_income = round(effective_income - maintenance, 3)
        nominal_income = round(float(data["nominal_income"]) * share, 3)

        faction.treasury += base_income
        faction.treasury -= empire_penalty
        faction.treasury -= maintenance
        data["base_income"] = base_income
        data["nominal_income"] = nominal_income
        data["empire_penalty"] = empire_penalty
        data["effective_income"] = effective_income
        data["maintenance"] = maintenance
        data["net"] = net_income

    return economy_snapshot


def _build_turn_order(world, faction_order=None, randomize_order=True):
    if faction_order is None:
        turn_order = get_active_faction_names(world)
    else:
        active_factions = set(get_active_faction_names(world))
        turn_order = [
            faction_name
            for faction_name in faction_order.copy()
            if faction_name in active_factions
        ]
    if randomize_order:
        random.shuffle(turn_order)
    return turn_order


def _run_turn_start_phase(world):
    apply_due_faction_arrivals(world)
    advance_trade_warfare_state(world)
    refresh_long_cycle_shocks(world)
    update_faction_resource_economy(world, advance_resources=True)
    update_shock_rollups(world)
    refresh_administrative_state(world)
    refresh_military_state(world)
    refresh_all_faction_visibility(world)


def _resolve_faction_action(world, faction_name, *, verbose=True, selected_action=None):
    if isinstance(selected_action, ActionOption):
        success = apply_action_option(world, faction_name, selected_action)
        if verbose:
            print(
                f"{faction_name} chose {selected_action.label}"
                if success
                else f"{faction_name} chose {selected_action.label} with no direct change"
            )
        return

    if selected_action is None:
        action_name, target_region_name = choose_action(faction_name, world)
    else:
        action_name, target_region_name = selected_action

    _execute_single_action(
        world,
        faction_name,
        action_name,
        target_region_name,
        verbose=verbose,
    )


def _execute_single_action(world, faction_name, action_name, target_region_name, *, verbose=True):
    if action_name == "expand":
        success = expand(faction_name, target_region_name, world)
        if verbose:
            if success:
                if is_band_faction(world.factions.get(faction_name)):
                    print(f"{faction_name} migrated into {target_region_name}")
                else:
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

    elif action_name == "explore":
        success = explore(faction_name, target_region_name, world)
        if verbose:
            if success:
                print(f"{faction_name} explored from {target_region_name}")
            else:
                print(f"{faction_name} failed to explore from {target_region_name}")

    elif action_name in {"develop", "invest"}:
        success = develop(faction_name, target_region_name, world)
        if verbose:
            if success:
                print(f"{faction_name} developed {target_region_name}")
            else:
                print(f"{faction_name} failed to develop {target_region_name}")

    elif action_name == "propose_alliance":
        success = propose_alliance(faction_name, target_region_name, world)
        if verbose:
            status = "started" if success else "blocked"
            print(f"{faction_name} proposed alliance to {target_region_name}: {status}")

    elif action_name == "send_envoy":
        success = send_envoy(faction_name, target_region_name, world)
        if verbose:
            status = "started" if success else "blocked"
            print(f"{faction_name} sent envoy to {target_region_name}: {status}")

    elif action_name == "demand_tribute":
        success = demand_tribute(faction_name, target_region_name, world)
        if verbose:
            status = "accepted" if success else "refused"
            print(f"{faction_name} demanded tribute from {target_region_name}: {status}")

    else:
        if verbose:
            print(f"{faction_name} skipped its turn")


def _run_advance_projects_phase(world):
    """Advance all in-progress faction projects by one turn and complete finished ones."""
    for faction_name, faction in world.factions.items():
        if not faction.active_projects:
            continue
        for track in list(faction.active_projects):
            project = faction.active_projects[track]
            project.turns_remaining -= 1

            if track == "admin" and project.action_type == "develop":
                if project.target_region in world.regions:
                    world.regions[project.target_region].last_resource_project_turn = world.turn

            elif track == "military" and project.action_type == "attack":
                if project.target_region in world.regions:
                    world.regions[project.target_region].siege_turns_remaining = max(
                        0, project.turns_remaining
                    )

            elif track == "military" and project.action_type == "expand":
                pass  # settling_faction already set; just count down

            if project.turns_remaining <= 0:
                if track == "admin" and project.action_type == "develop":
                    complete_develop_project(faction_name, project, world)
                elif track == "military" and project.action_type == "attack":
                    complete_siege_project(faction_name, project, world)
                elif track == "military" and project.action_type == "expand":
                    complete_expansion_project(faction_name, project, world)
                elif track == "diplomacy":
                    resolve_diplomacy_project(faction_name, project, world)
                del faction.active_projects[track]


def _run_faction_action_phase(
    world,
    turn_order,
    *,
    verbose=True,
    action_provider=None,
    action_diagnostics_callback=None,
):
    for faction_name in turn_order:
        update_faction_resource_economy(world, advance_resources=False)
        refresh_administrative_state(world)
        refresh_military_state(world)
        refresh_faction_visibility(world, faction_name)
        faction = world.factions[faction_name]
        faction.military_track_used = False
        faction.admin_track_used = False
        if action_provider is not None:
            selected_action = action_provider(faction_name, world)
            _resolve_faction_action(
                world,
                faction_name,
                verbose=verbose,
                selected_action=selected_action,
            )
        else:
            if action_diagnostics_callback is not None:
                diagnostics = evaluate_action_diagnostics(faction_name, world)
                action_diagnostics_callback(diagnostics)
                actions = [
                    (selected["action"], selected["target"])
                    for selected in diagnostics["selected_actions"]
                ]
            else:
                actions = choose_actions(faction_name, world)
            if not actions and verbose:
                print(f"{faction_name} skipped its turn")
            for action_name, target_region_name in actions:
                _execute_single_action(
                    world,
                    faction_name,
                    action_name,
                    target_region_name,
                    verbose=verbose,
                )
                if action_name in {"expand", "attack", "explore"}:
                    faction.military_track_used = True
                elif action_name in {"develop", "invest"}:
                    faction.admin_track_used = True
        refresh_faction_visibility(world, faction_name)
        refresh_administrative_state(world)
        refresh_military_state(world)


def _run_post_action_phase(world):
    update_faction_resource_economy(world, advance_resources=False)
    refresh_administrative_state(world)
    refresh_military_state(world)
    resolve_unrest_events(world)
    update_faction_resource_economy(world, advance_resources=False)
    refresh_administrative_state(world)
    economy_snapshot = apply_turn_economy(world)
    apply_turn_food_economy(world)
    resolve_food_and_disease_shocks(world)
    apply_shock_population_losses(world)
    update_region_integration(world, time_step_years=SEASONAL_TIME_STEP_YEARS)
    refresh_administrative_state(world)
    update_technology_diffusion(world)
    update_faction_resource_economy(world, advance_resources=False)
    resolve_trade_network_shocks(world)
    update_faction_resource_economy(world, advance_resources=False)
    resolve_population_migration(world)
    update_faction_resource_economy(world, advance_resources=False)
    update_shock_rollups(world)
    refresh_military_state(world)
    return economy_snapshot


def _run_year_end_phase(world):
    advance_long_run_economic_dynamics(world)
    update_religious_legitimacy(world)
    resolve_dynastic_succession(world)
    update_region_populations(world)
    update_region_settlement_levels(world)
    update_urban_specializations(world)
    update_elite_blocs(world)
    update_ideologies(world)
    update_rebel_faction_status(world)
    update_nomadic_social_forms(world)
    update_faction_polity_tiers(world)
    update_civilization_cycle(world)
    for faction_name in get_active_faction_names(world):
        choose_standing_orders(faction_name, world)


def _run_diplomatic_update_phase(world, economy_snapshot):
    refresh_administrative_state(world)
    refresh_military_state(world)
    update_relationships(world)
    apply_tributary_flows(world, economy_snapshot=economy_snapshot)
    apply_language_contact_borrowing(world)
    update_faction_doctrines(world)
    refresh_all_faction_visibility(world)


def _print_economy_summaries(world, turn_order, economy_snapshot):
    for faction_name in turn_order:
        data = economy_snapshot[faction_name]
        print(
            f"{faction_name} economy: base_income={data['base_income']}, "
            f"scale_penalty={data['empire_penalty']}, "
            f"effective_income={data['effective_income']}, "
            f"maintenance={data['maintenance']}, net={data['net']}, "
            f"treasury={world.factions[faction_name].treasury}"
        )


def _record_turn_observations(world, economy_snapshot):
    record_turn_metrics(world, economy_snapshot=economy_snapshot)
    record_region_history(world)
    world.turn += 1


def run_turn(
    world,
    faction_order=None,
    randomize_order=True,
    verbose=True,
    action_provider=None,
    action_diagnostics_callback=None,
):
    """Runs one full turn of the simulation."""
    current_turn = world.turn

    if verbose:
        print(f"\n{format_turn_label(current_turn)}")

    _run_turn_start_phase(world)
    _run_advance_projects_phase(world)
    turn_order = _build_turn_order(
        world,
        faction_order=faction_order,
        randomize_order=randomize_order,
    )
    _run_faction_action_phase(
        world,
        turn_order,
        verbose=verbose,
        action_provider=action_provider,
        action_diagnostics_callback=action_diagnostics_callback,
    )
    run_subfaction_phase(world)
    economy_snapshot = _run_post_action_phase(world)
    if is_year_end(current_turn):
        _run_year_end_phase(world)
    _run_diplomatic_update_phase(world, economy_snapshot)
    if verbose:
        _print_economy_summaries(world, turn_order, economy_snapshot)
    _record_turn_observations(world, economy_snapshot)


def run_simulation(
    world,
    num_turns,
    faction_order=None,
    verbose=True,
    action_provider=None,
    turn_callback=None,
    action_diagnostics_callback=None,
):
    """Runs the simulation for the given number of turns."""

    for _ in range(num_turns):
        run_turn(
            world,
            faction_order=faction_order,
            verbose=verbose,
            action_provider=action_provider,
            action_diagnostics_callback=action_diagnostics_callback,
        )
        if turn_callback is not None:
            turn_callback(world)

    return world
