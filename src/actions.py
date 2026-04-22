import random

from src.diplomacy import get_attack_diplomacy_modifier, get_relationship_status
from src.config import (
    ATTACK_COST,
    ATTACK_FAILURE_PENALTY,
    ATTACK_SUCCESS_MAX,
    ATTACK_SUCCESS_MIN,
    ATTACK_SUCCESS_STRENGTH_FACTOR,
    DIPLOMACY_ETHNIC_CLAIM_ATTACK_BONUS,
    EXPANSION_COST,
    MIN_TREASURY_CONCENTRATION,
    POPULATION_ATTACK_FAILURE_LOSS,
    POPULATION_ATTACK_SUCCESS_LOSS,
    POPULATION_EXPANSION_TRANSFER_MIN,
    POPULATION_EXPANSION_TRANSFER_RATIO,
    REGIME_CLAIMANT_ATTACK_SCORE_BONUS,
    REGIME_CLAIMANT_ATTACK_STRENGTH_BONUS,
    REGIME_SPLIT_ATTACK_SCORE_BONUS,
    REGIME_SPLIT_ATTACK_STRENGTH_BONUS,
    REBEL_PROTO_TREASURY_CONCENTRATION_FACTOR,
    REBEL_REABSORPTION_UNREST,
    TREASURY_CONCENTRATION_REGION_FACTOR,
)
from src.doctrine import get_faction_region_alignment
from src.region_state import (
    get_region_attack_projection_modifier,
    get_region_core_defense_bonus,
    get_region_core_status,
)
from src.resource_economy import (
    apply_region_resource_damage,
    get_region_taxable_value,
    update_faction_resource_economy,
)
from src.heartland import (
    apply_region_population_loss,
    factions_have_same_ethnicity_regime_tension,
    faction_has_ethnic_claim,
    get_region_dominant_ethnicity,
    get_rebel_reclaim_bonus,
    handle_region_owner_change,
    set_region_unrest,
    transfer_region_population,
)
from src.models import Event
from src.resources import (
    CAPACITY_CONSTRUCTION,
    CAPACITY_FOOD_SECURITY,
    CAPACITY_METAL,
    CAPACITY_MOBILITY,
    CAPACITY_TAXABLE_VALUE,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_LIVESTOCK,
    RESOURCE_SALT,
    RESOURCE_STONE,
    RESOURCE_TIMBER,
    RESOURCE_TEXTILES,
    RESOURCE_WILD_FOOD,
    format_resource_map,
)
from src.region_naming import assign_region_founding_name, format_region_reference
from src.terrain import get_terrain_profile
from src.visibility import faction_knows_region


TRADE_WARFARE_MAX_PRESSURE = 1.0
TRADE_BLOCKADE_MAX_STRENGTH = 1.0
TRADE_WARFARE_SUCCESS_TURNS = 3
TRADE_WARFARE_FAILURE_TURNS = 2
TRADE_BLOCKADE_SUCCESS_TURNS = 3
TRADE_BLOCKADE_FAILURE_TURNS = 2


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def get_expandable_regions(faction_name, world):
    """Returns a list of Regions the given faction is capable of expanding into."""

    expandable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner != faction_name or not faction_knows_region(world, faction_name, region.name):
            continue
        for neighbor_name in region.neighbors:
            if not faction_knows_region(world, faction_name, neighbor_name):
                continue
            neighbor = world.regions[neighbor_name]
            if neighbor.owner is None:
                expandable_regions.add(neighbor_name)

    return sorted(expandable_regions)


def get_attackable_regions(faction_name, world):
    """Returns adjacent enemy-owned regions the faction can attack."""

    attackable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner != faction_name or not faction_knows_region(world, faction_name, region.name):
            continue

        for neighbor_name in region.neighbors:
            if not faction_knows_region(world, faction_name, neighbor_name):
                continue
            neighbor = world.regions[neighbor_name]
            if (
                neighbor.owner is not None
                and neighbor.owner != faction_name
                and get_relationship_status(world, faction_name, neighbor.owner)
                not in {"alliance", "truce"}
            ):
                attackable_regions.add(neighbor_name)

    return sorted(attackable_regions)


def _get_region_resource_interest(region, faction_name, world) -> int:
    faction = world.factions.get(faction_name)
    if faction is None:
        return 0
    shortages = faction.resource_shortages
    bonus = 0
    if shortages.get(CAPACITY_FOOD_SECURITY, 0.0) > 0:
        bonus += int(
            round(
                region.resource_suitability.get(RESOURCE_GRAIN, 0.0) * 4
                + region.resource_suitability.get(RESOURCE_LIVESTOCK, 0.0) * 4
                + region.resource_wild_endowments.get("wild_food", 0.0) * 2
            )
        )
    if shortages.get(CAPACITY_MOBILITY, 0.0) > 0:
        bonus += int(round(region.resource_suitability.get(RESOURCE_HORSES, 0.0) * 4))
    if shortages.get(CAPACITY_METAL, 0.0) > 0:
        bonus += int(round(region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0) * 5))
    if shortages.get(CAPACITY_CONSTRUCTION, 0.0) > 0:
        bonus += int(
            round(
                region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0) * 2
                + region.resource_wild_endowments.get(RESOURCE_TIMBER, 0.0) * 2
            )
        )
    if shortages.get(CAPACITY_TAXABLE_VALUE, 0.0) > 0:
        bonus += int(
            round(
                region.resource_fixed_endowments.get(RESOURCE_SALT, 0.0) * 3
                + region.resource_suitability.get(RESOURCE_TEXTILES, 0.0) * 3
            )
        )
    bonus += int(round(region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0) * 2))
    return bonus


def _get_region_strategic_value(region, world) -> float:
    return round(get_region_taxable_value(region, world), 2)


def _get_region_corridor_pressure(region) -> float:
    isolation = float(region.resource_isolation_factor or 0.0)
    bottleneck_gap = max(0.0, 0.82 - float(region.resource_route_bottleneck or 0.0))
    depth_pressure = min(0.35, (region.resource_route_depth or 0) * 0.05)
    return round(isolation + bottleneck_gap + depth_pressure, 3)


def _faction_has_established_resource_source(
    faction_name: str,
    resource_name: str,
    world,
    *,
    exclude_region_name: str | None = None,
) -> bool:
    for region in world.regions.values():
        if region.owner != faction_name:
            continue
        if exclude_region_name is not None and region.name == exclude_region_name:
            continue
        if region.resource_established.get(resource_name, 0.0) > 0.2:
            return True
    return False


def _get_owned_path_length(
    faction_name: str,
    source_region_name: str,
    target_region_name: str,
    world,
) -> int | None:
    if source_region_name == target_region_name:
        return 0
    queue = [(source_region_name, 0)]
    seen = {source_region_name}
    while queue:
        region_name, distance = queue.pop(0)
        for neighbor_name in world.regions[region_name].neighbors:
            if neighbor_name in seen:
                continue
            seen.add(neighbor_name)
            neighbor = world.regions[neighbor_name]
            if neighbor_name == target_region_name and neighbor.owner == faction_name:
                return distance + 1
            if neighbor.owner != faction_name:
                continue
            queue.append((neighbor_name, distance + 1))
    return None


def _get_best_resource_source_region(
    faction_name: str,
    target_region_name: str,
    resource_name: str,
    world,
):
    best = None
    for region in world.regions.values():
        if region.owner != faction_name:
            continue
        if region.name == target_region_name:
            continue
        if region.resource_established.get(resource_name, 0.0) <= 0.2:
            continue
        path_length = _get_owned_path_length(
            faction_name,
            region.name,
            target_region_name,
            world,
        )
        if path_length is None:
            continue
        candidate = (
            path_length,
            -region.resource_established.get(resource_name, 0.0),
            region.name,
        )
        if best is None or candidate < best[0]:
            best = (candidate, region)
    return None if best is None else best[1]


