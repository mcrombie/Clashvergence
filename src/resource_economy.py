from __future__ import annotations

from heapq import heappop, heappush
from math import ceil

from src.config import (
    FOOD_STORAGE_AGRICULTURE_FACTOR,
    FOOD_STORAGE_BASE_PER_REGION,
    FOOD_STORAGE_BASE_SPOILAGE,
    FOOD_STORAGE_CITY_BONUS,
    FOOD_STORAGE_CORE_BONUS,
    FOOD_STORAGE_GRANARY_FACTOR,
    FOOD_STORAGE_GRANARY_SPOILAGE_REDUCTION,
    FOOD_STORAGE_HOMELAND_BONUS,
    FOOD_STORAGE_INFRASTRUCTURE_FACTOR,
    FOOD_STORAGE_INFRASTRUCTURE_SPOILAGE_REDUCTION,
    FOOD_STORAGE_MIN_SPOILAGE,
    FOOD_STORAGE_RURAL_BONUS,
    FOOD_STORAGE_TOWN_BONUS,
    FRONTIER_MAINTENANCE_SURCHARGE,
    REGION_MAINTENANCE_COST,
    UNREST_MAINTENANCE_MAX_FACTOR,
    UNREST_MAX,
    UNREST_MODERATE_THRESHOLD,
)
from src.governance import (
    get_faction_income_modifier,
    get_faction_maintenance_modifier,
)
from src.models import Faction, Region, WorldState
from src.region_state import (
    get_region_climate_affinity,
    get_region_climate_maintenance_factor,
    get_region_core_status,
    get_region_income_factor,
    get_region_unrest_income_factor,
)
from src.resources import (
    ALL_CAPACITIES,
    ALL_RESOURCES,
    CAPACITY_CONSTRUCTION,
    CAPACITY_FOOD_SECURITY,
    CAPACITY_METAL,
    CAPACITY_MOBILITY,
    CAPACITY_TAXABLE_VALUE,
    COMMERCIAL_RESOURCES,
    CONSTRUCTION_RESOURCES,
    DOMESTICABLE_RESOURCES,
    EXTRACTIVE_RESOURCES,
    FOOD_RESOURCES,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_LIVESTOCK,
    RESOURCE_SALT,
    RESOURCE_STONE,
    RESOURCE_TIMBER,
    RESOURCE_TEXTILES,
    RESOURCE_WILD_FOOD,
    WILD_RESOURCES,
    build_empty_capacity_map,
    build_empty_resource_map,
    get_legacy_region_resource_value,
    normalize_capacity_map,
    normalize_resource_map,
    seed_region_resource_profile,
)


RESOURCE_BASE_OUTPUT = {
    RESOURCE_GRAIN: 3.4,
    RESOURCE_LIVESTOCK: 2.25,
    RESOURCE_HORSES: 1.9,
    RESOURCE_WILD_FOOD: 1.8,
    RESOURCE_TIMBER: 1.5,
    RESOURCE_COPPER: 1.7,
    RESOURCE_STONE: 1.55,
    RESOURCE_SALT: 1.35,
    RESOURCE_TEXTILES: 1.45,
}
RESOURCE_GROWTH_STEP = {
    RESOURCE_GRAIN: 0.04,
    RESOURCE_LIVESTOCK: 0.03,
    RESOURCE_HORSES: 0.025,
    RESOURCE_TEXTILES: 0.02,
}
RESOURCE_DAMAGE_DECAY = 0.03
RESOURCE_MAX_DAMAGE = 0.65
RESOURCE_ROUTE_BASE_STEP_COST = 1.0
RESOURCE_ROUTE_FRONTIER_STEP_PENALTY = 0.42
RESOURCE_ROUTE_CORE_STEP_PENALTY = 0.08
RESOURCE_ROUTE_UNREST_STEP_FACTOR = 0.05
RESOURCE_ROUTE_CRISIS_STEP_PENALTY = 0.35
RESOURCE_ROUTE_DISTURBANCE_STEP_PENALTY = 0.15
RESOURCE_ROUTE_POPULATION_STEP_PENALTY = 0.08
RESOURCE_ROUTE_INFRASTRUCTURE_STEP_BONUS = 0.12
RESOURCE_ROUTE_DAMAGE_STEP_FACTOR = 0.7
RESOURCE_ROUTE_SETTLEMENT_STEP_PENALTIES = {
    "wild": 0.45,
    "rural": 0.18,
    "town": 0.08,
    "city": 0.0,
}
RESOURCE_ROUTE_BOTTLENECK_FRONTIER_PENALTY = 0.14
RESOURCE_ROUTE_BOTTLENECK_WILD_PENALTY = 0.18
RESOURCE_ROUTE_BOTTLENECK_UNREST_FACTOR = 0.03
RESOURCE_ROUTE_BOTTLENECK_DAMAGE_FACTOR = 0.45
RESOURCE_ROUTE_BOTTLENECK_INFRASTRUCTURE_BONUS = 0.09
RESOURCE_ROUTE_BOTTLENECK_INTEGRATION_BONUS = 0.015
RESOURCE_ROUTE_ROAD_STEP_BONUS = 0.18
RESOURCE_ROUTE_ROAD_SUPPORT_BONUS = 0.1
RESOURCE_GRAIN_UNIRRIGATED_FACTOR = 0.78
RESOURCE_GRAIN_IRRIGATION_LEVEL_FACTOR = 0.55
RESOURCE_GRAIN_SUPPORT_LEVEL_FACTOR = 0.22
RESOURCE_LIVESTOCK_UNPASTURED_FACTOR = 0.8
RESOURCE_LIVESTOCK_PASTURE_LEVEL_FACTOR = 0.48
RESOURCE_LIVESTOCK_SUPPORT_LEVEL_FACTOR = 0.4
RESOURCE_HORSE_UNPASTURED_FACTOR = 0.72
RESOURCE_HORSE_PASTURE_LEVEL_FACTOR = 0.7
RESOURCE_HORSE_SUPPORT_LEVEL_FACTOR = 0.22
RESOURCE_TIMBER_UNDEVELOPED_FACTOR = 0.58
RESOURCE_TIMBER_LOGGING_LEVEL_FACTOR = 0.78
RESOURCE_TEXTILE_BASE_FACTOR = 0.68
RESOURCE_TEXTILE_MARKET_FACTOR = 0.28
RESOURCE_TEXTILE_INFRASTRUCTURE_FACTOR = 0.16
RESOURCE_TEXTILE_FIBER_FACTOR = 0.16
RESOURCE_EXTRACTIVE_UNDEVELOPED_FACTOR = 0.18
RESOURCE_EXTRACTIVE_SITE_LEVEL_FACTOR = 0.95
RESOURCE_EXTRACTIVE_SUPPORT_LEVEL_FACTOR = 0.16
RESOURCE_SALT_UNWORKED_FACTOR = 0.34
RESOURCE_SALT_STOREHOUSE_FACTOR = 0.16
RESOURCE_SALT_MARKET_FACTOR = 0.12
RESOURCE_RETENTION_BASE_FACTOR = 0.72
RESOURCE_RETENTION_INFRASTRUCTURE_FACTOR = 0.05
RESOURCE_RETENTION_STOREHOUSE_FACTOR = 0.18
RESOURCE_RETENTION_MARKET_FACTOR = 0.04
RESOURCE_RETENTION_GRANARY_FACTOR = 0.16
RESOURCE_RETENTION_SETTLEMENT_BONUSES = {
    "wild": -0.08,
    "rural": -0.02,
    "town": 0.04,
    "city": 0.08,
}
RESOURCE_MONETIZATION_SETTLEMENT_BASE = {
    "wild": 0.28,
    "rural": 0.4,
    "town": 0.56,
    "city": 0.72,
}
RESOURCE_MONETIZATION_MARKET_FACTOR = 0.22
RESOURCE_MONETIZATION_INFRASTRUCTURE_FACTOR = 0.04
RESOURCE_MONETIZATION_ROAD_FACTOR = 0.04
RESOURCE_MONETIZATION_STOREHOUSE_FACTOR = 0.03
RESOURCE_MONETIZATION_ROUTE_FACTOR = 0.12
RESOURCE_MONETIZATION_BOTTLENECK_FACTOR = 0.08
RESOURCE_MONETIZATION_HOMELAND_BONUS = 0.05
RESOURCE_MONETIZATION_CORE_BONUS = 0.03
TRADE_IMPORT_POPULATION_FACTOR = 0.003
TRADE_IMPORT_MARKET_FACTOR = 0.12
TRADE_IMPORT_STOREHOUSE_FACTOR = 0.05
TRADE_IMPORT_SETTLEMENT_BONUSES = {
    "wild": 0.0,
    "rural": 0.05,
    "town": 0.12,
    "city": 0.2,
}
TRADE_IMPORT_DEPTH_FACTOR = 0.018
TRADE_TRANSIT_BASE_FACTOR = 0.045
TRADE_TRANSIT_ROAD_FACTOR = 0.03
TRADE_TRANSIT_INFRASTRUCTURE_FACTOR = 0.022
TRADE_TRANSIT_MARKET_FACTOR = 0.014
TRADE_HUB_BASE_FACTOR = 0.038
TRADE_HUB_MARKET_FACTOR = 0.03
TRADE_HUB_INFRASTRUCTURE_FACTOR = 0.022
TRADE_HUB_SETTLEMENT_BONUSES = {
    "wild": 0.0,
    "rural": 0.01,
    "town": 0.04,
    "city": 0.08,
}
TRADE_DISRUPTION_ISOLATION_FACTOR = 0.62
TRADE_DISRUPTION_BOTTLENECK_FACTOR = 0.78
TRADE_DISRUPTION_UNREST_FACTOR = 0.024
TRADE_DISRUPTION_DAMAGE_FACTOR = 0.34
TRADE_DISRUPTION_DEPTH_FACTOR = 0.018

