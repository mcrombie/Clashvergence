from src.diplomacy import get_faction_diplomacy_summary
from src.region_state import get_region_core_status


def get_turn_events(world, turn):
    """Returns all events recorded for a specific turn."""
    return [event for event in world.events if event.turn == turn]


def get_owned_region_counts(world):
    """Returns the number of regions currently owned by each faction."""
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def build_turn_metrics(world, economy_snapshot=None):
    """Builds a per-faction metrics snapshot for the just-completed turn."""
    turn_events = get_turn_events(world, world.turn)
    owned_region_counts = get_owned_region_counts(world)
    faction_metrics = {}

    for faction_name, faction in world.factions.items():
        attacks = 0
        expansions = 0
        developments = 0
        homeland_regions = 0
        core_regions = 0
        frontier_regions = 0
        rural_regions = 0
        town_regions = 0
        city_regions = 0
        economy_data = (economy_snapshot or {}).get(faction_name, {})
        income = economy_data.get("base_income", 0)
        nominal_income = economy_data.get("nominal_income", income)
        empire_penalty = economy_data.get("empire_penalty", 0)
        effective_income = economy_data.get("effective_income", 0)
        maintenance = economy_data.get("maintenance", 0)
        total_population = economy_data.get("population")
        total_surplus = economy_data.get("total_surplus", 0.0)
        resource_access = faction.resource_access or {}
        gross_output = faction.resource_gross_output or {}
        effective_access = faction.resource_effective_access or {}
        isolated_output = faction.resource_isolated_output or {}
        resource_shortages = faction.resource_shortages or {}
        derived_capacity = faction.derived_capacity or {}

        for event in turn_events:
            if event.faction != faction_name:
                continue

            if event.type == "attack":
                attacks += 1
            elif event.type == "expand":
                expansions += 1
            elif event.type in {"develop", "invest"}:
                developments += 1

        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            status = get_region_core_status(region)
            if status == "homeland":
                homeland_regions += 1
            elif status == "core":
                core_regions += 1
            else:
                frontier_regions += 1
            settlement_level = region.settlement_level
            if settlement_level == "city":
                city_regions += 1
            elif settlement_level == "town":
                town_regions += 1
            elif settlement_level == "rural":
                rural_regions += 1
            if total_population is None:
                total_population = 0
            if "population" not in economy_data:
                total_population += region.population

        faction_metrics[faction_name] = {
            "treasury": faction.treasury,
            "regions": owned_region_counts[faction_name],
            "population": total_population or 0,
            "total_surplus": round(total_surplus, 2),
            "attacks": attacks,
            "expansions": expansions,
            "developments": developments,
            "investments": developments,
            "income": income,
            "nominal_income": nominal_income,
            "empire_penalty": empire_penalty,
            "effective_income": effective_income,
            "maintenance": maintenance,
            "net_income": effective_income - maintenance,
            "doctrine_label": faction.doctrine_label,
            "terrain_identity": faction.doctrine_profile.terrain_identity,
            "homeland_identity": faction.doctrine_profile.homeland_identity,
            "climate_identity": faction.doctrine_profile.climate_identity,
            "expansion_posture": faction.doctrine_profile.expansion_posture,
            "war_posture": faction.doctrine_profile.war_posture,
            "development_posture": faction.doctrine_profile.development_posture,
            "insularity": faction.doctrine_profile.insularity,
            "homeland_regions": homeland_regions,
            "core_regions": core_regions,
            "frontier_regions": frontier_regions,
            "rural_regions": rural_regions,
            "town_regions": town_regions,
            "city_regions": city_regions,
            "polity_tier": faction.polity_tier,
            "government_form": faction.government_form,
            "food_security": round(derived_capacity.get("food_security", 0.0), 3),
            "mobility_capacity": round(derived_capacity.get("mobility_capacity", 0.0), 3),
            "construction_capacity": round(derived_capacity.get("construction_capacity", 0.0), 3),
            "metal_capacity": round(derived_capacity.get("metal_capacity", 0.0), 3),
            "taxable_value": round(derived_capacity.get("taxable_value", 0.0), 3),
            "food_stored": round(faction.food_stored, 3),
            "food_storage_capacity": round(faction.food_storage_capacity, 3),
            "food_produced": round(faction.food_produced, 3),
            "food_consumption": round(faction.food_consumption, 3),
            "food_balance": round(faction.food_balance, 3),
            "food_deficit": round(faction.food_deficit, 3),
            "food_spoilage": round(faction.food_spoilage, 3),
            "food_overflow": round(faction.food_overflow, 3),
            "trade_income": round(faction.trade_income, 3),
            "trade_transit_value": round(faction.trade_transit_value, 3),
            "trade_import_dependency": round(faction.trade_import_dependency, 3),
            "trade_corridor_exposure": round(faction.trade_corridor_exposure, 3),
            "trade_foreign_income": round(faction.trade_foreign_income, 3),
            "trade_foreign_imported_flow": round(faction.trade_foreign_imported_flow, 3),
            "migration_inflow": int(faction.migration_inflow or 0),
            "migration_outflow": int(faction.migration_outflow or 0),
            "refugee_inflow": int(faction.refugee_inflow or 0),
            "refugee_outflow": int(faction.refugee_outflow or 0),
            "frontier_settlers": int(faction.frontier_settlers or 0),
            "grain_access": round(resource_access.get("grain", 0.0), 3),
            "livestock_access": round(resource_access.get("livestock", 0.0), 3),
            "wild_food_access": round(resource_access.get("wild_food", 0.0), 3),
            "timber_access": round(resource_access.get("timber", 0.0), 3),
            "horse_access": round(resource_access.get("horses", 0.0), 3),
            "copper_access": round(resource_access.get("copper", 0.0), 3),
            "stone_access": round(resource_access.get("stone", 0.0), 3),
            "salt_access": round(resource_access.get("salt", 0.0), 3),
            "textiles_access": round(resource_access.get("textiles", 0.0), 3),
            "gross_grain_output": round(gross_output.get("grain", 0.0), 3),
            "gross_livestock_output": round(gross_output.get("livestock", 0.0), 3),
            "gross_horse_output": round(gross_output.get("horses", 0.0), 3),
            "gross_copper_output": round(gross_output.get("copper", 0.0), 3),
            "gross_stone_output": round(gross_output.get("stone", 0.0), 3),
            "gross_salt_output": round(gross_output.get("salt", 0.0), 3),
            "gross_textiles_output": round(gross_output.get("textiles", 0.0), 3),
            "effective_grain_access": round(effective_access.get("grain", 0.0), 3),
            "effective_livestock_access": round(effective_access.get("livestock", 0.0), 3),
            "effective_horse_access": round(effective_access.get("horses", 0.0), 3),
            "effective_copper_access": round(effective_access.get("copper", 0.0), 3),
            "effective_stone_access": round(effective_access.get("stone", 0.0), 3),
            "effective_salt_access": round(effective_access.get("salt", 0.0), 3),
            "effective_textiles_access": round(effective_access.get("textiles", 0.0), 3),
            "isolated_grain_output": round(isolated_output.get("grain", 0.0), 3),
            "isolated_livestock_output": round(isolated_output.get("livestock", 0.0), 3),
            "isolated_horse_output": round(isolated_output.get("horses", 0.0), 3),
            "isolated_copper_output": round(isolated_output.get("copper", 0.0), 3),
            "isolated_stone_output": round(isolated_output.get("stone", 0.0), 3),
            "isolated_salt_output": round(isolated_output.get("salt", 0.0), 3),
            "isolated_textiles_output": round(isolated_output.get("textiles", 0.0), 3),
            "food_shortage": round(resource_shortages.get("food_security", 0.0), 3),
            "mobility_shortage": round(resource_shortages.get("mobility_capacity", 0.0), 3),
            "metal_shortage": round(resource_shortages.get("metal_capacity", 0.0), 3),
            "construction_shortage": round(resource_shortages.get("construction_capacity", 0.0), 3),
            "salt_shortage": round(resource_shortages.get("salt", 0.0), 3),
            "textiles_shortage": round(resource_shortages.get("textiles", 0.0), 3),
            **get_faction_diplomacy_summary(world, faction_name),
        }

    return {
        "turn": world.turn + 1,
        "factions": faction_metrics,
    }