def _get_development_project_options(faction_name: str, region, world) -> list[dict[str, float | str]]:
    faction = world.factions[faction_name]
    shortages = faction.resource_shortages
    options: list[dict[str, float | str]] = []
    corridor_pressure = _get_region_corridor_pressure(region)
    route_bottleneck = float(region.resource_route_bottleneck or 0.0)
    local_storage_gap = max(0.0, region.food_produced - region.food_storage_capacity)
    local_food_waste = region.food_overflow + region.food_spoilage
    local_deficit_pressure = region.food_deficit
    raw_total_output = sum((region.resource_output or {}).values())
    retained_total_output = sum((region.resource_retained_output or {}).values())
    routed_total_output = sum((region.resource_routed_output or region.resource_effective_output or {}).values())
    trade_throughput = float(region.trade_throughput or 0.0)
    trade_value_bonus = float(region.trade_value_bonus or 0.0)
    trade_import_reliance = float(region.trade_import_reliance or 0.0)
    trade_disruption = float(region.trade_disruption_risk or 0.0)
    trade_foreign_flow = float(region.trade_foreign_flow or 0.0)
    trade_foreign_value = float(region.trade_foreign_value or 0.0)
    trade_gateway_role = region.trade_gateway_role or "none"
    trade_children = int(region.trade_route_children or 0)
    trade_role = region.trade_route_role or "local"
    retained_loss = max(0.0, raw_total_output - retained_total_output)
    routed_loss = max(0.0, retained_total_output - routed_total_output)
    monetization_gap = max(0.0, routed_total_output - float(region.resource_monetized_value or 0.0))
    extractive_pressure = (
        region.resource_output.get(RESOURCE_COPPER, 0.0)
        + region.resource_output.get(RESOURCE_STONE, 0.0)
        + region.resource_output.get(RESOURCE_SALT, 0.0)
        + region.resource_output.get(RESOURCE_TIMBER, 0.0)
    )
    commercial_pressure = (
        region.resource_output.get(RESOURCE_SALT, 0.0)
        + region.resource_output.get(RESOURCE_TEXTILES, 0.0)
    )
    has_material_site = any(
        level > 0
        for level in (
            region.logging_camp_level,
            region.copper_mine_level,
            region.stone_quarry_level,
            region.extractive_level,
        )
    ) or region.resource_fixed_endowments.get(RESOURCE_SALT, 0.0) > 0.25

    grain_suitability = region.resource_suitability.get(RESOURCE_GRAIN, 0.0)
    grain_established = region.resource_established.get(RESOURCE_GRAIN, 0.0)
    grain_source = _get_best_resource_source_region(
        faction_name,
        region.name,
        RESOURCE_GRAIN,
        world,
    )
    if (
        grain_suitability >= 0.35
        and grain_established < max(0.28, grain_suitability - 0.08)
        and grain_source is not None
    ):
        source_path = _get_owned_path_length(faction_name, grain_source.name, region.name, world) or 0
        options.append({
            "project_type": "introduce_grain",
            "score": 5.0 + (grain_suitability * 4.0) + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 2.8) - (source_path * 0.35),
            "resource_focus": RESOURCE_GRAIN,
            "source_region": grain_source.name,
        })
    if grain_established > 0 and region.irrigation_level < 1.8:
        options.append({
            "project_type": (
                "build_irrigation"
                if region.irrigation_level <= 0
                else "expand_irrigation"
            ),
            "score": (
                3.8
                + (grain_established * 3.0)
                + (region.food_deficit * 1.2)
                + (local_storage_gap * 0.8)
                + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 2.0)
                + (0.5 if region.irrigation_level <= 0 else region.irrigation_level * 0.35)
            ),
            "resource_focus": RESOURCE_GRAIN,
        })
    if region.irrigation_level > 0.4 and region.agriculture_level < 1.4:
        options.append({
            "project_type": "improve_agriculture",
            "score": 2.7 + (grain_established * 2.4) + (region.irrigation_level * 1.3),
            "resource_focus": RESOURCE_GRAIN,
        })
    if (
        region.granary_level < 1.8
        and (
            grain_established > 0
            or region.agriculture_level > 0.2
            or region.food_produced > 0.6
        )
    ):
        options.append({
            "project_type": "build_granary",
            "score": (
                3.2
                + (grain_established * 2.6)
                + (region.agriculture_level * 1.8)
                + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 2.4)
                + (local_storage_gap * 1.8)
                + (local_food_waste * 1.5)
                + (local_deficit_pressure * 0.9)
                + (region.infrastructure_level * 0.4)
                + (0.35 if region.settlement_level in {"town", "city"} else 0.0)
            ),
            "resource_focus": RESOURCE_GRAIN,
        })

    livestock_suitability = region.resource_suitability.get(RESOURCE_LIVESTOCK, 0.0)
    livestock_established = region.resource_established.get(RESOURCE_LIVESTOCK, 0.0)
    livestock_source = _get_best_resource_source_region(
        faction_name,
        region.name,
        RESOURCE_LIVESTOCK,
        world,
    )
    if (
        livestock_suitability >= 0.4
        and livestock_established < max(0.22, livestock_suitability - 0.1)
        and livestock_source is not None
    ):
        source_path = _get_owned_path_length(faction_name, livestock_source.name, region.name, world) or 0
        options.append({
            "project_type": "introduce_livestock",
            "score": (
                4.6
                + (livestock_suitability * 3.8)
                + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 2.4)
                - (source_path * 0.35)
            ),
            "resource_focus": RESOURCE_LIVESTOCK,
            "source_region": livestock_source.name,
        })

    horse_suitability = region.resource_suitability.get(RESOURCE_HORSES, 0.0)
    horse_established = region.resource_established.get(RESOURCE_HORSES, 0.0)
    horse_source = _get_best_resource_source_region(
        faction_name,
        region.name,
        RESOURCE_HORSES,
        world,
    )
    if (
        horse_suitability >= 0.55
        and horse_established < max(0.16, horse_suitability - 0.1)
        and horse_source is not None
    ):
        source_path = _get_owned_path_length(faction_name, horse_source.name, region.name, world) or 0
        options.append({
            "project_type": "introduce_horses",
            "score": 4.5 + (horse_suitability * 3.5) + (shortages.get(CAPACITY_MOBILITY, 0.0) * 2.5) - (source_path * 0.45),
            "resource_focus": RESOURCE_HORSES,
            "source_region": horse_source.name,
        })
    if (horse_established > 0 or livestock_established > 0) and region.pasture_level < 1.8:
        pastoral_output = horse_established + (livestock_established * 0.85)
        options.append({
            "project_type": (
                "establish_pasture"
                if region.pasture_level <= 0
                else "expand_pasture"
            ),
            "score": (
                3.2
                + (pastoral_output * 2.6)
                + (shortages.get(CAPACITY_MOBILITY, 0.0) * 1.9)
                + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 0.8)
                + (region.infrastructure_level * 0.25)
                + (0.45 if region.pasture_level <= 0 else region.pasture_level * 0.3)
            ),
            "resource_focus": (
                RESOURCE_LIVESTOCK
                if livestock_established >= horse_established and shortages.get(CAPACITY_FOOD_SECURITY, 0.0) > shortages.get(CAPACITY_MOBILITY, 0.0)
                else RESOURCE_HORSES
            ),
        })
    if region.pasture_level > 0.4 and region.pastoral_level < 1.4 and (horse_established > 0 or livestock_established > 0):
        options.append({
            "project_type": "improve_pastoralism",
            "score": 2.4 + ((horse_established + livestock_established) * 1.8) + (region.pasture_level * 1.1),
            "resource_focus": (
                RESOURCE_LIVESTOCK
                if livestock_established >= horse_established
                else RESOURCE_HORSES
            ),
        })

    timber_endowment = region.resource_wild_endowments.get(RESOURCE_TIMBER, 0.0)
    if timber_endowment > 0.25 and region.logging_camp_level < 1.8:
        construction_pressure = shortages.get(CAPACITY_CONSTRUCTION, 0.0)
        options.append({
            "project_type": (
                "build_logging_camp"
                if region.logging_camp_level <= 0
                else "expand_logging_camp"
            ),
            "score": (
                3.0
                + (timber_endowment * 3.8)
                + (construction_pressure * 2.0)
                + (corridor_pressure * 0.8)
                + (0.45 if region.logging_camp_level <= 0 else region.logging_camp_level * 0.28)
            ),
            "resource_focus": RESOURCE_TIMBER,
        })

    if (
        region.storehouse_level < 1.8
        and has_material_site
        and (
            extractive_pressure > 0.55
            or retained_loss > 0.35
            or routed_loss > 0.45
            or local_food_waste > 0.18
        )
    ):
        options.append({
            "project_type": (
                "build_storehouse"
                if region.storehouse_level <= 0
                else "expand_storehouse"
            ),
            "score": (
                2.9
                + (extractive_pressure * 1.8)
                + (retained_loss * 2.6)
                + (routed_loss * 2.3)
                + (local_food_waste * 0.9)
                + (corridor_pressure * 1.2)
                + (trade_throughput * 0.18)
                + (trade_foreign_flow * 0.25)
                + (0.35 if region.storehouse_level <= 0 else region.storehouse_level * 0.28)
            ),
            "resource_focus": "storage",
        })

    copper_endowment = region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0)
    if copper_endowment > 0 and region.copper_mine_level < 1.8:
        options.append({
            "project_type": (
                "build_copper_mine"
                if region.copper_mine_level <= 0
                else "expand_copper_mine"
            ),
            "score": (
                4.1
                + (copper_endowment * 4.4)
                + (shortages.get(CAPACITY_METAL, 0.0) * 2.3)
                + (region.infrastructure_level * 0.35)
                + (0.8 if region.copper_mine_level <= 0 else region.copper_mine_level * 0.45)
            ),
            "resource_focus": RESOURCE_COPPER,
        })

    stone_endowment = region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0)
    if stone_endowment > 0 and region.stone_quarry_level < 1.8:
        construction_pressure = shortages.get(CAPACITY_CONSTRUCTION, 0.0)
        options.append({
            "project_type": (
                "build_stone_quarry"
                if region.stone_quarry_level <= 0
                else "expand_stone_quarry"
            ),
            "score": (
                3.5
                + (stone_endowment * 3.6)
                + (construction_pressure * 2.1)
                + (shortages.get(CAPACITY_METAL, 0.0) * 0.5)
                + (region.infrastructure_level * 0.28)
                + (0.6 if region.stone_quarry_level <= 0 else region.stone_quarry_level * 0.35)
            ),
            "resource_focus": RESOURCE_STONE,
        })

    if region.road_level < 1.8 and (
        corridor_pressure >= 0.12
        or route_bottleneck < 0.84
        or get_region_core_status(region) == "frontier"
    ):
        logistics_pressure = (
            shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 0.25
            + shortages.get(CAPACITY_METAL, 0.0) * 0.25
            + shortages.get(CAPACITY_MOBILITY, 0.0) * 0.35
            + shortages.get(CAPACITY_CONSTRUCTION, 0.0) * 0.2
        )
        options.append({
            "project_type": (
                "build_road_station"
                if region.road_level <= 0
                else "improve_road"
            ),
            "score": (
                2.8
                + (corridor_pressure * 5.0)
                + (max(0.0, 0.86 - route_bottleneck) * 3.2)
                + (trade_throughput * 0.34)
                + (trade_disruption * 2.4)
                + (trade_foreign_flow * 0.3)
                + (trade_children * 0.45)
                + (0.65 if trade_role == "corridor" else 0.0)
                + (0.6 if trade_gateway_role != "none" else 0.0)
                + logistics_pressure
                + (0.4 if region.road_level <= 0 else region.road_level * 0.3)
            ),
            "resource_focus": "mixed",
        })

    market_eligible = (
        region.settlement_level in {"town", "city"}
        or region.infrastructure_level >= 0.9
        or region.storehouse_level >= 0.6
    )
    if region.market_level < 1.8 and market_eligible and routed_total_output > 0.6:
        market_pressure = shortages.get(CAPACITY_TAXABLE_VALUE, 0.0) * 0.28
        options.append({
            "project_type": (
                "build_market"
                if region.market_level <= 0
                else "expand_market"
            ),
            "score": (
                3.1
                + (routed_total_output * 1.4)
                + (commercial_pressure * 1.1)
                + (monetization_gap * 2.2)
                + (trade_value_bonus * 0.85)
                + (trade_foreign_value * 1.15)
                + (trade_import_reliance * 2.2)
                + (trade_throughput * 0.2)
                + (0.5 if trade_role == "hub" else 0.3 if trade_role == "corridor" else 0.0)
                + (0.7 if trade_gateway_role == "sea_gateway" else 0.45 if trade_gateway_role != "none" else 0.0)
                + (get_region_taxable_value(region, world) * 0.42)
                + (max(0.0, 0.8 - route_bottleneck) * 1.6)
                + market_pressure
                + (0.4 if region.market_level <= 0 else region.market_level * 0.32)
            ),
            "resource_focus": "trade",
        })

    if region.infrastructure_level < 1.6:
        infrastructure_shortage_bonus = (
            shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 0.25
            + shortages.get(CAPACITY_METAL, 0.0) * 0.45
            + shortages.get(CAPACITY_MOBILITY, 0.0) * 0.2
        )
        options.append({
            "project_type": "improve_infrastructure",
            "score": (
                1.5
                + (get_region_taxable_value(region, world) * 0.48)
                + (corridor_pressure * 4.4)
                + (max(0.0, 0.78 - route_bottleneck) * 3.0)
                + (trade_throughput * 0.24)
                + (trade_disruption * 2.0)
                + (trade_foreign_flow * 0.18)
                + (trade_foreign_value * 0.45)
                + infrastructure_shortage_bonus
                - (region.road_level * 0.35)
            ),
            "resource_focus": "mixed",
        })

    return options