RouteState = dict[str, float | int | str | None]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _sum_resource_map(resource_map: dict[str, float] | None) -> float:
    return round(sum((resource_map or {}).values()), 3)


def ensure_region_resource_state(region: Region) -> None:
    has_seed_data = any([
        bool(region.resource_fixed_endowments),
        bool(region.resource_wild_endowments),
        bool(region.resource_suitability),
    ])
    if not has_seed_data:
        seed_region_resource_profile(region)
    else:
        region.resource_fixed_endowments = normalize_resource_map(region.resource_fixed_endowments)
        region.resource_wild_endowments = normalize_resource_map(region.resource_wild_endowments)
        region.resource_suitability = normalize_resource_map(region.resource_suitability)
        region.resource_established = normalize_resource_map(region.resource_established)
        region.resource_output = normalize_resource_map(region.resource_output)
        region.resource_retained_output = normalize_resource_map(region.resource_retained_output)
        region.resource_routed_output = normalize_resource_map(region.resource_routed_output)
        region.resource_effective_output = normalize_resource_map(region.resource_effective_output)
        region.resource_damage = normalize_resource_map(region.resource_damage)
    region.resource_retained_output = normalize_resource_map(region.resource_retained_output)
    region.resource_routed_output = normalize_resource_map(region.resource_routed_output)
    region.resource_effective_output = normalize_resource_map(region.resource_effective_output)
    region.resource_damage = normalize_resource_map(region.resource_damage)
    region.resource_monetized_value = round(max(0.0, float(region.resource_monetized_value or 0.0)), 3)
    region.resource_isolation_factor = round(float(region.resource_isolation_factor or 0.0), 3)
    region.resource_route_depth = (
        int(region.resource_route_depth)
        if region.resource_route_depth is not None
        else None
    )
    region.resource_route_cost = round(float(region.resource_route_cost or 0.0), 3)
    region.resource_route_anchor = region.resource_route_anchor or None
    region.resource_route_bottleneck = round(float(region.resource_route_bottleneck or 0.0), 3)
    region.trade_route_role = (region.trade_route_role or "local").strip().lower()
    region.trade_route_parent = region.trade_route_parent or None
    region.trade_route_children = int(region.trade_route_children or 0)
    region.trade_served_regions = int(region.trade_served_regions or 0)
    region.trade_throughput = round(max(0.0, float(region.trade_throughput or 0.0)), 3)
    region.trade_transit_flow = round(max(0.0, float(region.trade_transit_flow or 0.0)), 3)
    region.trade_import_value = round(max(0.0, float(region.trade_import_value or 0.0)), 3)
    region.trade_transit_value = round(max(0.0, float(region.trade_transit_value or 0.0)), 3)
    region.trade_hub_value = round(max(0.0, float(region.trade_hub_value or 0.0)), 3)
    region.trade_value_bonus = round(max(0.0, float(region.trade_value_bonus or 0.0)), 3)
    region.trade_import_reliance = round(
        _clamp(float(region.trade_import_reliance or 0.0), 0.0, 1.0),
        3,
    )
    region.trade_disruption_risk = round(
        _clamp(float(region.trade_disruption_risk or 0.0), 0.0, 1.0),
        3,
    )
    region.storehouse_level = round(max(0.0, float(region.storehouse_level or 0.0)), 2)
    region.market_level = round(max(0.0, float(region.market_level or 0.0)), 2)
    region.irrigation_level = round(max(0.0, float(region.irrigation_level or 0.0)), 2)
    region.pasture_level = round(max(0.0, float(region.pasture_level or 0.0)), 2)
    region.logging_camp_level = round(max(0.0, float(region.logging_camp_level or 0.0)), 2)
    region.road_level = round(max(0.0, float(region.road_level or 0.0)), 2)
    region.copper_mine_level = round(max(0.0, float(region.copper_mine_level or 0.0)), 2)
    region.stone_quarry_level = round(max(0.0, float(region.stone_quarry_level or 0.0)), 2)


def ensure_region_food_state(region: Region) -> None:
    region.food_stored = round(max(0.0, float(region.food_stored or 0.0)), 3)
    region.food_storage_capacity = round(max(0.0, float(region.food_storage_capacity or 0.0)), 3)
    region.food_produced = round(max(0.0, float(region.food_produced or 0.0)), 3)
    region.food_consumption = round(max(0.0, float(region.food_consumption or 0.0)), 3)
    region.food_balance = round(float(region.food_balance or 0.0), 3)
    region.food_deficit = round(max(0.0, float(region.food_deficit or 0.0)), 3)
    region.food_spoilage = round(max(0.0, float(region.food_spoilage or 0.0)), 3)
    region.food_overflow = round(max(0.0, float(region.food_overflow or 0.0)), 3)


def _ensure_faction_resource_state(faction: Faction) -> None:
    faction.resource_gross_output = normalize_resource_map(faction.resource_gross_output)
    faction.resource_effective_access = normalize_resource_map(faction.resource_effective_access)
    faction.resource_isolated_output = normalize_resource_map(faction.resource_isolated_output)
    faction.resource_access = normalize_resource_map(faction.resource_access)
    faction.resource_shortages = {
        **build_empty_resource_map(),
        **build_empty_capacity_map(),
        **{
            key: round(float(value), 3)
            for key, value in (faction.resource_shortages or {}).items()
        },
    }
    faction.derived_capacity = normalize_capacity_map(faction.derived_capacity)
    faction.food_stored = round(max(0.0, float(faction.food_stored or 0.0)), 3)
    faction.food_storage_capacity = round(max(0.0, float(faction.food_storage_capacity or 0.0)), 3)
    faction.food_produced = round(max(0.0, float(faction.food_produced or 0.0)), 3)
    faction.food_consumption = round(max(0.0, float(faction.food_consumption or 0.0)), 3)
    faction.food_balance = round(float(faction.food_balance or 0.0), 3)
    faction.food_deficit = round(max(0.0, float(faction.food_deficit or 0.0)), 3)
    faction.food_spoilage = round(max(0.0, float(faction.food_spoilage or 0.0)), 3)
    faction.food_overflow = round(max(0.0, float(faction.food_overflow or 0.0)), 3)
    faction.trade_income = round(max(0.0, float(faction.trade_income or 0.0)), 3)
    faction.trade_transit_value = round(max(0.0, float(faction.trade_transit_value or 0.0)), 3)
    faction.trade_import_dependency = round(
        _clamp(float(faction.trade_import_dependency or 0.0), 0.0, 1.0),
        3,
    )
    faction.trade_corridor_exposure = round(
        _clamp(float(faction.trade_corridor_exposure or 0.0), 0.0, 1.0),
        3,
    )


def get_region_resource_workforce_factor(region: Region) -> float:
    if region.population <= 0:
        return 0.2 if region.owner is None else 0.3
    settlement_bonus = {
        "wild": 0.0,
        "rural": 0.05,
        "town": 0.12,
        "city": 0.22,
    }.get(region.settlement_level, 0.0)
    base = 0.2 if region.owner is None else 0.35
    return _clamp(base + min(0.95, region.population / 180.0) + settlement_bonus, 0.2, 1.45)