def record_turn_metrics(world, economy_snapshot=None):
    """Appends the latest per-turn metrics snapshot to the world state."""
    world.metrics.append(build_turn_metrics(world, economy_snapshot=economy_snapshot))


def get_metrics_log(world):
    """Returns the raw metrics log."""
    return world.metrics


def get_turn_metrics(world, turn_number):
    """Returns the metrics snapshot for a one-based turn number."""
    for snapshot in world.metrics:
        if snapshot["turn"] == turn_number:
            return snapshot

    return None


def get_faction_metrics_history(world, faction_name):
    """Returns one faction's metrics across all recorded turns."""
    history = []

    for snapshot in world.metrics:
        if faction_name in snapshot["factions"]:
            history.append({
                "turn": snapshot["turn"],
                **snapshot["factions"][faction_name],
            })

    return history


def _get_ranked_factions(snapshot, metric_key):
    return sorted(
        snapshot["factions"].items(),
        key=lambda item: (-item[1].get(metric_key, 0), item[0]),
    )


def _get_metric_leaders(snapshot, metric_key):
    ranked = _get_ranked_factions(snapshot, metric_key)
    if not ranked:
        return []

    top_value = ranked[0][1].get(metric_key, 0)
    return [
        faction_name
        for faction_name, metrics in ranked
        if metrics.get(metric_key, 0) == top_value
    ]