def get_development_target_score_components(region_name: str, faction_name: str, world) -> dict[str, float | str]:
    region = world.regions[region_name]
    options = _get_development_project_options(faction_name, region, world)
    if not options:
        return {
            "score": 0.0,
            "project_type": "none",
            "resource_focus": "",
            "resource_profile": "None",
        }
    best_option = max(
        options,
        key=lambda item: (float(item["score"]), str(item["project_type"])),
    )
    return {
        "score": round(float(best_option["score"]), 3),
        "project_type": str(best_option["project_type"]),
        "resource_focus": str(best_option["resource_focus"]),
        "source_region": str(best_option.get("source_region", "")),
        "resource_profile": format_resource_map(region.resource_output or region.resource_fixed_endowments, limit=3),
    }


def get_invest_target_score_components(region_name: str, faction_name: str, world) -> dict[str, float | str]:
    """Backward-compatible alias for development project scoring."""
    return get_development_target_score_components(region_name, faction_name, world)


def get_owned_region_count(faction_name, world):
    """Returns the number of regions currently owned by the faction."""

    return sum(
        1
        for region in world.regions.values()
        if region.owner == faction_name
    )


def _is_trade_port_target(region) -> bool:
    return (
        "coast" in region.terrain_tags
        and (
            region.trade_gateway_role == "sea_gateway"
            or region.trade_route_mode == "sea"
            or region.market_level >= 0.2
            or region.storehouse_level >= 0.25
            or region.infrastructure_level >= 0.45
            or region.settlement_level in {"town", "city"}
        )
    )


def _get_active_war_target_bonus(
    faction_name: str,
    defender_name: str,
    region,
    world,
) -> tuple[int, str | None]:
    war = world.wars.get(tuple(sorted((faction_name, defender_name))))
    if war is None or not war.active:
        return (0, None)

    objective = war.objective_type or "territorial_conquest"
    bonus = 0
    if war.target_region and region.name == war.target_region:
        bonus += 8

    if objective == "trade_supremacy":
        bonus += (
            5
            if region.trade_gateway_role != "none"
            else 3 if region.trade_route_role in {"hub", "corridor"} else 0
        )
    elif objective in {"claim_reclamation", "claimant_restoration", "regime_change"}:
        if region.core_status in {"homeland", "core"}:
            bonus += 4
    elif objective == "subjugation":
        bonus += 4 if region.core_status == "homeland" else 2 if region.core_status == "core" else 0
    elif objective == "punitive_raid":
        bonus += 3 if get_region_taxable_value(region, world) >= 4 else 1

    return (bonus, objective)