def get_region_resource_integration_factor(region: Region) -> float:
    if region.owner is None:
        return 0.45
    status = get_region_core_status(region)
    if status == "homeland":
        return 1.0
    if status == "core":
        return 0.9
    return _clamp(0.6 + (region.integration_score * 0.03), 0.6, 0.82)


def get_region_resource_unrest_factor(region: Region) -> float:
    unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
    return _clamp(1.0 - (unrest_ratio * 0.65), 0.35, 1.0)


def get_region_resource_climate_factor(region: Region, world: WorldState | None) -> float:
    if world is None or region.owner is None or region.owner not in world.factions:
        return 1.0
    return 0.85 + (get_region_climate_affinity(region, world) * 0.3)


def get_region_resource_development_factor(region: Region, resource_name: str) -> float:
    if resource_name == RESOURCE_GRAIN:
        return (
            RESOURCE_GRAIN_UNIRRIGATED_FACTOR
            + (region.irrigation_level * RESOURCE_GRAIN_IRRIGATION_LEVEL_FACTOR)
            + (region.agriculture_level * RESOURCE_GRAIN_SUPPORT_LEVEL_FACTOR)
            + (region.infrastructure_level * 0.08)
        )
    if resource_name == RESOURCE_LIVESTOCK:
        return (
            RESOURCE_LIVESTOCK_UNPASTURED_FACTOR
            + (region.pasture_level * RESOURCE_LIVESTOCK_PASTURE_LEVEL_FACTOR)
            + (region.pastoral_level * RESOURCE_LIVESTOCK_SUPPORT_LEVEL_FACTOR)
            + (region.infrastructure_level * 0.06)
        )
    if resource_name == RESOURCE_HORSES:
        return (
            RESOURCE_HORSE_UNPASTURED_FACTOR
            + (region.pasture_level * RESOURCE_HORSE_PASTURE_LEVEL_FACTOR)
            + (region.pastoral_level * RESOURCE_HORSE_SUPPORT_LEVEL_FACTOR)
            + (region.infrastructure_level * 0.08)
        )
    if resource_name == RESOURCE_TEXTILES:
        settlement_bonus = {
            "wild": 0.0,
            "rural": 0.04,
            "town": 0.1,
            "city": 0.16,
        }.get(region.settlement_level, 0.0)
        return (
            RESOURCE_TEXTILE_BASE_FACTOR
            + (region.agriculture_level * 0.12)
            + (region.pastoral_level * RESOURCE_TEXTILE_FIBER_FACTOR)
            + (region.infrastructure_level * RESOURCE_TEXTILE_INFRASTRUCTURE_FACTOR)
            + settlement_bonus
        )
    if resource_name == RESOURCE_TIMBER:
        return (
            RESOURCE_TIMBER_UNDEVELOPED_FACTOR
            + (region.logging_camp_level * RESOURCE_TIMBER_LOGGING_LEVEL_FACTOR)
            + (region.infrastructure_level * 0.08)
        )
    if resource_name == RESOURCE_SALT:
        return (
            RESOURCE_SALT_UNWORKED_FACTOR
            + (region.extractive_level * RESOURCE_EXTRACTIVE_SUPPORT_LEVEL_FACTOR)
            + (region.infrastructure_level * 0.1)
        )
    if resource_name in EXTRACTIVE_RESOURCES:
        site_level = get_region_extractive_site_level(region, resource_name)
        return (
            RESOURCE_EXTRACTIVE_UNDEVELOPED_FACTOR
            + (site_level * RESOURCE_EXTRACTIVE_SITE_LEVEL_FACTOR)
            + (region.extractive_level * RESOURCE_EXTRACTIVE_SUPPORT_LEVEL_FACTOR)
            + (region.infrastructure_level * 0.12)
        )
    return 0.95 + (region.infrastructure_level * 0.1)


def get_region_extractive_site_level(region: Region, resource_name: str) -> float:
    if resource_name == RESOURCE_COPPER:
        return float(region.copper_mine_level or 0.0)
    if resource_name == RESOURCE_STONE:
        return float(region.stone_quarry_level or 0.0)
    return 0.0


def _get_domestic_resource_decay(region: Region, resource_name: str) -> float:
    decay = 0.0
    if region.owner is None:
        decay += 0.018
    if region.population < 90:
        decay += 0.012
    if region.unrest >= UNREST_MODERATE_THRESHOLD:
        decay += 0.012
    if region.unrest_event_level == "crisis":
        decay += 0.018
    if get_region_core_status(region) == "frontier":
        decay += 0.006
    if resource_name == RESOURCE_GRAIN and region.agriculture_level < 0.1:
        decay += 0.007
    if resource_name == RESOURCE_LIVESTOCK and region.pastoral_level < 0.1:
        decay += 0.007
    if resource_name == RESOURCE_HORSES and region.pastoral_level < 0.1:
        decay += 0.007
    if resource_name == RESOURCE_TEXTILES and region.market_level < 0.1:
        decay += 0.006
    decay += region.resource_damage.get(resource_name, 0.0) * 0.06
    return decay


def _advance_region_resource_damage(region: Region) -> None:
    for resource_name in ALL_RESOURCES:
        current_damage = region.resource_damage.get(resource_name, 0.0)
        if current_damage <= 0:
            continue
        region.resource_damage[resource_name] = round(
            max(0.0, current_damage - RESOURCE_DAMAGE_DECAY),
            3,
        )


def advance_region_domesticable_resources(region: Region) -> None:
    ensure_region_resource_state(region)
    _advance_region_resource_damage(region)
    for resource_name in DOMESTICABLE_RESOURCES:
        established = region.resource_established.get(resource_name, 0.0)
        if established <= 0:
            continue
        cap = region.resource_suitability.get(resource_name, 0.0)
        if cap <= 0:
            continue
        growth = 0.0
        if region.owner is not None:
            growth = RESOURCE_GROWTH_STEP.get(resource_name, 0.02)
            if resource_name == RESOURCE_GRAIN:
                growth += region.agriculture_level * 0.01
            elif resource_name == RESOURCE_LIVESTOCK:
                growth += region.pastoral_level * 0.01
            elif resource_name == RESOURCE_HORSES:
                growth += region.pastoral_level * 0.01
            elif resource_name == RESOURCE_TEXTILES:
                growth += region.market_level * 0.008 + region.infrastructure_level * 0.004
            growth *= max(0.35, get_region_resource_unrest_factor(region))
        decay = _get_domestic_resource_decay(region, resource_name)
        region.resource_established[resource_name] = round(
            _clamp(established + growth - decay, 0.0, cap),
            3,
        )


def _get_owned_resource_anchor_names(world: WorldState, faction_name: str) -> set[str]:
    homeland_names = {
        region.name
        for region in world.regions.values()
        if region.owner == faction_name and get_region_core_status(region) == "homeland"
    }
    if homeland_names:
        return homeland_names

    core_names = {
        region.name
        for region in world.regions.values()
        if region.owner == faction_name and get_region_core_status(region) == "core"
    }
    if core_names:
        return core_names

    return {
        region.name
        for region in world.regions.values()
        if region.owner == faction_name
    }


def _get_region_route_step_cost(region: Region) -> float:
    step_cost = RESOURCE_ROUTE_BASE_STEP_COST
    status = get_region_core_status(region)
    if status == "frontier":
        step_cost += RESOURCE_ROUTE_FRONTIER_STEP_PENALTY
    elif status == "core":
        step_cost += RESOURCE_ROUTE_CORE_STEP_PENALTY

    step_cost += RESOURCE_ROUTE_SETTLEMENT_STEP_PENALTIES.get(region.settlement_level, 0.1)
    step_cost += min(0.65, region.unrest * RESOURCE_ROUTE_UNREST_STEP_FACTOR)
    if region.unrest_event_level == "disturbance":
        step_cost += RESOURCE_ROUTE_DISTURBANCE_STEP_PENALTY
    elif region.unrest_event_level == "crisis":
        step_cost += RESOURCE_ROUTE_CRISIS_STEP_PENALTY
    if region.population < 90:
        step_cost += RESOURCE_ROUTE_POPULATION_STEP_PENALTY

    average_damage = sum(region.resource_damage.values()) / max(1, len(ALL_RESOURCES))
    step_cost += min(0.3, average_damage * RESOURCE_ROUTE_DAMAGE_STEP_FACTOR)
    step_cost -= min(0.28, region.infrastructure_level * RESOURCE_ROUTE_INFRASTRUCTURE_STEP_BONUS)
    step_cost -= min(0.35, region.road_level * RESOURCE_ROUTE_ROAD_STEP_BONUS)
    return _clamp(step_cost, 0.55, 2.4)