def analyze_competition_metrics(world):
    """Builds high-level dynamics metrics from the recorded turn snapshots."""
    snapshots = get_metrics_log(world)
    faction_names = set(world.factions)
    for snapshot in snapshots:
        faction_names.update(snapshot["factions"])
    faction_names = list(faction_names)
    eliminations = {
        faction_name: {
            "eliminated": False,
            "turn": None,
        }
        for faction_name in faction_names
    }
    result = {
        "lead_changes": 0,
        "largest_treasury_lead": {
            "turn": None,
            "leader": None,
            "runner_up": None,
            "margin": 0,
        },
        "largest_region_lead": {
            "turn": None,
            "leader": None,
            "runner_up": None,
            "margin": 0,
        },
        "runaway": {
            "detected": False,
            "winner": None,
            "start_turn": None,
        },
        "comeback": {
            "detected": False,
            "winner": None,
            "midpoint_turn": None,
            "midpoint_deficit": 0,
            "max_deficit_overcome": 0,
        },
        "eliminations": eliminations,
        "eliminated_factions": 0,
    }

    if not snapshots:
        return result

    previous_outright_leader = None
    had_regions = {faction_name: False for faction_name in faction_names}

    for snapshot in snapshots:
        treasury_ranked = _get_ranked_factions(snapshot, "treasury")
        region_ranked = _get_ranked_factions(snapshot, "regions")
        treasury_leaders = _get_metric_leaders(snapshot, "treasury")

        if len(treasury_leaders) == 1:
            outright_leader = treasury_leaders[0]
            if previous_outright_leader is None:
                previous_outright_leader = outright_leader
            elif outright_leader != previous_outright_leader:
                result["lead_changes"] += 1
                previous_outright_leader = outright_leader

        if len(treasury_ranked) >= 2:
            treasury_margin = treasury_ranked[0][1]["treasury"] - treasury_ranked[1][1]["treasury"]
            if treasury_margin > result["largest_treasury_lead"]["margin"]:
                result["largest_treasury_lead"] = {
                    "turn": snapshot["turn"],
                    "leader": treasury_ranked[0][0],
                    "runner_up": treasury_ranked[1][0],
                    "margin": treasury_margin,
                }

        if len(region_ranked) >= 2:
            region_margin = region_ranked[0][1]["regions"] - region_ranked[1][1]["regions"]
            if region_margin > result["largest_region_lead"]["margin"]:
                result["largest_region_lead"] = {
                    "turn": snapshot["turn"],
                    "leader": region_ranked[0][0],
                    "runner_up": region_ranked[1][0],
                    "margin": region_margin,
                }

        for faction_name in faction_names:
            region_count = snapshot["factions"].get(faction_name, {}).get("regions", 0)
            if region_count > 0:
                had_regions[faction_name] = True
            elif had_regions[faction_name] and not eliminations[faction_name]["eliminated"]:
                eliminations[faction_name]["eliminated"] = True
                eliminations[faction_name]["turn"] = snapshot["turn"]

    result["eliminated_factions"] = sum(
        1
        for elimination in eliminations.values()
        if elimination["eliminated"]
    )

    final_snapshot = snapshots[-1]
    final_leaders = _get_metric_leaders(final_snapshot, "treasury")
    if len(final_leaders) != 1:
        return result

    winner = final_leaders[0]

    for index, snapshot in enumerate(snapshots):
        leaders = _get_metric_leaders(snapshot, "treasury")
        if leaders != [winner]:
            continue

        if all(_get_metric_leaders(later_snapshot, "treasury") == [winner] for later_snapshot in snapshots[index:]):
            result["runaway"] = {
                "detected": True,
                "winner": winner,
                "start_turn": snapshot["turn"],
            }
            break

    midpoint_index = len(snapshots) // 2
    midpoint_snapshot = snapshots[midpoint_index]
    midpoint_ranked = _get_ranked_factions(midpoint_snapshot, "treasury")
    midpoint_treasury = midpoint_snapshot["factions"].get(winner, {}).get("treasury", 0)
    midpoint_deficit = midpoint_ranked[0][1]["treasury"] - midpoint_treasury
    max_deficit_overcome = 0

    for snapshot in snapshots:
        ranked = _get_ranked_factions(snapshot, "treasury")
        winner_treasury = snapshot["factions"].get(winner, {}).get("treasury", 0)
        deficit = ranked[0][1]["treasury"] - winner_treasury
        if deficit > max_deficit_overcome:
            max_deficit_overcome = deficit

    result["comeback"] = {
        "detected": winner not in _get_metric_leaders(midpoint_snapshot, "treasury"),
        "winner": winner,
        "midpoint_turn": midpoint_snapshot["turn"],
        "midpoint_deficit": midpoint_deficit,
        "max_deficit_overcome": max_deficit_overcome,
    }

    return result