def _choose_war_objective(
    faction_name: str,
    defender_name: str,
    region,
    score_components: dict[str, float | int | str | None],
    world,
) -> tuple[str, str]:
    attacker = world.factions[faction_name]
    defender = world.factions[defender_name]
    objective_type = "territorial_conquest"
    objective_label = "territorial conquest"

    if score_components.get("regime_target_reason") == "civil_war_claim":
        return ("claimant_restoration", "claimant restoration")
    if score_components.get("regime_target_bonus", 0) and score_components.get("regime_target_reason") == "regime_split":
        return ("regime_change", "regime change")
    if int(score_components.get("ethnic_claim_bonus", 0) or 0) > 0:
        return ("claim_reclamation", "claim reclamation")
    if (
        (region.trade_gateway_role or "none") != "none"
        or float(score_components.get("foreign_gateway_bonus", 0) or 0) >= 4
        or float(score_components.get("trade_chokepoint_bonus", 0) or 0) >= 7
    ):
        return ("trade_supremacy", "trade supremacy")

    attacker_power = (
        float(attacker.treasury)
        + (int(score_components.get("attacker_region_count", 0) or 0) * 3.0)
    )
    defender_power = max(
        1.0,
        float(defender.treasury)
        + (int(score_components.get("defender_region_count", 0) or 0) * 3.0),
    )
    if (
        attacker_power / defender_power >= 1.6
        and attacker.polity_tier in {"chiefdom", "state"}
        and attacker.government_form in {"leader", "monarchy", "oligarchy", "council", "republic"}
    ):
        return ("subjugation", "subjugation")

    if (
        str(score_components.get("core_status") or "frontier") in {"core", "homeland"}
        or float(score_components.get("target_taxable_value", 0.0) or 0.0) >= 4.5
    ):
        return (objective_type, objective_label)
    return ("punitive_raid", "punitive raid")


def _apply_trade_warfare_pressure(region, *, succeeded: bool) -> dict[str, float | bool | str]:
    trade_role = region.trade_route_role or "local"
    gateway_role = region.trade_gateway_role or "none"
    throughput = float(region.trade_throughput or 0.0)
    transit_flow = float(region.trade_transit_flow or 0.0)
    foreign_flow = float(region.trade_foreign_flow or 0.0)
    foreign_value = float(region.trade_foreign_value or 0.0)
    served_regions = int(region.trade_served_regions or 0)
    value_denied_before = float(region.trade_value_denied or 0.0)

    pressure_gain = 0.06
    pressure_gain += min(0.2, throughput * 0.018)
    pressure_gain += min(0.14, transit_flow * 0.045)
    pressure_gain += min(0.1, foreign_flow * 0.04)
    pressure_gain += min(0.08, foreign_value * 0.05)
    pressure_gain += min(0.08, served_regions * 0.015)
    if trade_role == "corridor":
        pressure_gain += 0.12
    elif trade_role == "hub":
        pressure_gain += 0.09
    elif trade_role == "terminal":
        pressure_gain += 0.04
    if gateway_role == "border_gateway":
        pressure_gain += 0.08
    elif gateway_role == "sea_gateway":
        pressure_gain += 0.14
    if succeeded:
        pressure_gain += 0.08
    else:
        pressure_gain += 0.03

    blockade_gain = 0.0
    if gateway_role == "sea_gateway" or _is_trade_port_target(region):
        blockade_gain = 0.12 + min(0.18, throughput * 0.02) + min(0.1, foreign_flow * 0.05)
        if gateway_role == "sea_gateway":
            blockade_gain += 0.14
        blockade_gain += 0.1 if succeeded else 0.04

    pressure_after = _clamp(
        float(region.trade_warfare_pressure or 0.0) + pressure_gain,
        0.0,
        TRADE_WARFARE_MAX_PRESSURE,
    )
    blockade_after = _clamp(
        float(region.trade_blockade_strength or 0.0) + blockade_gain,
        0.0,
        TRADE_BLOCKADE_MAX_STRENGTH,
    )
    region.trade_warfare_pressure = round(pressure_after, 3)
    region.trade_warfare_turns = max(
        int(region.trade_warfare_turns or 0),
        TRADE_WARFARE_SUCCESS_TURNS if succeeded else TRADE_WARFARE_FAILURE_TURNS,
    )
    if blockade_gain > 0.0:
        region.trade_blockade_strength = round(blockade_after, 3)
        region.trade_blockade_turns = max(
            int(region.trade_blockade_turns or 0),
            TRADE_BLOCKADE_SUCCESS_TURNS if succeeded else TRADE_BLOCKADE_FAILURE_TURNS,
        )

    trade_value_loss = max(
        value_denied_before,
        (
            throughput * pressure_gain * 0.18
            + foreign_value * pressure_gain * 0.7
            + blockade_gain * max(0.0, throughput + foreign_flow) * 0.16
        ),
    )
    trade_value_loss = round(max(0.0, trade_value_loss), 3)
    region.trade_value_denied = round(max(float(region.trade_value_denied or 0.0), trade_value_loss), 3)

    return {
        "trade_warfare_hit": pressure_gain > 0.08,
        "trade_warfare_pressure_added": round(pressure_gain, 3),
        "trade_warfare_pressure": round(pressure_after, 3),
        "trade_blockade_added": round(blockade_gain, 3),
        "trade_blockade_strength": round(blockade_after, 3),
        "trade_warfare_target_role": trade_role,
        "trade_gateway_role": gateway_role,
        "trade_value_denied": trade_value_loss,
        "port_blockaded": blockade_after >= 0.42,
    }


def get_treasury_concentration_multiplier(region_count):
    """Returns the share of treasury a faction can focus on a single front."""

    if region_count <= 1:
        return 1.0

    multiplier = 1.0 / (
        1.0 + (TREASURY_CONCENTRATION_REGION_FACTOR * (region_count - 1))
    )
    return max(MIN_TREASURY_CONCENTRATION, round(multiplier, 3))