def _get_region_corridor_support_factor(region: Region) -> float:
    support = 0.78
    status = get_region_core_status(region)
    if status == "homeland":
        support += 0.12
    elif status == "core":
        support += 0.04
    else:
        support -= RESOURCE_ROUTE_BOTTLENECK_FRONTIER_PENALTY

    if region.settlement_level == "wild":
        support -= RESOURCE_ROUTE_BOTTLENECK_WILD_PENALTY
    elif region.settlement_level == "rural":
        support -= 0.08
    elif region.settlement_level == "city":
        support += 0.04

    if region.population < 60:
        support -= 0.08
    elif region.population >= 180:
        support += 0.03

    support += min(0.16, region.infrastructure_level * RESOURCE_ROUTE_BOTTLENECK_INFRASTRUCTURE_BONUS)
    support += min(0.18, region.road_level * RESOURCE_ROUTE_ROAD_SUPPORT_BONUS)
    support += min(0.12, region.integration_score * RESOURCE_ROUTE_BOTTLENECK_INTEGRATION_BONUS)
    support -= min(0.18, region.unrest * RESOURCE_ROUTE_BOTTLENECK_UNREST_FACTOR)
    average_damage = sum(region.resource_damage.values()) / max(1, len(ALL_RESOURCES))
    support -= min(0.16, average_damage * RESOURCE_ROUTE_BOTTLENECK_DAMAGE_FACTOR)

    if region.unrest_event_level == "disturbance":
        support -= 0.05
    elif region.unrest_event_level == "crisis":
        support -= 0.12

    return _clamp(support, 0.32, 1.0)


def build_faction_resource_route_map(
    world: WorldState,
    faction_name: str,
) -> dict[str, RouteState]:
    anchor_names = _get_owned_resource_anchor_names(world, faction_name)
    if not anchor_names:
        return {}

    route_map: dict[str, RouteState] = {}
    frontier: list[tuple[float, float, int, str, str]] = []
    best_routes: dict[str, tuple[float, float]] = {}

    for anchor_name in sorted(anchor_names):
        route_map[anchor_name] = {
            "anchor": anchor_name,
            "parent": None,
            "depth": 0,
            "cost": 0.0,
            "bottleneck": 1.0,
        }
        best_routes[anchor_name] = (0.0, 1.0)
        heappush(frontier, (0.0, -1.0, 0, anchor_name, anchor_name))

    while frontier:
        route_cost, negative_bottleneck, route_depth, region_name, anchor_name = heappop(frontier)
        route_bottleneck = -negative_bottleneck
        best_cost, best_bottleneck = best_routes.get(region_name, (float("inf"), 0.0))
        if (
            route_cost > best_cost + 1e-9
            or (abs(route_cost - best_cost) <= 1e-9 and route_bottleneck < best_bottleneck - 1e-9)
        ):
            continue
        current_region = world.regions[region_name]
        for neighbor_name in current_region.neighbors:
            neighbor = world.regions[neighbor_name]
            if neighbor.owner != faction_name:
                continue
            step_cost = _get_region_route_step_cost(neighbor)
            step_support = _get_region_corridor_support_factor(neighbor)
            next_cost = route_cost + step_cost
            next_bottleneck = min(route_bottleneck, step_support)
            best_known = best_routes.get(neighbor_name)
            if best_known is not None:
                best_known_cost, best_known_bottleneck = best_known
                if (
                    next_cost > best_known_cost + 0.25
                    or (
                        abs(next_cost - best_known_cost) <= 0.25
                        and next_bottleneck <= best_known_bottleneck + 1e-9
                    )
                ):
                    continue
            if best_known is None or next_cost < best_known[0] - 1e-9 or (
                abs(next_cost - best_known[0]) <= 0.25 and next_bottleneck > best_known[1] + 1e-9
            ):
                best_routes[neighbor_name] = (next_cost, next_bottleneck)
            else:
                continue
            route_map[neighbor_name] = {
                "anchor": anchor_name,
                "parent": region_name,
                "depth": route_depth + 1,
                "cost": round(next_cost, 3),
                "bottleneck": round(next_bottleneck, 3),
            }
            heappush(frontier, (next_cost, -next_bottleneck, route_depth + 1, neighbor_name, anchor_name))

    return route_map


def _build_world_resource_route_maps(world: WorldState) -> dict[str, dict[str, RouteState]]:
    return {
        faction_name: build_faction_resource_route_map(world, faction_name)
        for faction_name in world.factions
    }


def _get_region_trade_demand(region: Region) -> float:
    settlement_bonus = TRADE_IMPORT_SETTLEMENT_BONUSES.get(region.settlement_level, 0.0)
    return round(
        max(0.08, region.population * TRADE_IMPORT_POPULATION_FACTOR)
        + settlement_bonus
        + (region.market_level * TRADE_IMPORT_MARKET_FACTOR)
        + (region.storehouse_level * TRADE_IMPORT_STOREHOUSE_FACTOR),
        3,
    )


def _get_region_average_resource_damage(region: Region) -> float:
    return sum(region.resource_damage.values()) / max(1, len(ALL_RESOURCES))


def _get_trade_route_role(
    region: Region,
    *,
    depth: int,
    children_count: int,
    route_factor: float,
    bottleneck: float,
) -> str:
    if depth <= 0:
        return "hub"
    if route_factor < 0.38 or (route_factor < 0.5 and bottleneck < 0.55):
        return "isolated"
    if children_count > 0:
        return "corridor"
    return "terminal"


