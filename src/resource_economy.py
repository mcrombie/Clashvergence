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
    DOMESTICABLE_RESOURCES,
    EXTRACTIVE_RESOURCES,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_STONE,
    RESOURCE_TIMBER,
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
    RESOURCE_HORSES: 1.9,
    RESOURCE_WILD_FOOD: 1.8,
    RESOURCE_TIMBER: 1.5,
    RESOURCE_COPPER: 1.7,
    RESOURCE_STONE: 1.55,
}
RESOURCE_GROWTH_STEP = {
    RESOURCE_GRAIN: 0.04,
    RESOURCE_HORSES: 0.025,
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
RESOURCE_EXTRACTIVE_UNDEVELOPED_FACTOR = 0.18
RESOURCE_EXTRACTIVE_SITE_LEVEL_FACTOR = 0.95
RESOURCE_EXTRACTIVE_SUPPORT_LEVEL_FACTOR = 0.16

RouteState = dict[str, float | int | str | None]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


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
        region.resource_effective_output = normalize_resource_map(region.resource_effective_output)
        region.resource_damage = normalize_resource_map(region.resource_damage)
    region.resource_effective_output = normalize_resource_map(region.resource_effective_output)
    region.resource_damage = normalize_resource_map(region.resource_damage)
    region.resource_isolation_factor = round(float(region.resource_isolation_factor or 0.0), 3)
    region.resource_route_depth = (
        int(region.resource_route_depth)
        if region.resource_route_depth is not None
        else None
    )
    region.resource_route_cost = round(float(region.resource_route_cost or 0.0), 3)
    region.resource_route_anchor = region.resource_route_anchor or None
    region.resource_route_bottleneck = round(float(region.resource_route_bottleneck or 0.0), 3)
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
        return 1.0 + (region.agriculture_level * 0.35) + (region.infrastructure_level * 0.1)
    if resource_name == RESOURCE_HORSES:
        return 1.0 + (region.pastoral_level * 0.35) + (region.infrastructure_level * 0.08)
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
    if resource_name == RESOURCE_HORSES and region.pastoral_level < 0.1:
        decay += 0.007
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
            elif resource_name == RESOURCE_HORSES:
                growth += region.pastoral_level * 0.01
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
    raw_output = normalize_resource_map(raw_output or region.resource_output)
    distribution_factor = get_region_internal_distribution_factor(
        region,
        world,
        faction_route_map=faction_route_map,
    )
    effective_output = build_empty_resource_map()
    for resource_name, amount in raw_output.items():
        resource_specific_factor = distribution_factor
        route_bottleneck = max(0.35, float(region.resource_route_bottleneck or 0.35))
        if resource_name in EXTRACTIVE_RESOURCES and get_region_core_status(region) == "frontier":
            resource_specific_factor *= 0.88
        if resource_name in EXTRACTIVE_RESOURCES:
            resource_specific_factor *= _clamp(0.68 + (route_bottleneck * 0.4), 0.62, 1.0)
        elif resource_name in {RESOURCE_GRAIN, RESOURCE_HORSES}:
            resource_specific_factor *= _clamp(0.78 + (route_bottleneck * 0.24), 0.72, 1.0)
        damage_penalty = 1.0 - min(
            0.4,
            region.resource_damage.get(resource_name, 0.0) * 0.6,
        )
        effective_output[resource_name] = round(
            amount * resource_specific_factor * damage_penalty,
            3,
        )
    return normalize_resource_map(effective_output)


def refresh_region_resource_state(
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, RouteState] | None = None,
) -> None:
    ensure_region_resource_state(region)
    region.resource_output = get_region_resource_output(region, world)
    region.resource_effective_output = get_region_effective_resource_output(
        region,
        world,
        raw_output=region.resource_output,
        faction_route_map=faction_route_map,
    )
    region.resources = get_legacy_region_resource_value(
        region.resource_effective_output if region.owner is not None else region.resource_output,
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
                RESOURCE_HORSES: 0.9,
                RESOURCE_WILD_FOOD: 0.9,
                RESOURCE_TIMBER: 0.85,
                RESOURCE_COPPER: 1.35,
                RESOURCE_STONE: 0.8,
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
    if region.resources > 0:
        return float(region.resources)

    raw_output = get_region_resource_output(region, world)
    output = (
        get_region_effective_resource_output(
            region,
            world,
            raw_output=raw_output,
            faction_route_map=faction_route_map,
        )
        if world is not None
        else raw_output
    )
    return _get_taxable_value_from_output(normalize_resource_map(output))


def get_region_effective_income(region: Region, world: WorldState | None = None) -> int:
    income_factor = get_region_income_factor(region)
    base_value = float(region.resources)
    if base_value <= 0:
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

    demand[CAPACITY_FOOD_SECURITY] = round(food_demand, 3)
    demand[CAPACITY_MOBILITY] = round(mobility_demand, 3)
    demand[CAPACITY_METAL] = round(metal_demand, 3)
    demand[CAPACITY_CONSTRUCTION] = round(construction_demand, 3)
    demand[RESOURCE_GRAIN] = round(max(0.3, food_demand * 0.65), 3)
    demand[RESOURCE_HORSES] = round(mobility_demand, 3)
    demand[RESOURCE_COPPER] = round(metal_demand, 3)
    demand[RESOURCE_STONE] = round(construction_demand * 0.55, 3)
    demand[RESOURCE_TIMBER] = round(construction_demand * 0.45, 3)
    demand[RESOURCE_WILD_FOOD] = round(max(0.2, food_demand * 0.35), 3)
    demand[CAPACITY_TAXABLE_VALUE] = round(food_demand + mobility_demand + metal_demand + construction_demand, 3)
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
        effective_access[RESOURCE_GRAIN] + effective_access[RESOURCE_WILD_FOOD],
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
            + region.resource_output.get(RESOURCE_WILD_FOOD, 0.0),
            3,
        )
        food_demand = get_region_food_demand(region)
        food_storage_capacity = get_region_food_storage_capacity(region)
        food_stored = min(region.food_stored, food_storage_capacity)
        spoilage_rate = get_region_food_spoilage_rate(region)
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