def get_attack_target_score_components(region_name, faction_name, world):
    """Returns a simple attack score and combat stats for an enemy region."""

    region = world.regions[region_name]
    terrain_profile = get_terrain_profile(region)
    doctrine_alignment = get_faction_region_alignment(
        world.factions[faction_name],
        region.terrain_tags,
        region.climate,
    )
    region_core_status = get_region_core_status(region)
    core_defense_bonus = get_region_core_defense_bonus(region)
    defender_name = region.owner
    attacker_region_count = get_owned_region_count(faction_name, world)
    defender_region_count = get_owned_region_count(defender_name, world)
    attacker_treasury_multiplier = get_treasury_concentration_multiplier(attacker_region_count)
    defender_treasury_multiplier = get_treasury_concentration_multiplier(defender_region_count)
    attacker_faction = world.factions[faction_name]
    if attacker_faction.is_rebel and attacker_faction.proto_state:
        attacker_treasury_multiplier *= REBEL_PROTO_TREASURY_CONCENTRATION_FACTOR
    defender_faction_state = world.factions[defender_name]
    if defender_faction_state.is_rebel and defender_faction_state.proto_state:
        defender_treasury_multiplier *= REBEL_PROTO_TREASURY_CONCENTRATION_FACTOR
    attacker_deployable_treasury = int(
        round(attacker_faction.treasury * attacker_treasury_multiplier)
    )
    defender_deployable_treasury = int(
        round(defender_faction_state.treasury * defender_treasury_multiplier)
    )
    staging_regions = [
        world.regions[neighbor_name]
        for neighbor_name in region.neighbors
        if world.regions[neighbor_name].owner == faction_name
    ]
    staging_resources = max(
        (_get_region_strategic_value(staging_region, world) for staging_region in staging_regions),
        default=0.0,
    )
    staging_projection = max(
        (
            _get_region_strategic_value(staging_region, world)
            + get_region_attack_projection_modifier(
                staging_region,
                world=world,
                faction_name=faction_name,
            )
            for staging_region in staging_regions
        ),
        default=0,
    )
    attacker_strength = (
        attacker_deployable_treasury
        + staging_projection
        + doctrine_alignment["combat_modifier"]
    )
    rebel_reclaim_bonus = get_rebel_reclaim_bonus(
        faction_name,
        defender_name,
        world,
    )
    attacker_strength += rebel_reclaim_bonus
    ethnic_claim_bonus = 0
    claim_ethnicity = None
    if faction_has_ethnic_claim(world, region, faction_name):
        attacker_primary_ethnicity = world.factions[faction_name].primary_ethnicity
        defender_primary_ethnicity = defender_faction_state.primary_ethnicity
        if attacker_primary_ethnicity and attacker_primary_ethnicity != defender_primary_ethnicity:
            ethnic_claim_bonus = DIPLOMACY_ETHNIC_CLAIM_ATTACK_BONUS
            claim_ethnicity = attacker_primary_ethnicity
    attacker_strength += ethnic_claim_bonus
    regime_target_bonus = 0
    regime_target_score_bonus = 0
    regime_target_reason = None
    target_dominant_ethnicity = get_region_dominant_ethnicity(region)
    if (
        target_dominant_ethnicity is not None
        and target_dominant_ethnicity == attacker_faction.primary_ethnicity
        and factions_have_same_ethnicity_regime_tension(world, faction_name, defender_name)
    ):
        if (
            (attacker_faction.rebel_conflict_type == "civil_war" and attacker_faction.origin_faction == defender_name and not attacker_faction.proto_state)
            or (defender_faction_state.rebel_conflict_type == "civil_war" and defender_faction_state.origin_faction == faction_name and not defender_faction_state.proto_state)
        ):
            regime_target_bonus = REGIME_CLAIMANT_ATTACK_STRENGTH_BONUS
            regime_target_score_bonus = REGIME_CLAIMANT_ATTACK_SCORE_BONUS
            regime_target_reason = "civil_war_claim"
        elif attacker_faction.government_form != defender_faction_state.government_form:
            regime_target_bonus = REGIME_SPLIT_ATTACK_STRENGTH_BONUS
            regime_target_score_bonus = REGIME_SPLIT_ATTACK_SCORE_BONUS
            regime_target_reason = "regime_split"
        if region_core_status == "homeland":
            regime_target_bonus += 1
            regime_target_score_bonus += 3
        elif region_core_status == "core":
            regime_target_score_bonus += 2
    attacker_strength += regime_target_bonus
    diplomacy_attack_modifier, diplomacy_status = get_attack_diplomacy_modifier(
        world,
        faction_name,
        defender_name,
    )
    resource_need_bonus = _get_region_resource_interest(region, faction_name, world)
    target_value = _get_region_strategic_value(region, world)
    trade_chokepoint_bonus = (
        min(10, int(round(float(region.trade_throughput or 0.0) * 0.18)))
        + min(6, int(round(float(region.trade_transit_flow or 0.0) * 0.45)))
        + min(5, int(round(float(region.trade_hub_value or 0.0) * 0.3)))
        + (4 if region.trade_route_role == "corridor" else 2 if region.trade_route_role == "hub" else 0)
        + min(4, int(region.trade_served_regions or 0))
    )
    foreign_gateway_bonus = (
        min(8, int(round(float(region.trade_foreign_flow or 0.0) * 0.45)))
        + min(6, int(round(float(region.trade_foreign_value or 0.0) * 1.2)))
        + (5 if region.trade_gateway_role == "sea_gateway" else 3 if region.trade_gateway_role == "border_gateway" else 0)
    )
    active_war_bonus, active_war_objective = _get_active_war_target_bonus(
        faction_name,
        defender_name,
        region,
        world,
    )
    defender_strength = (
        defender_deployable_treasury
        + target_value
        + terrain_profile["defense_modifier"]
        + core_defense_bonus
    )
    success_chance = 0.5 + (
        (attacker_strength - defender_strength) * ATTACK_SUCCESS_STRENGTH_FACTOR
    )
    success_chance = max(ATTACK_SUCCESS_MIN, min(ATTACK_SUCCESS_MAX, success_chance))
    score = (
        int(success_chance * 100)
        + int(round(target_value * 3))
        + terrain_profile["economic_modifier"]
        + doctrine_alignment["economic_modifier"]
        + diplomacy_attack_modifier
        + regime_target_score_bonus
        + resource_need_bonus
        + trade_chokepoint_bonus
        + foreign_gateway_bonus
        + active_war_bonus
    )

    return {
        "defender": defender_name,
        "target_resources": region.resources,
        "target_taxable_value": target_value,
        "attacker_region_count": attacker_region_count,
        "defender_region_count": defender_region_count,
        "attacker_treasury_multiplier": round(attacker_treasury_multiplier, 3),
        "defender_treasury_multiplier": round(defender_treasury_multiplier, 3),
        "attacker_deployable_treasury": attacker_deployable_treasury,
        "defender_deployable_treasury": defender_deployable_treasury,
        "staging_resources": staging_resources,
        "staging_projection": staging_projection,
        "attacker_strength": attacker_strength,
        "defender_strength": defender_strength,
        "terrain_tags": terrain_profile["terrain_tags"],
        "terrain_label": terrain_profile["terrain_label"],
        "defense_modifier": terrain_profile["defense_modifier"],
        "economic_modifier": terrain_profile["economic_modifier"],
        "doctrine_combat_modifier": doctrine_alignment["combat_modifier"],
        "doctrine_economic_modifier": doctrine_alignment["economic_modifier"],
        "rebel_reclaim_bonus": rebel_reclaim_bonus,
        "ethnic_claim_bonus": ethnic_claim_bonus,
        "claim_ethnicity": claim_ethnicity,
        "regime_target_bonus": regime_target_bonus,
        "regime_target_score_bonus": regime_target_score_bonus,
        "regime_target_reason": regime_target_reason,
        "diplomacy_status": diplomacy_status,
        "diplomacy_attack_modifier": diplomacy_attack_modifier,
        "resource_need_bonus": resource_need_bonus,
        "trade_chokepoint_bonus": trade_chokepoint_bonus,
        "foreign_gateway_bonus": foreign_gateway_bonus,
        "active_war_bonus": active_war_bonus,
        "active_war_objective": active_war_objective,
        "terrain_affinity": doctrine_alignment["average_affinity"],
        "core_status": region_core_status,
        "core_defense_bonus": core_defense_bonus,
        "success_chance": success_chance,
        "score": score,
    }


def get_expand_target_score_components(region_name, world, faction_name=None):
    """Returns the scoring breakdown for an expansion target."""

    region = world.regions[region_name]
    terrain_profile = get_terrain_profile(region)
    doctrine_alignment = None
    if faction_name is not None and faction_name in world.factions:
        doctrine_alignment = get_faction_region_alignment(
            world.factions[faction_name],
            region.terrain_tags,
            region.climate,
        )
    region_core_status = get_region_core_status(region)
    unclaimed_neighbors = 0

    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None:
            unclaimed_neighbors += 1

    resource_need_bonus = (
        _get_region_resource_interest(region, faction_name, world)
        if faction_name is not None
        else 0
    )
    resource_need_bonus = min(resource_need_bonus, 4)
    target_value = _get_region_strategic_value(region, world)
    score = (
        (target_value * 2)
        + len(region.neighbors)
        + (unclaimed_neighbors * 2)
        + terrain_profile["expansion_modifier"]
        + terrain_profile["economic_modifier"]
        + (doctrine_alignment["expansion_modifier"] if doctrine_alignment is not None else 0)
        + (doctrine_alignment["economic_modifier"] if doctrine_alignment is not None else 0)
        + resource_need_bonus
    )

    return {
        "resources": region.resources,
        "taxable_value": target_value,
        "neighbors": len(region.neighbors),
        "unclaimed_neighbors": unclaimed_neighbors,
        "terrain_tags": terrain_profile["terrain_tags"],
        "terrain_label": terrain_profile["terrain_label"],
        "terrain_expansion_modifier": terrain_profile["expansion_modifier"],
        "terrain_economic_modifier": terrain_profile["economic_modifier"],
        "doctrine_expansion_modifier": (
            doctrine_alignment["expansion_modifier"]
            if doctrine_alignment is not None
            else 0
        ),
        "doctrine_economic_modifier": (
            doctrine_alignment["economic_modifier"]
            if doctrine_alignment is not None
            else 0
        ),
        "terrain_affinity": (
            doctrine_alignment["average_affinity"]
            if doctrine_alignment is not None
            else 0.0
        ),
        "core_status": region_core_status,
        "resource_need_bonus": resource_need_bonus,
        "score": score,
    }