def _apply_faction_trade_state(
    world: WorldState,
    faction_name: str,
    faction_route_map: dict[str, RouteState],
) -> None:
    faction = world.factions[faction_name]
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]
    if not owned_regions:
        faction.trade_income = 0.0
        faction.trade_transit_value = 0.0
        faction.trade_import_dependency = 0.0
        faction.trade_corridor_exposure = 0.0
        return

    children_by_region = {
        region.name: []
        for region in owned_regions
    }
    for region_name, route_state in faction_route_map.items():
        parent_name = route_state.get("parent")
        if (
            isinstance(parent_name, str)
            and parent_name in children_by_region
            and region_name in children_by_region
        ):
            children_by_region[parent_name].append(region_name)

    local_flow = {
        region.name: _sum_resource_map(region.resource_routed_output)
        for region in owned_regions
    }
    throughput_by_region: dict[str, float] = {}
    served_by_region: dict[str, int] = {}

    def measure_trade_tree(region_name: str) -> tuple[float, int]:
        total_flow = local_flow.get(region_name, 0.0)
        served_regions = 0
        for child_name in children_by_region.get(region_name, []):
            child_flow, child_served = measure_trade_tree(child_name)
            total_flow += child_flow
            served_regions += child_served + 1
        throughput_by_region[region_name] = round(total_flow, 3)
        served_by_region[region_name] = served_regions
        return total_flow, served_regions

    root_names = sorted(
        region.name
        for region in owned_regions
        if faction_route_map.get(region.name, {}).get("parent") is None
    )
    for root_name in root_names:
        measure_trade_tree(root_name)
    for region in owned_regions:
        throughput_by_region.setdefault(region.name, local_flow.get(region.name, 0.0))
        served_by_region.setdefault(region.name, 0)

    total_trade_income = 0.0
    total_transit_value = 0.0
    total_import_value = 0.0
    total_base_value = 0.0
    exposure_weight = 0.0
    weighted_exposure = 0.0

    for region in owned_regions:
        route_state = faction_route_map.get(region.name, {})
        depth = int(route_state.get("depth", region.resource_route_depth or 0) or 0)
        parent_name = route_state.get("parent")
        throughput = float(throughput_by_region.get(region.name, local_flow.get(region.name, 0.0)))
        transit_flow = max(0.0, throughput - local_flow.get(region.name, 0.0))
        route_factor = max(0.0, 1.0 - float(region.resource_isolation_factor or 0.0))
        bottleneck = max(0.35, float(region.resource_route_bottleneck or 0.35))
        average_damage = _get_region_average_resource_damage(region)
        disruption_risk = _clamp(
            (float(region.resource_isolation_factor or 0.0) * TRADE_DISRUPTION_ISOLATION_FACTOR)
            + (max(0.0, 0.85 - bottleneck) * TRADE_DISRUPTION_BOTTLENECK_FACTOR)
            + (region.unrest * TRADE_DISRUPTION_UNREST_FACTOR)
            + (average_damage * TRADE_DISRUPTION_DAMAGE_FACTOR)
            + (depth * TRADE_DISRUPTION_DEPTH_FACTOR),
            0.0,
            0.95,
        )
        children_count = len(children_by_region.get(region.name, []))
        route_role = _get_trade_route_role(
            region,
            depth=depth,
            children_count=children_count,
            route_factor=route_factor,
            bottleneck=bottleneck,
        )

        import_value = 0.0
        if depth > 0:
            import_value = (
                _get_region_trade_demand(region)
                * route_factor
                * bottleneck
                * (
                    0.18
                    + TRADE_IMPORT_SETTLEMENT_BONUSES.get(region.settlement_level, 0.0)
                    + (region.market_level * 0.06)
                    + (region.storehouse_level * 0.02)
                    + min(0.12, depth * TRADE_IMPORT_DEPTH_FACTOR)
                )
                * (1.0 - (disruption_risk * 0.55))
            )

        transit_value = 0.0
        if transit_flow > 0:
            transit_value = (
                transit_flow
                * route_factor
                * bottleneck
                * (
                    TRADE_TRANSIT_BASE_FACTOR
                    + (region.road_level * TRADE_TRANSIT_ROAD_FACTOR)
                    + (region.infrastructure_level * TRADE_TRANSIT_INFRASTRUCTURE_FACTOR)
                    + (region.market_level * TRADE_TRANSIT_MARKET_FACTOR)
                )
                * (1.0 - (disruption_risk * 0.45))
            )

        hub_value = 0.0
        if depth == 0 or route_role == "corridor":
            hub_value = (
                throughput
                * route_factor
                * bottleneck
                * (
                    TRADE_HUB_BASE_FACTOR
                    + TRADE_HUB_SETTLEMENT_BONUSES.get(region.settlement_level, 0.0)
                    + (region.market_level * TRADE_HUB_MARKET_FACTOR)
                    + (region.infrastructure_level * TRADE_HUB_INFRASTRUCTURE_FACTOR)
                )
                * (1.0 - (disruption_risk * 0.35))
            )

        trade_bonus = max(0.0, import_value + transit_value + hub_value)
        base_value = max(0.0, float(region.resource_monetized_value or 0.0))
        total_value = base_value + trade_bonus

        region.trade_route_role = route_role
        region.trade_route_parent = str(parent_name) if isinstance(parent_name, str) else None
        region.trade_route_children = children_count
        region.trade_served_regions = int(served_by_region.get(region.name, 0))
        region.trade_throughput = round(throughput, 3)
        region.trade_transit_flow = round(transit_flow, 3)
        region.trade_import_value = round(max(0.0, import_value), 3)
        region.trade_transit_value = round(max(0.0, transit_value), 3)
        region.trade_hub_value = round(max(0.0, hub_value), 3)
        region.trade_value_bonus = round(trade_bonus, 3)
        region.trade_import_reliance = round(
            _clamp(
                max(0.0, import_value) / max(0.1, total_value),
                0.0,
                0.95,
            ),
            3,
        )
        region.trade_disruption_risk = round(disruption_risk, 3)

        total_trade_income += trade_bonus
        total_transit_value += max(0.0, transit_value)
        total_import_value += max(0.0, import_value)
        total_base_value += base_value
        exposure_weight += max(0.1, throughput)
        weighted_exposure += disruption_risk * max(0.1, throughput)

    faction.trade_income = round(total_trade_income, 3)
    faction.trade_transit_value = round(total_transit_value, 3)
    faction.trade_import_dependency = round(
        _clamp(total_import_value / max(0.1, total_base_value + total_trade_income), 0.0, 0.95),
        3,
    )
    faction.trade_corridor_exposure = round(
        _clamp(weighted_exposure / max(0.1, exposure_weight), 0.0, 0.95),
        3,
    )


