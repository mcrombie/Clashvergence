from src.administration import refresh_administrative_state
from src.calendar import format_turn_date, get_turn_year
from src.config import DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD, DUAL_TRACK_MIN_REGIONS
from src.diplomacy import get_faction_diplomacy_summary
from src.internal_politics import (
    ALL_ELITE_BLOCS,
    BLOC_PREFERRED_TRACK,
    get_bloc_action_biases,
    get_faction_elite_summary,
)
from src.ideology import ALL_IDEOLOGIES, get_faction_ideology_summary
from src.military import refresh_military_state
from src.movement import get_faction_seafaring_level, get_maritime_reachable_region_names
from src.region_state import get_region_core_status
from src.social_forms import get_band_camp_region_name
from src.technology import (
    ALL_TECHNOLOGIES,
    TECH_COPPER_WORKING,
    TECH_IRRIGATION_METHODS,
    TECH_MARKET_ACCOUNTING,
    TECH_ORGANIZED_LEVIES,
    TECH_PASTORAL_BREEDING,
    TECH_ROAD_ADMINISTRATION,
    TECH_SEAFARING,
    TECH_TEMPLE_RECORDKEEPING,
)
from src.urban import ALL_URBAN_SPECIALIZATIONS, URBAN_NONE


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
    refresh_administrative_state(world)
    refresh_military_state(world, emit_events=False)
    turn_events = get_turn_events(world, world.turn)
    owned_region_counts = get_owned_region_counts(world)
    faction_metrics = {}

    for faction_name, faction in world.factions.items():
        attacks = 0
        expansions = 0
        developments = 0
        band_migrations = 0
        maritime_attacks = 0
        maritime_expansions = 0
        homeland_regions = 0
        core_regions = 0
        frontier_regions = 0
        rural_regions = 0
        town_regions = 0
        city_regions = 0
        urban_specialization_counts = {
            role: 0
            for role in ALL_URBAN_SPECIALIZATIONS
            if role != URBAN_NONE
        }
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
        produced_goods = faction.produced_goods or {}
        production_chain_shortages = faction.production_chain_shortages or {}
        known_technologies = faction.known_technologies or {}
        institutional_technologies = faction.institutional_technologies or {}
        elite_summary = get_faction_elite_summary(faction)
        ideology_summary = get_faction_ideology_summary(faction)
        bloc_action_biases = get_bloc_action_biases(faction)
        bloc_bias_abs = (
            sum(abs(value) for value in bloc_action_biases.values())
            / max(1, len(bloc_action_biases))
        )

        for event in turn_events:
            if event.faction != faction_name:
                continue

            if event.type == "attack":
                attacks += 1
                if event.details.get("maritime_operation"):
                    maritime_attacks += 1
            elif event.type == "expand":
                expansions += 1
                if event.details.get("maritime_operation"):
                    maritime_expansions += 1
            elif event.type == "band_migration":
                band_migrations += 1
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
            urban_role = region.urban_specialization or URBAN_NONE
            if urban_role != URBAN_NONE:
                urban_specialization_counts.setdefault(urban_role, 0)
                urban_specialization_counts[urban_role] += 1
            if total_population is None:
                total_population = 0
            if "population" not in economy_data:
                total_population += region.population

        military_track_used = bool(getattr(faction, "military_track_used", False) or attacks or expansions)
        admin_track_used = bool(getattr(faction, "admin_track_used", False) or developments)
        dual_track_qualified = bool(
            not faction.proto_state
            and owned_region_counts[faction_name] >= DUAL_TRACK_MIN_REGIONS
            and float(faction.administrative_efficiency or 1.0) >= DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD
        )
        dominant_bloc_track = BLOC_PREFERRED_TRACK.get(faction.strongest_elite_bloc, "")
        maritime_expansion_reach = len(get_maritime_reachable_region_names(
            world,
            faction_name,
            purpose="expand",
        ))
        maritime_attack_reach = len(get_maritime_reachable_region_names(
            world,
            faction_name,
            purpose="attack",
        ))

        faction_metrics[faction_name] = {
            "treasury": faction.treasury,
            "regions": owned_region_counts[faction_name],
            "population": total_population or 0,
            "total_surplus": round(total_surplus, 2),
            "attacks": attacks,
            "expansions": expansions,
            "maritime_attacks": maritime_attacks,
            "maritime_expansions": maritime_expansions,
            "maritime_actions": maritime_attacks + maritime_expansions,
            "maritime_expansion_reach": maritime_expansion_reach,
            "maritime_attack_reach": maritime_attack_reach,
            "developments": developments,
            "investments": developments,
            "band_migrations": band_migrations,
            "military_track_used": military_track_used,
            "admin_track_used": admin_track_used,
            "dual_track_qualified": dual_track_qualified,
            "dual_track_both_tracks_used": bool(dual_track_qualified and military_track_used and admin_track_used),
            "bloc_action_bias_abs": round(bloc_bias_abs, 4),
            "dominant_bloc_track": dominant_bloc_track,
            "dominant_bloc_military_alignment": bool(
                dominant_bloc_track == "military" and military_track_used
            ),
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
            "capital_region": faction.capital_region,
            "urban_network_value": round(float(faction.urban_network_value or 0.0), 3),
            "urban_specialized_regions": sum(urban_specialization_counts.values()),
            "capital_regions": urban_specialization_counts.get("capital", 0),
            "craft_center_regions": urban_specialization_counts.get("craft_center", 0),
            "port_city_regions": urban_specialization_counts.get("port_city", 0),
            "temple_city_regions": urban_specialization_counts.get("temple_city", 0),
            "frontier_fort_regions": urban_specialization_counts.get("frontier_fort", 0),
            "mining_town_regions": urban_specialization_counts.get("mining_town", 0),
            "scholarly_hub_regions": urban_specialization_counts.get("scholarly_hub", 0),
            "market_town_regions": urban_specialization_counts.get("market_town", 0),
            "economic_identity": faction.economic_identity,
            "economic_identity_secondary": faction.economic_identity_secondary,
            "economic_identity_scores": dict(faction.economic_identity_scores or {}),
            **{
                f"economic_identity_{identity_name}_score": round(
                    float((faction.economic_identity_scores or {}).get(identity_name, 0.0)),
                    3,
                )
                for identity_name in (
                    "agricultural",
                    "pastoral",
                    "commercial",
                    "industrial",
                    "maritime",
                    "imperial",
                )
            },
            "polity_tier": faction.polity_tier,
            "government_form": faction.government_form,
            "camp_region": get_band_camp_region_name(world, faction_name),
            "tribalization_progress": round(float(faction.tribalization_progress or 0.0), 3),
            "band_settled_turns": int(faction.band_settled_turns or 0),
            "migration_pressure": round(float(faction.migration_pressure or 0.0), 3),
            "migration_cooldown_turns": int(faction.migration_cooldown_turns or 0),
            "last_migration_reason": faction.last_migration_reason,
            "last_migration_turn": faction.last_migration_turn,
            "dynasty_name": faction.succession.dynasty_name,
            "ruler_name": faction.succession.ruler_name,
            "ruler_age": int(faction.succession.ruler_age or 0),
            "ruler_reign_turns": int(faction.succession.ruler_reign_turns or 0),
            "heir_name": faction.succession.heir_name,
            "heir_age": int(faction.succession.heir_age or 0),
            "heir_preparedness": round(float(faction.succession.heir_preparedness or 0.0), 3),
            "legitimacy": round(float(faction.succession.legitimacy or 0.0), 3),
            "dynasty_prestige": round(float(faction.succession.dynasty_prestige or 0.0), 3),
            "regency_turns": int(faction.succession.regency_turns or 0),
            "succession_crisis_turns": int(faction.succession.succession_crisis_turns or 0),
            "claimant_pressure": round(float(faction.succession.claimant_pressure or 0.0), 3),
            "last_succession_turn": faction.succession.last_succession_turn,
            "last_succession_type": faction.succession.last_succession_type,
            "strongest_elite_bloc": elite_summary["strongest_elite_bloc"],
            "strongest_elite_bloc_label": elite_summary["strongest_elite_bloc_label"],
            "alienated_elite_bloc": elite_summary["alienated_elite_bloc"],
            "alienated_elite_bloc_label": elite_summary["alienated_elite_bloc_label"],
            "elite_unrest_pressure": elite_summary["elite_unrest_pressure"],
            "elite_bloc_count": len(faction.elite_blocs),
            **{
                f"{bloc_type}_influence": round(
                    next((bloc.influence for bloc in faction.elite_blocs if bloc.bloc_type == bloc_type), 0.0),
                    3,
                )
                for bloc_type in ALL_ELITE_BLOCS
            },
            **{
                f"{bloc_type}_loyalty": round(
                    next((bloc.loyalty for bloc in faction.elite_blocs if bloc.bloc_type == bloc_type), 0.0),
                    3,
                )
                for bloc_type in ALL_ELITE_BLOCS
            },
            "dominant_ideology": ideology_summary["dominant_ideology"],
            "dominant_ideology_label": ideology_summary["dominant_ideology_label"],
            "ideology_cohesion": ideology_summary["ideology_cohesion"],
            "ideology_radicalism": ideology_summary["ideology_radicalism"],
            "ideology_institutionalism": ideology_summary["ideology_institutionalism"],
            "ideology_reform_pressure": ideology_summary["ideology_reform_pressure"],
            "legitimacy_model": ideology_summary["legitimacy_model"],
            **{
                f"{ideology_key}_current": round(
                    faction.ideology.currents.get(ideology_key, 0.0),
                    3,
                )
                for ideology_key in ALL_IDEOLOGIES
            },
            "official_religion": faction.religion.official_religion,
            "religious_legitimacy": round(float(faction.religion.religious_legitimacy or 0.0), 3),
            "clergy_support": round(float(faction.religion.clergy_support or 0.0), 3),
            "religious_tolerance": round(float(faction.religion.religious_tolerance or 0.0), 3),
            "religious_zeal": round(float(faction.religion.religious_zeal or 0.0), 3),
            "state_cult_strength": round(float(faction.religion.state_cult_strength or 0.0), 3),
            "reform_pressure": round(float(faction.religion.reform_pressure or 0.0), 3),
            "sacred_sites_controlled": int(faction.religion.sacred_sites_controlled or 0),
            "total_sacred_sites": int(faction.religion.total_sacred_sites or 0),
            "last_reform_turn": faction.religion.last_reform_turn,
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
            "trade_warfare_damage": round(faction.trade_warfare_damage, 3),
            "trade_blockade_losses": round(faction.trade_blockade_losses, 3),
            "merchant_capacity": round(float(faction.merchant_capacity or 0.0), 3),
            "shock_exposure": round(float(faction.shock_exposure or 0.0), 3),
            "shock_resilience": round(float(faction.shock_resilience or 0.0), 3),
            "famine_pressure": round(float(faction.famine_pressure or 0.0), 3),
            "epidemic_pressure": round(float(faction.epidemic_pressure or 0.0), 3),
            "trade_collapse_exposure": round(float(faction.trade_collapse_exposure or 0.0), 3),
            "civilizational_phase": faction.civilizational_phase,
            "civilizational_phase_turns": int(faction.civilizational_phase_turns or 0),
            "social_energy": round(float(faction.social_energy or 0.0), 3),
            "religious_vitality": round(float(faction.religious_vitality or 0.0), 3),
            "material_accumulation": round(float(faction.material_accumulation or 0.0), 3),
            "intellectual_activity": round(float(faction.intellectual_activity or 0.0), 3),
            "revival_surge_turns": int(faction.revival_surge_turns or 0),
            "manpower_pool": round(float(faction.manpower_pool or 0.0), 3),
            "manpower_capacity": round(float(faction.manpower_capacity or 0.0), 3),
            "standing_forces": round(float(faction.standing_forces or 0.0), 3),
            "army_quality": round(float(faction.army_quality or 0.0), 3),
            "military_readiness": round(float(faction.military_readiness or 0.0), 3),
            "logistics_capacity": round(float(faction.logistics_capacity or 0.0), 3),
            "logistics_radius": round(float(faction.logistics_radius or 0.0), 3),
            "naval_power": round(float(faction.naval_power or 0.0), 3),
            "seafaring_level": round(get_faction_seafaring_level(world, faction_name), 3),
            "force_projection": round(float(faction.force_projection or 0.0), 3),
            "military_tradition": round(float(faction.military_tradition or 0.0), 3),
            "military_reform_pressure": round(float(faction.military_reform_pressure or 0.0), 3),
            "military_upkeep": round(float(faction.military_upkeep or 0.0), 3),
            "campaign_supply_draw": round(float(faction.campaign_supply_draw or 0.0), 3),
            "campaign_supply_crisis": round(float(faction.campaign_supply_crisis or 0.0), 3),
            "campaign_supply_crisis_turns": int(faction.campaign_supply_crisis_turns or 0),
            "weapons_quality_bonus": round(float(faction.weapons_quality_bonus or 0.0), 3),
            "campaign_cost_pressure": round(float(faction.campaign_cost_pressure or 0.0), 3),
            "tribute_income": round(faction.tribute_income, 3),
            "tribute_paid": round(faction.tribute_paid, 3),
            "administrative_capacity": round(float(faction.administrative_capacity or 0.0), 3),
            "administrative_load": round(float(faction.administrative_load or 0.0), 3),
            "administrative_efficiency": round(float(faction.administrative_efficiency or 1.0), 3),
            "administrative_reach": round(float(faction.administrative_reach or 1.0), 3),
            "administrative_overextension": round(float(faction.administrative_overextension or 0.0), 3),
            "administrative_overextension_penalty": round(float(faction.administrative_overextension_penalty or 0.0), 3),
            "capital_connected_regions": int(faction.capital_connected_regions or 0),
            "capital_isolated_regions": int(faction.capital_isolated_regions or 0),
            "capital_fragment_count": int(faction.capital_fragment_count or 0),
            "capital_connectivity_penalty": round(float(faction.capital_connectivity_penalty or 0.0), 3),
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
            "iron_access": round(resource_access.get("iron", 0.0), 3),
            "gold_access": round(resource_access.get("gold", 0.0), 3),
            "stone_access": round(resource_access.get("stone", 0.0), 3),
            "salt_access": round(resource_access.get("salt", 0.0), 3),
            "textiles_access": round(resource_access.get("textiles", 0.0), 3),
            "gross_grain_output": round(gross_output.get("grain", 0.0), 3),
            "gross_livestock_output": round(gross_output.get("livestock", 0.0), 3),
            "gross_horse_output": round(gross_output.get("horses", 0.0), 3),
            "gross_copper_output": round(gross_output.get("copper", 0.0), 3),
            "gross_iron_output": round(gross_output.get("iron", 0.0), 3),
            "gross_gold_output": round(gross_output.get("gold", 0.0), 3),
            "gross_stone_output": round(gross_output.get("stone", 0.0), 3),
            "gross_salt_output": round(gross_output.get("salt", 0.0), 3),
            "gross_textiles_output": round(gross_output.get("textiles", 0.0), 3),
            "effective_grain_access": round(effective_access.get("grain", 0.0), 3),
            "effective_livestock_access": round(effective_access.get("livestock", 0.0), 3),
            "effective_horse_access": round(effective_access.get("horses", 0.0), 3),
            "effective_copper_access": round(effective_access.get("copper", 0.0), 3),
            "effective_iron_access": round(effective_access.get("iron", 0.0), 3),
            "effective_gold_access": round(effective_access.get("gold", 0.0), 3),
            "effective_stone_access": round(effective_access.get("stone", 0.0), 3),
            "effective_salt_access": round(effective_access.get("salt", 0.0), 3),
            "effective_textiles_access": round(effective_access.get("textiles", 0.0), 3),
            "isolated_grain_output": round(isolated_output.get("grain", 0.0), 3),
            "isolated_livestock_output": round(isolated_output.get("livestock", 0.0), 3),
            "isolated_horse_output": round(isolated_output.get("horses", 0.0), 3),
            "isolated_copper_output": round(isolated_output.get("copper", 0.0), 3),
            "isolated_iron_output": round(isolated_output.get("iron", 0.0), 3),
            "isolated_gold_output": round(isolated_output.get("gold", 0.0), 3),
            "isolated_stone_output": round(isolated_output.get("stone", 0.0), 3),
            "isolated_salt_output": round(isolated_output.get("salt", 0.0), 3),
            "isolated_textiles_output": round(isolated_output.get("textiles", 0.0), 3),
            "food_shortage": round(resource_shortages.get("food_security", 0.0), 3),
            "mobility_shortage": round(resource_shortages.get("mobility_capacity", 0.0), 3),
            "metal_shortage": round(resource_shortages.get("metal_capacity", 0.0), 3),
            "construction_shortage": round(resource_shortages.get("construction_capacity", 0.0), 3),
            "iron_shortage": round(resource_shortages.get("iron", 0.0), 3),
            "gold_shortage": round(resource_shortages.get("gold", 0.0), 3),
            "salt_shortage": round(resource_shortages.get("salt", 0.0), 3),
            "textiles_shortage": round(resource_shortages.get("textiles", 0.0), 3),
            "tools_output": round(produced_goods.get("tools", 0.0), 3),
            "iron_goods_output": round(produced_goods.get("iron_goods", 0.0), 3),
            "weapons_output": round(produced_goods.get("weapons", 0.0), 3),
            "provisions_output": round(produced_goods.get("provisions", 0.0), 3),
            "crafted_goods_output": round(produced_goods.get("crafted_goods", 0.0), 3),
            "ships_output": round(produced_goods.get("ships", 0.0), 3),
            "urban_surplus_output": round(produced_goods.get("urban_surplus", 0.0), 3),
            "tools_shortage": round(production_chain_shortages.get("tools", 0.0), 3),
            "iron_goods_shortage": round(production_chain_shortages.get("iron_goods", 0.0), 3),
            "weapons_shortage": round(production_chain_shortages.get("weapons", 0.0), 3),
            "provisions_shortage": round(production_chain_shortages.get("provisions", 0.0), 3),
            "crafted_goods_shortage": round(production_chain_shortages.get("crafted_goods", 0.0), 3),
            "ships_shortage": round(production_chain_shortages.get("ships", 0.0), 3),
            "urban_surplus_shortage": round(
                production_chain_shortages.get("urban_surplus", 0.0),
                3,
            ),
            "grain_stockpile": round((faction.resource_stockpiles or {}).get("grain", 0.0), 3),
            "copper_stockpile": round((faction.resource_stockpiles or {}).get("copper", 0.0), 3),
            "iron_stockpile": round((faction.resource_stockpiles or {}).get("iron", 0.0), 3),
            "salt_stockpile": round((faction.resource_stockpiles or {}).get("salt", 0.0), 3),
            "weapons_stockpile": round((faction.produced_good_stockpiles or {}).get("weapons", 0.0), 3),
            "provisions_stockpile": round((faction.produced_good_stockpiles or {}).get("provisions", 0.0), 3),
            "grain_price": round((faction.resource_price_index or {}).get("grain", 1.0), 3),
            "copper_price": round((faction.resource_price_index or {}).get("copper", 1.0), 3),
            "iron_price": round((faction.resource_price_index or {}).get("iron", 1.0), 3),
            "salt_price": round((faction.resource_price_index or {}).get("salt", 1.0), 3),
            "textiles_price": round((faction.resource_price_index or {}).get("textiles", 1.0), 3),
            "average_technology_presence": round(
                sum(known_technologies.get(technology_key, 0.0) for technology_key in ALL_TECHNOLOGIES)
                / max(1, len(ALL_TECHNOLOGIES)),
                3,
            ),
            "average_institutional_technology": round(
                sum(institutional_technologies.get(technology_key, 0.0) for technology_key in ALL_TECHNOLOGIES)
                / max(1, len(ALL_TECHNOLOGIES)),
                3,
            ),
            "irrigation_methods": round(known_technologies.get(TECH_IRRIGATION_METHODS, 0.0), 3),
            "pastoral_breeding": round(known_technologies.get(TECH_PASTORAL_BREEDING, 0.0), 3),
            "copper_working": round(known_technologies.get(TECH_COPPER_WORKING, 0.0), 3),
            "road_administration": round(known_technologies.get(TECH_ROAD_ADMINISTRATION, 0.0), 3),
            "market_accounting": round(known_technologies.get(TECH_MARKET_ACCOUNTING, 0.0), 3),
            "organized_levies": round(known_technologies.get(TECH_ORGANIZED_LEVIES, 0.0), 3),
            "temple_recordkeeping": round(known_technologies.get(TECH_TEMPLE_RECORDKEEPING, 0.0), 3),
            "seafaring": round(known_technologies.get(TECH_SEAFARING, 0.0), 3),
            "institutional_irrigation_methods": round(institutional_technologies.get(TECH_IRRIGATION_METHODS, 0.0), 3),
            "institutional_pastoral_breeding": round(institutional_technologies.get(TECH_PASTORAL_BREEDING, 0.0), 3),
            "institutional_copper_working": round(institutional_technologies.get(TECH_COPPER_WORKING, 0.0), 3),
            "institutional_road_administration": round(institutional_technologies.get(TECH_ROAD_ADMINISTRATION, 0.0), 3),
            "institutional_market_accounting": round(institutional_technologies.get(TECH_MARKET_ACCOUNTING, 0.0), 3),
            "institutional_organized_levies": round(institutional_technologies.get(TECH_ORGANIZED_LEVIES, 0.0), 3),
            "institutional_temple_recordkeeping": round(institutional_technologies.get(TECH_TEMPLE_RECORDKEEPING, 0.0), 3),
            "institutional_seafaring": round(institutional_technologies.get(TECH_SEAFARING, 0.0), 3),
            **get_faction_diplomacy_summary(world, faction_name),
        }

    return {
        "turn": world.turn + 1,
        "year": get_turn_year(world.turn),
        "season": "Annual",
        "date_label": format_turn_date(world.turn),
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