def get_expand_event_tags(score_components):
    """Returns interpretation tags for an expansion event."""
    tags = ["expansion", "territory_gain"]

    if score_components["score"] >= 13:
        tags.append("high_value")
    if score_components["unclaimed_neighbors"] >= 2:
        tags.append("frontier")
    if (
        score_components["neighbors"] >= 6
        or (
            score_components["neighbors"] >= 5
            and score_components["unclaimed_neighbors"] >= 3
        )
    ):
        tags.append("pivotal")
    if score_components["unclaimed_neighbors"] == 0:
        tags.append("consolidating")
    if score_components.get("taxable_value", score_components["resources"]) <= 1 and score_components["unclaimed_neighbors"] == 0:
        tags.append("risky")

    return tags


def get_owned_region_counts(world):
    """Returns current owned region counts by faction."""
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def get_faction_rankings(world):
    """Returns faction names sorted by a simple treasury/territory ranking."""
    owned_region_counts = get_owned_region_counts(world)

    return sorted(
        world.factions,
        key=lambda faction_name: (
            world.factions[faction_name].treasury,
            owned_region_counts[faction_name],
        ),
        reverse=True,
    )


def get_faction_rank(world, faction_name):
    """Returns one-based rank for a faction with shared ranks for ties."""
    owned_region_counts = get_owned_region_counts(world)
    faction_score = (
        world.factions[faction_name].treasury,
        owned_region_counts[faction_name],
    )

    better_factions = 0
    for other_faction_name in world.factions:
        other_score = (
            world.factions[other_faction_name].treasury,
            owned_region_counts[other_faction_name],
        )
        if other_score > faction_score:
            better_factions += 1

    return better_factions + 1


def get_faction_score(world, faction_name):
    """Returns the ranking tuple used for simple standings comparisons."""
    owned_region_counts = get_owned_region_counts(world)
    return (
        world.factions[faction_name].treasury,
        owned_region_counts[faction_name],
    )


def has_unique_lead(world, faction_name):
    """Returns whether the faction holds a unique lead by the current simple ranking."""
    faction_score = get_faction_score(world, faction_name)
    return sum(
        1
        for other_faction_name in world.factions
        if get_faction_score(world, other_faction_name) == faction_score
    ) == 1 and get_faction_rank(world, faction_name) == 1


def get_expand_strategic_role(score_components, expand_tags):
    """Returns a simple interpreted strategic role for an expansion."""
    if "pivotal" in expand_tags:
        return "junction"
    if "frontier" in expand_tags:
        return "frontier"
    if "consolidating" in expand_tags:
        return "consolidation"
    if "risky" in expand_tags:
        return "gamble"
    return "territorial_gain"


def get_importance_tier(score):
    """Returns a simple importance tier for an expansion score."""
    if score >= 18:
        return "major"
    if score >= 13:
        return "high"
    if score >= 9:
        return "moderate"
    return "minor"


def get_momentum_effect(rank_change, expand_tags, importance_tier, future_expansion_opened):
    """Returns a readable label for the expansion's momentum effect."""
    if rank_change is not None and rank_change > 0:
        return "surging"
    if (
        importance_tier == "major"
        and "frontier" in expand_tags
        and future_expansion_opened >= 4
    ):
        return "accelerating"
    if importance_tier == "high" and "consolidating" in expand_tags:
        return "stabilizing"
    if "risky" in expand_tags:
        return "fragile"
    return None


def get_summary_reason(score_components, strategic_role, importance_tier):
    """Returns a one-line reason for why the target mattered."""
    if strategic_role == "junction":
        return "it offered strong connectivity and multiple follow-up routes"
    if strategic_role == "frontier":
        return "it opened new directions for future expansion"
    if strategic_role == "consolidation":
        return "it secured nearby territory and tightened the faction's position"
    if importance_tier in {"major", "high"}:
        return "it combined strong income with strong positional value"
    return "it provided a straightforward territorial gain"


def _choose_expansion_population_source(faction_name, target_region_name, world):
    candidate_regions = [
        world.regions[neighbor_name]
        for neighbor_name in world.regions[target_region_name].neighbors
        if world.regions[neighbor_name].owner == faction_name
    ]
    if not candidate_regions:
        return None
    return max(
        candidate_regions,
        key=lambda region: (
            region.population,
            _get_region_strategic_value(region, world),
            region.name,
        ),
    )


def expand(faction_name, target_region_name, world):
    """Returns whether the Faction successfully expanded into the target Region."""

    if target_region_name not in world.regions:
        return False

    faction = world.factions[faction_name]

    if faction.treasury < EXPANSION_COST:
        return False

    if target_region_name not in get_expandable_regions(faction_name, world):
        return False

    treasury_before = faction.treasury
    rank_before = get_faction_rank(world, faction_name)
    owner_before = world.regions[target_region_name].owner
    score_components = get_expand_target_score_components(
        target_region_name,
        world,
        faction_name=faction_name,
    )
    expand_tags = get_expand_event_tags(score_components)
    strategic_role = get_expand_strategic_role(score_components, expand_tags)
    income_gain = score_components["taxable_value"]
    future_expansion_opened = score_components["unclaimed_neighbors"]
    importance_tier = get_importance_tier(score_components["score"])
    population_source = _choose_expansion_population_source(faction_name, target_region_name, world)
    source_region_name = population_source.name if population_source is not None else None
    source_population_before = population_source.population if population_source is not None else 0
    source_ethnicity_before = (
        get_region_dominant_ethnicity(population_source)
        if population_source is not None
        else None
    )
    target_population_before = world.regions[target_region_name].population
    faction.treasury -= EXPANSION_COST
    handle_region_owner_change(world.regions[target_region_name], faction_name)
    transferred_population = 0
    if population_source is not None and population_source.population > 0:
        transferred_population = max(
            POPULATION_EXPANSION_TRANSFER_MIN,
            int(round(population_source.population * POPULATION_EXPANSION_TRANSFER_RATIO)),
        )
        transferred_population = min(transferred_population, population_source.population)
        transferred_population = transfer_region_population(
            population_source,
            world.regions[target_region_name],
            transferred_population,
        )
    region_display_name = assign_region_founding_name(
        world,
        target_region_name,
        faction_name,
        is_homeland=False,
    )
    rank_after = get_faction_rank(world, faction_name)
    rank_change = rank_before - rank_after
    unique_lead_after = has_unique_lead(world, faction_name)
    is_turning_point = (
        (rank_change is not None and rank_change > 0)
        or (
            importance_tier == "major"
            and "pivotal" in expand_tags
            and future_expansion_opened >= 4
            and unique_lead_after
        )
    )
    momentum_effect = get_momentum_effect(
        rank_change,
        expand_tags,
        importance_tier,
        future_expansion_opened,
    )
    summary_reason = get_summary_reason(
        score_components,
        strategic_role,
        importance_tier,
    )
    narrative_tags = [tag for tag in expand_tags if tag not in {"expansion", "territory_gain"}]

    world.events.append(Event(
        turn=world.turn,
        type="expand",
        faction=faction_name,
        region=target_region_name,
        details={
            "cost": EXPANSION_COST,
            "resources": score_components["resources"],
            "taxable_value": score_components["taxable_value"],
            "neighbors": score_components["neighbors"],
            "unclaimed_neighbors": score_components["unclaimed_neighbors"],
            "score": score_components["score"],
            "terrain_tags": score_components["terrain_tags"],
            "terrain_label": score_components["terrain_label"],
            "terrain_expansion_modifier": score_components["terrain_expansion_modifier"],
            "terrain_economic_modifier": score_components["terrain_economic_modifier"],
            "doctrine_expansion_modifier": score_components["doctrine_expansion_modifier"],
            "doctrine_economic_modifier": score_components["doctrine_economic_modifier"],
            "terrain_affinity": score_components["terrain_affinity"],
            "core_status": score_components["core_status"],
            "region_display_name": region_display_name,
            "population_source_region": source_region_name,
            "population_source_before": source_population_before,
            "population_source_after": population_source.population if population_source is not None else 0,
            "population_source_ethnicity": source_ethnicity_before,
            "population_before": target_population_before,
            "population_after": world.regions[target_region_name].population,
            "population_transfer": transferred_population,
            "dominant_ethnicity_after": get_region_dominant_ethnicity(world.regions[target_region_name]),
            "region_reference": format_region_reference(
                world.regions[target_region_name],
                include_code=True,
            ),
        },
        context={
            "treasury_before": treasury_before,
            "treasury_after": faction.treasury,
            "owner_before": owner_before,
            "rank_before": rank_before,
        },
        impact={
            "owner_after": faction_name,
            "treasury_change": -EXPANSION_COST,
            "regions_gained": 1,
            "income_gain": income_gain,
            "population_change": world.regions[target_region_name].population - target_population_before,
            "rank_after": rank_after,
            "rank_change": rank_change,
            "future_expansion_opened": future_expansion_opened,
            "importance_tier": importance_tier,
            "is_turning_point": is_turning_point,
            "momentum_effect": momentum_effect,
            "strategic_role": strategic_role,
            "summary_reason": summary_reason,
            "narrative_tags": narrative_tags,
        },
        tags=expand_tags,
        significance=float(score_components["score"]),
    ))

    return True