def get_region_internal_distribution_state(
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> RouteState:
    if world is None or region.owner is None or region.owner not in world.factions:
        return {
            "factor": 0.55,
            "isolation": 0.45,
            "depth": None,
            "cost": 0.0,
            "anchor": None,
            "bottleneck": 0.65,
        }

    route_state = None
    if faction_route_map is not None:
        route_state = faction_route_map.get(region.name)
    if route_state is None:
        route_state = build_faction_resource_route_map(world, region.owner).get(region.name)

    if route_state is None:
        return {
            "factor": 0.38,
            "isolation": 0.62,
            "depth": None,
            "cost": 0.0,
            "anchor": None,
            "bottleneck": 0.4,
        }

    status = get_region_core_status(region)
    local_factor = 1.0
    if status == "frontier":
        local_factor -= 0.08
    elif status == "core":
        local_factor -= 0.02

    if region.settlement_level == "wild":
        local_factor -= 0.12
    elif region.settlement_level == "rural":
        local_factor -= 0.05

    local_factor -= min(0.18, region.unrest * 0.015)
    average_damage = sum(region.resource_damage.values()) / max(1, len(ALL_RESOURCES))
    local_factor -= min(0.12, average_damage * 0.5)
    local_factor += min(0.12, region.infrastructure_level * 0.06)
    local_factor += min(0.14, region.storehouse_level * 0.06)
    local_factor = _clamp(local_factor, 0.58, 1.02)

    route_cost = float(route_state.get("cost", 0.0) or 0.0)
    route_bottleneck = float(route_state.get("bottleneck", 0.7) or 0.7)
    if int(route_state.get("depth", 0) or 0) <= 0:
        path_factor = 1.0
    else:
        path_factor = _clamp(1.02 - (route_cost * 0.11), 0.42, 0.96)
    bottleneck_factor = _clamp(0.5 + (route_bottleneck * 0.5), 0.48, 1.0)

    factor = _clamp(local_factor * path_factor * bottleneck_factor, 0.28, 1.0)
    return {
        "factor": round(factor, 3),
        "isolation": round(1.0 - factor, 3),
        "depth": (
            int(route_state["depth"])
            if route_state.get("depth") is not None
            else None
        ),
        "cost": round(route_cost, 3),
        "anchor": route_state.get("anchor"),
        "bottleneck": round(route_bottleneck, 3),
    }


def get_region_internal_distribution_factor(
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> float:
    distribution_state = get_region_internal_distribution_state(
        region,
        world,
        faction_route_map=faction_route_map,
    )
    region.resource_isolation_factor = float(distribution_state["isolation"])
    region.resource_route_depth = (
        int(distribution_state["depth"])
        if distribution_state["depth"] is not None
        else None
    )
    region.resource_route_cost = float(distribution_state["cost"] or 0.0)
    region.resource_route_anchor = (
        str(distribution_state["anchor"])
        if distribution_state["anchor"] is not None
        else None
    )
    region.resource_route_bottleneck = float(distribution_state["bottleneck"] or 0.0)
    return float(distribution_state["factor"])


def get_region_effective_resource_output(
    region: Region,
    world: WorldState | None = None,
    raw_output: dict[str, float] | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> dict[str, float]:
    retained_output = get_region_retained_resource_output(
        region,
        world,
        raw_output=raw_output or region.resource_retained_output or region.resource_output,
    )
    distribution_factor = get_region_internal_distribution_factor(
        region,
        world,
        faction_route_map=faction_route_map,
    )
    effective_output = build_empty_resource_map()
    for resource_name, amount in retained_output.items():
        resource_specific_factor = distribution_factor
        route_bottleneck = max(0.35, float(region.resource_route_bottleneck or 0.35))
        if resource_name in EXTRACTIVE_RESOURCES and get_region_core_status(region) == "frontier":
            resource_specific_factor *= 0.88
        if resource_name in EXTRACTIVE_RESOURCES or resource_name == RESOURCE_TIMBER:
            resource_specific_factor *= _clamp(
                0.66
                + (route_bottleneck * 0.4)
                + (region.storehouse_level * 0.05)
                + (region.road_level * 0.02),
                0.58,
                1.05,
            )
        elif resource_name in FOOD_RESOURCES or resource_name == RESOURCE_HORSES:
            resource_specific_factor *= _clamp(0.78 + (route_bottleneck * 0.24), 0.72, 1.0)
        elif resource_name in COMMERCIAL_RESOURCES:
            resource_specific_factor *= _clamp(
                0.72
                + (route_bottleneck * 0.26)
                + (region.road_level * 0.03),
                0.68,
                1.08,
            )
        effective_output[resource_name] = round(
            amount * resource_specific_factor,
            3,
        )
    return normalize_resource_map(effective_output)


def get_region_resource_retention_factor(region: Region, resource_name: str) -> float:
    status = get_region_core_status(region)
    factor = RESOURCE_RETENTION_BASE_FACTOR
    factor += RESOURCE_RETENTION_SETTLEMENT_BONUSES.get(region.settlement_level, 0.0)
    factor += min(0.16, region.infrastructure_level * RESOURCE_RETENTION_INFRASTRUCTURE_FACTOR)
    if resource_name in EXTRACTIVE_RESOURCES or resource_name == RESOURCE_TIMBER:
        factor += min(0.28, region.storehouse_level * RESOURCE_RETENTION_STOREHOUSE_FACTOR)
    if resource_name in FOOD_RESOURCES:
        factor += min(0.24, region.granary_level * RESOURCE_RETENTION_GRANARY_FACTOR)
        factor += min(0.08, region.storehouse_level * 0.05)
    if resource_name in COMMERCIAL_RESOURCES:
        factor += min(0.1, region.storehouse_level * 0.08)
    if status == "homeland":
        factor += 0.04
    elif status == "core":
        factor += 0.02
    factor -= min(0.14, region.unrest * 0.012)
    if region.unrest_event_level == "disturbance":
        factor -= 0.04
    elif region.unrest_event_level == "crisis":
        factor -= 0.08
    return _clamp(factor, 0.38, 1.0)


def get_region_retained_resource_output(
    region: Region,
    world: WorldState | None = None,
    raw_output: dict[str, float] | None = None,
) -> dict[str, float]:
    raw_output = normalize_resource_map(raw_output or region.resource_output)
    retained_output = build_empty_resource_map()
    for resource_name, amount in raw_output.items():
        damage_penalty = 1.0 - min(
            0.42,
            region.resource_damage.get(resource_name, 0.0) * 0.62,
        )
        retained_output[resource_name] = round(
            amount
            * get_region_resource_retention_factor(region, resource_name)
            * damage_penalty,
            3,
        )
    return normalize_resource_map(retained_output)


def get_region_monetization_factor(
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> float:
    factor = RESOURCE_MONETIZATION_SETTLEMENT_BASE.get(region.settlement_level, 0.38)
    factor += min(0.34, region.market_level * RESOURCE_MONETIZATION_MARKET_FACTOR)
    factor += min(0.08, region.infrastructure_level * RESOURCE_MONETIZATION_INFRASTRUCTURE_FACTOR)
    factor += min(0.08, region.road_level * RESOURCE_MONETIZATION_ROAD_FACTOR)
    factor += min(0.06, region.storehouse_level * RESOURCE_MONETIZATION_STOREHOUSE_FACTOR)
    if region.owner is not None:
        factor += min(0.1, region.integration_score * 0.01)
    status = get_region_core_status(region)
    if status == "homeland":
        factor += RESOURCE_MONETIZATION_HOMELAND_BONUS
    elif status == "core":
        factor += RESOURCE_MONETIZATION_CORE_BONUS
    distribution_state = get_region_internal_distribution_state(
        region,
        world,
        faction_route_map=faction_route_map,
    )
    factor += min(0.14, float(distribution_state["factor"] or 0.0) * RESOURCE_MONETIZATION_ROUTE_FACTOR)
    factor += min(0.08, float(distribution_state["bottleneck"] or 0.0) * RESOURCE_MONETIZATION_BOTTLENECK_FACTOR)
    factor -= min(0.18, region.unrest * 0.015)
    if region.unrest_event_level == "disturbance":
        factor -= 0.04
    elif region.unrest_event_level == "crisis":
        factor -= 0.08
    return _clamp(factor, 0.18, 1.25)


def _get_monetized_value_from_output(
    output: dict[str, float],
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> float:
    base_value = sum(
        amount * {
            RESOURCE_GRAIN: 0.82,
            RESOURCE_LIVESTOCK: 0.88,
            RESOURCE_HORSES: 0.95,
            RESOURCE_WILD_FOOD: 0.58,
            RESOURCE_TIMBER: 0.9,
            RESOURCE_COPPER: 1.48,
            RESOURCE_STONE: 0.86,
            RESOURCE_SALT: 1.24,
            RESOURCE_TEXTILES: 1.18,
        }.get(resource_name, 1.0)
        for resource_name, amount in output.items()
    )
    return round(
        base_value
        * get_region_monetization_factor(
            region,
            world,
            faction_route_map=faction_route_map,
        ),
        2,
    )


def refresh_region_resource_state(
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> None:
    ensure_region_resource_state(region)
    region.resource_output = get_region_resource_output(region, world)
    region.resource_retained_output = get_region_retained_resource_output(
        region,
        world,
        raw_output=region.resource_output,
    )
    region.resource_routed_output = get_region_effective_resource_output(
        region,
        world,
        raw_output=region.resource_retained_output,
        faction_route_map=faction_route_map,
    )
    region.resource_effective_output = normalize_resource_map(region.resource_routed_output)
    region.resource_monetized_value = _get_monetized_value_from_output(
        region.resource_routed_output if region.owner is not None else region.resource_retained_output,
        region,
        world,
        faction_route_map=faction_route_map,
    )
    region.resources = get_legacy_region_resource_value(
        region.resource_effective_output if region.owner is not None else region.resource_retained_output,
        fixed_endowments=region.resource_fixed_endowments,
        wild_endowments=region.resource_wild_endowments,
        suitability=region.resource_suitability,
        established=region.resource_established,
    )


def get_region_resource_output(region: Region, world: WorldState | None = None) -> dict[str, float]:
    ensure_region_resource_state(region)
    workforce_factor = get_region_resource_workforce_factor(region)
    integration_factor = get_region_resource_integration_factor(region)
    unrest_factor = get_region_resource_unrest_factor(region)
    climate_factor = get_region_resource_climate_factor(region, world)
    output = build_empty_resource_map()

    for resource_name in DOMESTICABLE_RESOURCES:
        suitability = region.resource_suitability.get(resource_name, 0.0)
        established = region.resource_established.get(resource_name, 0.0)
        if suitability <= 0 or established <= 0:
            continue
        output[resource_name] = round(
            RESOURCE_BASE_OUTPUT[resource_name]
            * suitability
            * established
            * workforce_factor
            * get_region_resource_development_factor(region, resource_name)
            * integration_factor
            * unrest_factor
            * climate_factor,
            3,
        )

    for resource_name in WILD_RESOURCES:
        endowment = region.resource_wild_endowments.get(resource_name, 0.0)
        if endowment <= 0:
            continue
        output[resource_name] = round(
            RESOURCE_BASE_OUTPUT[resource_name]
            * endowment
            * (0.5 + (workforce_factor * 0.55))
            * get_region_resource_development_factor(region, resource_name)
            * unrest_factor,
            3,
        )

    for resource_name in EXTRACTIVE_RESOURCES:
        endowment = region.resource_fixed_endowments.get(resource_name, 0.0)
        if endowment <= 0:
            continue
        output[resource_name] = round(
            RESOURCE_BASE_OUTPUT[resource_name]
            * endowment
            * workforce_factor
            * get_region_resource_development_factor(region, resource_name)
            * integration_factor
            * unrest_factor,
            3,
        )

    return normalize_resource_map(output)


def _get_taxable_value_from_output(output: dict[str, float]) -> float:
    return round(
        sum(
            amount * {
                RESOURCE_GRAIN: 1.1,
                RESOURCE_LIVESTOCK: 1.0,
                RESOURCE_HORSES: 0.9,
                RESOURCE_WILD_FOOD: 0.9,
                RESOURCE_TIMBER: 0.85,
                RESOURCE_COPPER: 1.35,
                RESOURCE_STONE: 0.8,
                RESOURCE_SALT: 1.18,
                RESOURCE_TEXTILES: 1.15,
            }.get(resource_name, 1.0)
            for resource_name, amount in output.items()
        ),
        2,
    )


def get_region_taxable_value(
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> float:
    trade_value_bonus = round(max(0.0, float(region.trade_value_bonus or 0.0)), 2)
    if region.resource_monetized_value > 0:
        return round(float(region.resource_monetized_value) + trade_value_bonus, 2)

    if region.resources > 0 and world is None:
        return float(region.resources)

    raw_output = get_region_resource_output(region, world)
    retained_output = get_region_retained_resource_output(
        region,
        world,
        raw_output=raw_output,
    )
    routed_output = (
        get_region_effective_resource_output(
            region,
            world,
            raw_output=retained_output,
            faction_route_map=faction_route_map,
        )
        if world is not None
        else retained_output
    )
    return round(
        _get_monetized_value_from_output(
        normalize_resource_map(routed_output),
        region,
        world,
        faction_route_map=faction_route_map,
        )
        + trade_value_bonus,
        2,
    )


def get_region_effective_income(region: Region, world: WorldState | None = None) -> int:
    income_factor = get_region_income_factor(region)
    base_value = float(get_region_taxable_value(region, world))
    base_value *= get_region_unrest_income_factor(region)
    if world is not None and region.owner in world.factions:
        income_factor *= get_faction_income_modifier(world.factions[region.owner])
    return int(round(base_value * income_factor))


def get_region_maintenance_cost(region: Region, world: WorldState | None = None) -> int:
    status = get_region_core_status(region)
    if status == "frontier":
        base_cost = REGION_MAINTENANCE_COST + FRONTIER_MAINTENANCE_SURCHARGE
    else:
        base_cost = REGION_MAINTENANCE_COST
    if world is None:
        unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
        unrest_factor = 1.0 + ((UNREST_MAINTENANCE_MAX_FACTOR - 1.0) * unrest_ratio)
        return int(ceil(base_cost * unrest_factor))
    if region.owner in world.factions:
        base_cost *= get_faction_maintenance_modifier(world.factions[region.owner])
    climate_factor = get_region_climate_maintenance_factor(region, world)
    unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
    unrest_factor = 1.0 + ((UNREST_MAINTENANCE_MAX_FACTOR - 1.0) * unrest_ratio)
    return int(ceil(base_cost * climate_factor * unrest_factor))


def get_faction_resource_demand(
    world: WorldState,
    faction_name: str,
) -> dict[str, float]:
    demand = {
        **build_empty_resource_map(),
        **build_empty_capacity_map(),
    }
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]
    if not owned_regions or faction_name not in world.factions:
        return demand

    total_population = sum(region.population for region in owned_regions)
    rural_regions = sum(1 for region in owned_regions if region.settlement_level == "rural")
    town_regions = sum(1 for region in owned_regions if region.settlement_level == "town")
    city_regions = sum(1 for region in owned_regions if region.settlement_level == "city")
    faction = world.factions[faction_name]
    war_bias = max(0.0, faction.doctrine_profile.war_posture - 0.5)

    frontier_regions = sum(1 for region in owned_regions if get_region_core_status(region) == "frontier")
    avg_infrastructure = (
        sum(region.infrastructure_level for region in owned_regions) / max(1, len(owned_regions))
    )
    food_demand = max(0.8, total_population / 138.0)
    mobility_demand = max(0.0, len(owned_regions) * 0.18 + frontier_regions * 0.1 + war_bias * 1.2)
    metal_demand = max(
        0.0,
        len(owned_regions) * 0.16
        + town_regions * 0.12
        + city_regions * 0.28
        + (0.25 if faction.polity_tier in {"chiefdom", "state"} else 0.0)
        + war_bias * 0.5,
    )
    construction_demand = max(
        0.0,
        len(owned_regions) * 0.18
        + rural_regions * 0.04
        + town_regions * 0.18
        + city_regions * 0.38,
    )
    infrastructure_gap = max(0.0, 1.2 - avg_infrastructure)
    construction_demand += infrastructure_gap * len(owned_regions) * 0.18
    commercial_demand = max(
        0.0,
        len(owned_regions) * 0.06
        + town_regions * 0.16
        + city_regions * 0.34,
    )

    demand[CAPACITY_FOOD_SECURITY] = round(food_demand, 3)
    demand[CAPACITY_MOBILITY] = round(mobility_demand, 3)
    demand[CAPACITY_METAL] = round(metal_demand, 3)
    demand[CAPACITY_CONSTRUCTION] = round(construction_demand, 3)
    demand[RESOURCE_GRAIN] = round(max(0.25, food_demand * 0.42), 3)
    demand[RESOURCE_LIVESTOCK] = round(max(0.18, food_demand * 0.24), 3)
    demand[RESOURCE_HORSES] = round(mobility_demand, 3)
    demand[RESOURCE_COPPER] = round(metal_demand, 3)
    demand[RESOURCE_STONE] = round(construction_demand * 0.52, 3)
    demand[RESOURCE_TIMBER] = round(construction_demand * 0.36, 3)
    demand[RESOURCE_WILD_FOOD] = round(max(0.15, food_demand * 0.18), 3)
    demand[RESOURCE_SALT] = round(
        max(0.12, food_demand * 0.16 + town_regions * 0.04 + city_regions * 0.08),
        3,
    )
    demand[RESOURCE_TEXTILES] = round(max(0.1, commercial_demand), 3)
    demand[CAPACITY_TAXABLE_VALUE] = round(
        food_demand + mobility_demand + metal_demand + construction_demand + commercial_demand,
        3,
    )
    return demand


def get_faction_food_storage_capacity(
    world: WorldState,
    faction_name: str,
) -> float:
    return round(
        sum(
            get_region_food_storage_capacity(region)
            for region in world.regions.values()
            if region.owner == faction_name
        ),
        3,
    )


def get_region_food_storage_capacity(region: Region) -> float:
    capacity = FOOD_STORAGE_BASE_PER_REGION
    capacity += {
        "rural": FOOD_STORAGE_RURAL_BONUS,
        "town": FOOD_STORAGE_TOWN_BONUS,
        "city": FOOD_STORAGE_CITY_BONUS,
    }.get(region.settlement_level, 0.0)
    if region.granary_level > 0:
        capacity += region.granary_level * (
            FOOD_STORAGE_GRANARY_FACTOR
            + (region.infrastructure_level * FOOD_STORAGE_INFRASTRUCTURE_FACTOR)
            + (region.agriculture_level * FOOD_STORAGE_AGRICULTURE_FACTOR)
        )
    status = get_region_core_status(region)
    if status == "homeland":
        capacity += FOOD_STORAGE_HOMELAND_BONUS
    elif status == "core":
        capacity += FOOD_STORAGE_CORE_BONUS
    return round(capacity, 3)


def get_faction_food_spoilage_rate(
    world: WorldState,
    faction_name: str,
) -> float:
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]
    if not owned_regions:
        return FOOD_STORAGE_BASE_SPOILAGE

    total_stored = sum(region.food_stored for region in owned_regions)
    if total_stored <= 0:
        return round(
            sum(get_region_food_spoilage_rate(region) for region in owned_regions) / max(1, len(owned_regions)),
            3,
        )

    weighted_rate = sum(
        region.food_stored * get_region_food_spoilage_rate(region)
        for region in owned_regions
    ) / total_stored
    return round(weighted_rate, 3)


def get_region_food_spoilage_rate(region: Region) -> float:
    spoilage_rate = FOOD_STORAGE_BASE_SPOILAGE - (
        region.infrastructure_level * FOOD_STORAGE_INFRASTRUCTURE_SPOILAGE_REDUCTION
    ) - (
        region.granary_level * FOOD_STORAGE_GRANARY_SPOILAGE_REDUCTION
    )
    return round(
        _clamp(spoilage_rate, FOOD_STORAGE_MIN_SPOILAGE, FOOD_STORAGE_BASE_SPOILAGE),
        3,
    )


def get_faction_salt_preservation_modifier(
    world: WorldState,
    faction_name: str,
) -> float:
    faction = world.factions.get(faction_name)
    if faction is None:
        return 0.0
    salt_shortage = max(0.0, faction.resource_shortages.get(RESOURCE_SALT, 0.0))
    if salt_shortage <= 0:
        salt_access = max(0.0, faction.resource_effective_access.get(RESOURCE_SALT, 0.0))
        return round(-min(0.012, salt_access * 0.01), 3)
    shortage_ratio = salt_shortage / max(
        0.1,
        salt_shortage + max(0.0, faction.resource_effective_access.get(RESOURCE_SALT, 0.0)),
    )
    return round(min(0.045, shortage_ratio * 0.045), 3)


def get_region_food_demand(region: Region) -> float:
    if region.owner is None or region.population <= 0:
        return 0.0
    return round(max(0.2, region.population / 138.0), 3)


def _build_faction_derived_capacity(
    world: WorldState,
    faction_name: str,
    faction_route_maps: dict[str, dict[str, RouteState]],
) -> dict[str, float]:
    effective_access = world.factions[faction_name].resource_effective_access
    derived_capacity = build_empty_capacity_map()
    derived_capacity[CAPACITY_FOOD_SECURITY] = round(
        effective_access[RESOURCE_GRAIN]
        + (effective_access[RESOURCE_LIVESTOCK] * 0.9)
        + (effective_access[RESOURCE_WILD_FOOD] * 0.7)
        + (effective_access[RESOURCE_SALT] * 0.1),
        3,
    )
    derived_capacity[CAPACITY_MOBILITY] = round(effective_access[RESOURCE_HORSES], 3)
    derived_capacity[CAPACITY_METAL] = round(effective_access[RESOURCE_COPPER], 3)
    derived_capacity[CAPACITY_CONSTRUCTION] = round(
        effective_access[RESOURCE_TIMBER] + effective_access[RESOURCE_STONE],
        3,
    )
    derived_capacity[CAPACITY_TAXABLE_VALUE] = round(
        sum(
            get_region_taxable_value(
                region,
                world,
                faction_route_map=faction_route_maps.get(faction_name, {}),
            )
            for region in world.regions.values()
            if region.owner == faction_name
        ),
        3,
    )
    return normalize_capacity_map(derived_capacity)


def _build_faction_resource_shortages(
    faction: Faction,
    demand: dict[str, float],
) -> dict[str, float]:
    shortages = {
        **build_empty_resource_map(),
        **build_empty_capacity_map(),
    }
    for key, demand_value in demand.items():
        access_value = (
            faction.derived_capacity.get(key, 0.0)
            if key in ALL_CAPACITIES
            else faction.resource_effective_access.get(key, 0.0)
        )
        if key == CAPACITY_FOOD_SECURITY:
            shortages[key] = round(
                max(
                    max(0.0, demand_value - access_value),
                    faction.food_deficit,
                ),
                3,
            )
            continue
        shortages[key] = round(max(0.0, demand_value - access_value), 3)
    return shortages


def _update_faction_food_aggregate(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]
    faction.food_storage_capacity = round(sum(region.food_storage_capacity for region in owned_regions), 3)
    faction.food_stored = round(sum(region.food_stored for region in owned_regions), 3)
    faction.food_produced = round(sum(region.food_produced for region in owned_regions), 3)
    faction.food_consumption = round(sum(region.food_consumption for region in owned_regions), 3)
    faction.food_balance = round(sum(region.food_balance for region in owned_regions), 3)
    faction.food_deficit = round(sum(region.food_deficit for region in owned_regions), 3)
    faction.food_spoilage = round(sum(region.food_spoilage for region in owned_regions), 3)
    faction.food_overflow = round(sum(region.food_overflow for region in owned_regions), 3)


def update_faction_resource_economy(
    world: WorldState,
    *,
    advance_resources: bool = False,
) -> None:
    faction_route_maps = _build_world_resource_route_maps(world)
    faction_gross_totals = {
        faction_name: build_empty_resource_map()
        for faction_name in world.factions
    }
    faction_effective_totals = {
        faction_name: build_empty_resource_map()
        for faction_name in world.factions
    }

    for region in world.regions.values():
        ensure_region_resource_state(region)
        ensure_region_food_state(region)
        if advance_resources:
            advance_region_domesticable_resources(region)
        refresh_region_resource_state(
            region,
            world,
            faction_route_map=faction_route_maps.get(region.owner or "", {}),
        )
        if region.owner is None:
            region.trade_route_role = "local"
            region.trade_route_parent = None
            region.trade_route_children = 0
            region.trade_served_regions = 0
            region.trade_throughput = 0.0
            region.trade_transit_flow = 0.0
            region.trade_import_value = 0.0
            region.trade_transit_value = 0.0
            region.trade_hub_value = 0.0
            region.trade_value_bonus = 0.0
            region.trade_import_reliance = 0.0
            region.trade_disruption_risk = 0.0
            region.food_storage_capacity = 0.0
            region.food_stored = 0.0
            region.food_produced = 0.0
            region.food_consumption = 0.0
            region.food_balance = 0.0
            region.food_deficit = 0.0
            region.food_spoilage = 0.0
            region.food_overflow = 0.0
        else:
            region.food_storage_capacity = get_region_food_storage_capacity(region)
            region.food_stored = round(
                min(region.food_stored, region.food_storage_capacity),
                3,
            )
            region.food_produced = round(
                region.resource_output.get(RESOURCE_GRAIN, 0.0)
                + region.resource_output.get(RESOURCE_LIVESTOCK, 0.0)
                + region.resource_output.get(RESOURCE_WILD_FOOD, 0.0),
                3,
            )
            region.food_consumption = get_region_food_demand(region)
        if region.owner in faction_gross_totals:
            for resource_name, amount in region.resource_output.items():
                faction_gross_totals[region.owner][resource_name] += amount
            for resource_name, amount in region.resource_effective_output.items():
                faction_effective_totals[region.owner][resource_name] += amount

    for faction_name, faction in world.factions.items():
        _ensure_faction_resource_state(faction)
        _apply_faction_trade_state(
            world,
            faction_name,
            faction_route_maps.get(faction_name, {}),
        )
        faction.resource_gross_output = normalize_resource_map(faction_gross_totals[faction_name])
        faction.resource_effective_access = normalize_resource_map(faction_effective_totals[faction_name])
        faction.resource_isolated_output = normalize_resource_map({
            resource_name: round(
                faction.resource_gross_output.get(resource_name, 0.0)
                - faction.resource_effective_access.get(resource_name, 0.0),
                3,
            )
            for resource_name in ALL_RESOURCES
        })
        faction.resource_access = normalize_resource_map(faction.resource_effective_access)
        _update_faction_food_aggregate(world, faction_name)
        faction.derived_capacity = _build_faction_derived_capacity(
            world,
            faction_name,
            faction_route_maps,
        )
        demand = get_faction_resource_demand(world, faction_name)
        faction.resource_shortages = _build_faction_resource_shortages(faction, demand)


def apply_turn_food_economy(world: WorldState) -> None:
    for region in world.regions.values():
        ensure_region_food_state(region)
        if region.owner is None:
            region.food_storage_capacity = 0.0
            region.food_stored = 0.0
            region.food_produced = 0.0
            region.food_consumption = 0.0
            region.food_balance = 0.0
            region.food_deficit = 0.0
            region.food_spoilage = 0.0
            region.food_overflow = 0.0
            continue

        food_produced = round(
            region.resource_output.get(RESOURCE_GRAIN, 0.0)
            + region.resource_output.get(RESOURCE_LIVESTOCK, 0.0)
            + region.resource_output.get(RESOURCE_WILD_FOOD, 0.0),
            3,
        )
        food_demand = get_region_food_demand(region)
        food_storage_capacity = get_region_food_storage_capacity(region)
        food_stored = min(region.food_stored, food_storage_capacity)
        spoilage_rate = get_region_food_spoilage_rate(region) + get_faction_salt_preservation_modifier(
            world,
            region.owner,
        )
        spoilage_rate = _clamp(
            spoilage_rate,
            FOOD_STORAGE_MIN_SPOILAGE,
            FOOD_STORAGE_BASE_SPOILAGE + 0.05,
        )
        food_spoilage = round(min(food_stored, food_stored * spoilage_rate), 3)
        usable_stored_food = round(max(0.0, food_stored - food_spoilage), 3)
        available_food = round(food_produced + usable_stored_food, 3)
        net_food = round(available_food - food_demand, 3)
        food_deficit = round(max(0.0, -net_food), 3)
        stored_after_consumption = round(max(0.0, net_food), 3)
        food_overflow = round(
            max(0.0, stored_after_consumption - food_storage_capacity),
            3,
        )

        region.food_storage_capacity = round(food_storage_capacity, 3)
        region.food_stored = round(
            min(food_storage_capacity, stored_after_consumption),
            3,
        )
        region.food_produced = food_produced
        region.food_consumption = round(food_demand, 3)
        region.food_balance = net_food
        region.food_deficit = food_deficit
        region.food_spoilage = food_spoilage
        region.food_overflow = food_overflow

    for faction_name, faction in world.factions.items():
        _ensure_faction_resource_state(faction)
        _update_faction_food_aggregate(world, faction_name)


def initialize_region_resources(world: WorldState) -> None:
    for region in world.regions.values():
        seed_region_resource_profile(region)
    update_faction_resource_economy(world, advance_resources=False)


def apply_region_resource_damage(
    region: Region,
    damage_by_resource: dict[str, float],
) -> None:
    ensure_region_resource_state(region)
    for resource_name, damage_amount in damage_by_resource.items():
        current_damage = region.resource_damage.get(resource_name, 0.0)
        region.resource_damage[resource_name] = round(
            _clamp(current_damage + damage_amount, 0.0, RESOURCE_MAX_DAMAGE),
            3,
        )