def attack(faction_name, target_region_name, world):
    """Attempts a simple attack on an adjacent enemy-held region."""

    if target_region_name not in world.regions:
        return False

    if target_region_name not in get_attackable_regions(faction_name, world):
        return False

    attacker = world.factions[faction_name]
    target_region = world.regions[target_region_name]
    defender_name = target_region.owner

    if defender_name is None or defender_name == faction_name:
        return False

    if attacker.treasury < ATTACK_COST:
        return False

    score_components = get_attack_target_score_components(target_region_name, faction_name, world)
    war_objective, war_objective_label = _choose_war_objective(
        faction_name,
        defender_name,
        target_region,
        score_components,
        world,
    )
    treasury_before = attacker.treasury
    population_before = target_region.population
    attacker.treasury -= ATTACK_COST
    success_roll = random.random()
    succeeded = success_roll < score_components["success_chance"]
    treasury_change = -ATTACK_COST
    actual_failure_penalty = 0
    population_loss = 0
    trade_warfare_effect = {
        "trade_warfare_hit": False,
        "trade_warfare_pressure_added": 0.0,
        "trade_warfare_pressure": round(float(target_region.trade_warfare_pressure or 0.0), 3),
        "trade_blockade_added": 0.0,
        "trade_blockade_strength": round(float(target_region.trade_blockade_strength or 0.0), 3),
        "trade_warfare_target_role": target_region.trade_route_role or "local",
        "trade_gateway_role": target_region.trade_gateway_role or "none",
        "trade_value_denied": round(float(target_region.trade_value_denied or 0.0), 3),
        "port_blockaded": False,
    }
    defender_faction = world.factions.get(defender_name)
    is_reintegration_attempt = (
        defender_faction is not None
        and defender_faction.is_rebel
        and defender_faction.origin_faction == faction_name
    )
    is_proto_reintegration_attempt = (
        is_reintegration_attempt
        and defender_faction is not None
        and defender_faction.proto_state
    )

    if succeeded:
        population_loss = apply_region_population_loss(
            target_region,
            POPULATION_ATTACK_SUCCESS_LOSS,
        )
        apply_region_resource_damage(
            target_region,
            {
                RESOURCE_GRAIN: 0.06,
                RESOURCE_LIVESTOCK: 0.05,
                RESOURCE_HORSES: 0.04,
                RESOURCE_WILD_FOOD: 0.03,
                RESOURCE_TIMBER: 0.04,
                RESOURCE_SALT: 0.03,
                RESOURCE_TEXTILES: 0.04,
            },
        )
        apply_region_resource_damage(
            target_region,
            {
                RESOURCE_SALT: 0.08,
                RESOURCE_TEXTILES: 0.08,
                RESOURCE_TIMBER: 0.05,
            },
        )
        trade_warfare_effect = _apply_trade_warfare_pressure(target_region, succeeded=True)
        set_region_unrest(target_region, target_region.unrest + 0.45 + (trade_warfare_effect["trade_warfare_pressure_added"] * 1.1))
        handle_region_owner_change(target_region, faction_name)
        if is_proto_reintegration_attempt:
            set_region_unrest(
                target_region,
                min(target_region.unrest, REBEL_REABSORPTION_UNREST),
            )
        if not target_region.founding_name:
            assign_region_founding_name(
                world,
                target_region_name,
                faction_name,
                is_homeland=False,
            )
    else:
        population_loss = apply_region_population_loss(
            target_region,
            POPULATION_ATTACK_FAILURE_LOSS,
        )
        apply_region_resource_damage(
            target_region,
            {
                RESOURCE_GRAIN: 0.03,
                RESOURCE_LIVESTOCK: 0.025,
                RESOURCE_HORSES: 0.02,
                RESOURCE_WILD_FOOD: 0.015,
                RESOURCE_TIMBER: 0.02,
                RESOURCE_SALT: 0.015,
                RESOURCE_TEXTILES: 0.02,
            },
        )
        apply_region_resource_damage(
            target_region,
            {
                RESOURCE_SALT: 0.05,
                RESOURCE_TEXTILES: 0.05,
                RESOURCE_TIMBER: 0.03,
            },
        )
        trade_warfare_effect = _apply_trade_warfare_pressure(target_region, succeeded=False)
        set_region_unrest(target_region, target_region.unrest + 0.2 + (trade_warfare_effect["trade_warfare_pressure_added"] * 0.75))
        actual_failure_penalty = min(ATTACK_FAILURE_PENALTY, attacker.treasury)
        treasury_change -= actual_failure_penalty
        attacker.treasury -= actual_failure_penalty

    world.events.append(Event(
        turn=world.turn,
        type="attack",
        faction=faction_name,
        region=target_region_name,
        details={
            "defender": defender_name,
            "success": succeeded,
            "attack_cost": ATTACK_COST,
            "failure_penalty": actual_failure_penalty,
            "target_taxable_value": score_components["target_taxable_value"],
            "success_chance": round(score_components["success_chance"], 3),
            "attack_strength": score_components["attacker_strength"],
            "defense_strength": score_components["defender_strength"],
            "terrain_tags": score_components["terrain_tags"],
            "terrain_label": score_components["terrain_label"],
            "terrain_defense_modifier": score_components["defense_modifier"],
            "terrain_economic_modifier": score_components["economic_modifier"],
            "doctrine_combat_modifier": score_components["doctrine_combat_modifier"],
            "doctrine_economic_modifier": score_components["doctrine_economic_modifier"],
            "rebel_reclaim_bonus": score_components["rebel_reclaim_bonus"],
            "terrain_affinity": score_components["terrain_affinity"],
            "core_status": score_components["core_status"],
            "core_defense_bonus": score_components["core_defense_bonus"],
            "ethnic_claim_attack": score_components["ethnic_claim_bonus"] > 0,
            "claim_ethnicity": score_components.get("claim_ethnicity"),
            "regime_target_attack": score_components["regime_target_bonus"] > 0,
            "regime_target_reason": score_components.get("regime_target_reason"),
            "trade_chokepoint_bonus": score_components["trade_chokepoint_bonus"],
            "foreign_gateway_bonus": score_components["foreign_gateway_bonus"],
            "active_war_bonus": score_components.get("active_war_bonus", 0),
            "active_war_objective": score_components.get("active_war_objective"),
            "war_objective": war_objective,
            "war_objective_label": war_objective_label,
            "war_target_region": target_region_name,
            "region_display_name": target_region.display_name,
            "region_reference": format_region_reference(target_region, include_code=True),
            "population_before": population_before,
            "population_after": target_region.population,
            "population_loss": population_loss,
            **trade_warfare_effect,
        },
        context={
            "treasury_before": treasury_before,
            "owner_before": defender_name,
        },
        impact={
            "owner_after": faction_name if succeeded else defender_name,
            "treasury_after": attacker.treasury,
            "treasury_change": treasury_change,
            "success": succeeded,
            "population_change": target_region.population - population_before,
            "population_after": target_region.population,
            "reintegrated_rebel": succeeded and is_proto_reintegration_attempt,
            "reclaimed_successor": succeeded and is_reintegration_attempt and not is_proto_reintegration_attempt,
        },
        tags=[
            "combat",
            "attack",
            "success" if succeeded else "failure",
            *(["trade_warfare"] if trade_warfare_effect["trade_warfare_hit"] else []),
            *(["blockade"] if trade_warfare_effect["port_blockaded"] else []),
            *(["reintegration"] if is_reintegration_attempt else []),
        ],
        significance=score_components["success_chance"],
    ))

    return succeeded


def get_developable_regions(faction_name, world):
    """Returns a list of Regions the Faction owns and can currently develop."""

    developable_regions: set[str] = set()

    for region in world.regions.values():
        if (
            region.owner == faction_name
            and faction_knows_region(world, faction_name, region.name)
            and _get_development_project_options(faction_name, region, world)
        ):
            developable_regions.add(region.name)

    return sorted(developable_regions)


def get_investable_regions(faction_name, world):
    """Backward-compatible alias for owned regions with development projects."""
    return get_developable_regions(faction_name, world)


def develop(faction_name, target_region_name, world):
    """Returns whether the Faction successfully developed the target Region."""

    if target_region_name not in world.regions:
        return False

    if target_region_name not in get_developable_regions(faction_name, world):
        return False

    region = world.regions[target_region_name]
    taxable_before = get_region_taxable_value(region, world)
    resources_before = region.resources
    score_components = get_development_target_score_components(
        target_region_name,
        faction_name,
        world,
    )
    project_type = score_components["project_type"]
    source_region_name = score_components.get("source_region") or None
    if project_type == "none":
        return False

    project_amount = 0.0
    if project_type == "introduce_grain":
        region.resource_established[RESOURCE_GRAIN] = min(
            region.resource_suitability.get(RESOURCE_GRAIN, 0.0),
            region.resource_established.get(RESOURCE_GRAIN, 0.0) + 0.24,
        )
        project_amount = 0.24
    elif project_type == "introduce_livestock":
        region.resource_established[RESOURCE_LIVESTOCK] = min(
            region.resource_suitability.get(RESOURCE_LIVESTOCK, 0.0),
            region.resource_established.get(RESOURCE_LIVESTOCK, 0.0) + 0.2,
        )
        project_amount = 0.2
    elif project_type == "introduce_horses":
        region.resource_established[RESOURCE_HORSES] = min(
            region.resource_suitability.get(RESOURCE_HORSES, 0.0),
            region.resource_established.get(RESOURCE_HORSES, 0.0) + 0.16,
        )
        project_amount = 0.16
    elif project_type == "build_irrigation":
        region.irrigation_level = round(min(1.8, region.irrigation_level + 0.36), 2)
        region.agriculture_level = round(min(1.8, region.agriculture_level + 0.08), 2)
        project_amount = 0.36
    elif project_type == "expand_irrigation":
        region.irrigation_level = round(min(1.8, region.irrigation_level + 0.24), 2)
        region.agriculture_level = round(min(1.8, region.agriculture_level + 0.05), 2)
        project_amount = 0.24
    elif project_type == "improve_agriculture":
        region.agriculture_level = round(min(1.8, region.agriculture_level + 0.2), 2)
        if region.irrigation_level > 0:
            region.irrigation_level = round(min(1.8, region.irrigation_level + 0.08), 2)
        project_amount = 0.28
    elif project_type == "build_granary":
        region.granary_level = round(min(1.8, region.granary_level + 0.32), 2)
        project_amount = 0.32
    elif project_type == "build_storehouse":
        region.storehouse_level = round(min(1.8, region.storehouse_level + 0.34), 2)
        region.infrastructure_level = round(min(1.8, region.infrastructure_level + 0.05), 2)
        project_amount = 0.34
    elif project_type == "expand_storehouse":
        region.storehouse_level = round(min(1.8, region.storehouse_level + 0.24), 2)
        project_amount = 0.24
    elif project_type == "build_market":
        region.market_level = round(min(1.8, region.market_level + 0.3), 2)
        region.infrastructure_level = round(min(1.8, region.infrastructure_level + 0.04), 2)
        project_amount = 0.3
    elif project_type == "expand_market":
        region.market_level = round(min(1.8, region.market_level + 0.22), 2)
        project_amount = 0.22
    elif project_type == "establish_pasture":
        region.pasture_level = round(min(1.8, region.pasture_level + 0.34), 2)
        region.pastoral_level = round(min(1.8, region.pastoral_level + 0.06), 2)
        project_amount = 0.34
    elif project_type == "expand_pasture":
        region.pasture_level = round(min(1.8, region.pasture_level + 0.24), 2)
        region.pastoral_level = round(min(1.8, region.pastoral_level + 0.04), 2)
        project_amount = 0.24
    elif project_type == "build_logging_camp":
        region.logging_camp_level = round(min(1.8, region.logging_camp_level + 0.34), 2)
        region.infrastructure_level = round(min(1.8, region.infrastructure_level + 0.04), 2)
        project_amount = 0.34
    elif project_type == "expand_logging_camp":
        region.logging_camp_level = round(min(1.8, region.logging_camp_level + 0.24), 2)
        project_amount = 0.24
    elif project_type == "build_road_station":
        region.road_level = round(min(1.8, region.road_level + 0.34), 2)
        region.infrastructure_level = round(min(1.8, region.infrastructure_level + 0.08), 2)
        project_amount = 0.34
    elif project_type == "improve_road":
        region.road_level = round(min(1.8, region.road_level + 0.24), 2)
        region.infrastructure_level = round(min(1.8, region.infrastructure_level + 0.04), 2)
        project_amount = 0.24
    elif project_type == "build_copper_mine":
        region.copper_mine_level = round(min(1.8, region.copper_mine_level + 0.42), 2)
        project_amount = 0.42
    elif project_type == "expand_copper_mine":
        region.copper_mine_level = round(min(1.8, region.copper_mine_level + 0.28), 2)
        project_amount = 0.28
    elif project_type == "build_stone_quarry":
        region.stone_quarry_level = round(min(1.8, region.stone_quarry_level + 0.4), 2)
        project_amount = 0.4
    elif project_type == "expand_stone_quarry":
        region.stone_quarry_level = round(min(1.8, region.stone_quarry_level + 0.26), 2)
        project_amount = 0.26
    elif project_type == "improve_pastoralism":
        region.pastoral_level = round(min(1.8, region.pastoral_level + 0.18), 2)
        if region.pasture_level > 0:
            region.pasture_level = round(min(1.8, region.pasture_level + 0.06), 2)
        project_amount = 0.24
    elif project_type == "improve_extraction":
        if score_components["resource_focus"] == RESOURCE_COPPER:
            region.copper_mine_level = round(min(1.8, region.copper_mine_level + 0.28), 2)
        elif score_components["resource_focus"] == RESOURCE_STONE:
            region.stone_quarry_level = round(min(1.8, region.stone_quarry_level + 0.28), 2)
        region.extractive_level = round(min(1.8, region.extractive_level + 0.18), 2)
        project_amount = 0.28
    else:
        region.infrastructure_level = round(min(1.8, region.infrastructure_level + 0.18), 2)
        if region.road_level > 0:
            region.road_level = round(min(1.8, region.road_level + 0.05), 2)
        project_amount = 0.22

    region.last_resource_project_turn = world.turn
    if source_region_name is not None and source_region_name in world.regions:
        source_region = world.regions[source_region_name]
        source_region.last_resource_project_turn = world.turn
        apply_region_resource_damage(
            source_region,
            {
                score_components["resource_focus"]: 0.05
                if project_type == "introduce_grain"
                else 0.045
                if project_type == "introduce_livestock"
                else 0.04
            },
        )

    update_faction_resource_economy(world)
    taxable_after = get_region_taxable_value(region, world)

    world.events.append(Event(
        turn=world.turn,
        type="develop",
        faction=faction_name,
        region=target_region_name,
        details={
            "development_amount": project_amount,
            "invest_amount": project_amount,
            "project_type": project_type,
            "resource_focus": score_components["resource_focus"],
            "source_region": source_region_name,
            "region_display_name": region.display_name,
            "region_reference": format_region_reference(region, include_code=True),
        },
        context={
            "resources_before": resources_before,
            "taxable_before": taxable_before,
        },
        impact={
            "new_resources": region.resources,
            "resource_change": region.resources - resources_before,
            "new_taxable_value": taxable_after,
            "taxable_change": round(taxable_after - taxable_before, 2),
        },
        tags=["development", "investment", str(project_type)],
        significance=max(0.1, float(round(taxable_after - taxable_before, 2))),
    ))

    return True


def invest(faction_name, target_region_name, world):
    """Backward-compatible alias for regional development projects."""
    return develop(faction_name, target_region_name, world)
