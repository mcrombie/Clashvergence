from __future__ import annotations

from copy import deepcopy
from heapq import heappop, heappush
from math import ceil
import random
import re

from src.config import (
    CLIMATE_ATTACK_PROJECTION_MAX_PENALTY,
    CLIMATE_CORE_INTEGRATION_CLIMATE_FACTOR,
    CLIMATE_FRONTIER_INTEGRATION_CLIMATE_FACTOR,
    CLIMATE_INCOME_MAX_FACTOR,
    CLIMATE_INCOME_MIN_FACTOR,
    CLIMATE_MAINTENANCE_MAX_FACTOR,
    CLIMATE_MAINTENANCE_MIN_FACTOR,
    CORE_INCOME_FACTOR,
    DIPLOMACY_RIVAL_THRESHOLD,
    ETHNIC_CLAIM_INTEGRATION_BONUS,
    ETHNIC_CLAIM_UNREST_REDUCTION,
    ETHNIC_INTEGRATION_MIN_MULTIPLIER,
    ETHNIC_UNREST_CALMING_EFFECT,
    ETHNIC_UNREST_CALMING_THRESHOLD,
    ETHNIC_UNREST_LOW_AFFINITY_PRESSURE,
    ETHNIC_UNREST_NEUTRAL_THRESHOLD,
    ETHNIC_UNREST_SEVERE_AFFINITY_PRESSURE,
    ETHNIC_UNREST_SEVERE_THRESHOLD,
    REGIME_CONTESTATION_CORE_UNREST_BONUS,
    REGIME_CONTESTATION_HOMELAND_UNREST_BONUS,
    REGIME_CONTESTATION_UNREST_BASE,
    REGIME_AGITATION_CLAIMANT_BONUS,
    REGIME_AGITATION_HEAVY_BACKLASH_MULTIPLIER,
    REGIME_AGITATION_HEAVY_COST_MULTIPLIER,
    REGIME_AGITATION_HEAVY_MODE_THRESHOLD,
    REGIME_AGITATION_HEAVY_PRESSURE_MULTIPLIER,
    REGIME_AGITATION_INSULARITY_FACTOR,
    REGIME_AGITATION_LOW_BACKLASH_MULTIPLIER,
    REGIME_AGITATION_LOW_COST_MULTIPLIER,
    REGIME_AGITATION_LOW_MODE_THRESHOLD,
    REGIME_AGITATION_LOW_PRESSURE_MULTIPLIER,
    REGIME_AGITATION_MAX,
    REGIME_AGITATION_MAX_SPONSOR_FACTOR,
    REGIME_AGITATION_MIN_SPONSOR_FACTOR,
    REGIME_AGITATION_HOMEFRONT_UNREST_FACTOR,
    REGIME_AGITATION_TREASURY_COST_FACTOR,
    REGIME_AGITATION_TREASURY_FACTOR,
    REGIME_AGITATION_TREASURY_MAX_BONUS,
    REGIME_AGITATION_UNREST_PER_SPONSOR,
    REGIME_AGITATION_WAR_POSTURE_FACTOR,
    FRONTIER_ATTACK_PROJECTION_PENALTY,
    FRONTIER_INCOME_FACTOR,
    FRONTIER_MAINTENANCE_SURCHARGE,
    HOMELAND_INCOME_FACTOR,
    POPULATION_BASE,
    POPULATION_GROWTH_PER_TURN,
    POPULATION_MINIMUM,
    POPULATION_PER_CONNECTION,
    POPULATION_PER_RESOURCE,
    POPULATION_SECESSION_LOSS,
    POPULATION_STARTING_OWNER_BONUS,
    POPULATION_UNOWNED_GROWTH_FACTOR,
    POPULATION_UNREST_CRISIS_LOSS,
    POPULATION_UNREST_GROWTH_PENALTY,
    POLITY_ADVANCEMENT_UNREST_REDUCTION,
    REGION_MAINTENANCE_COST,
    UNREST_ATTACK_PROJECTION_MAX_PENALTY,
    UNREST_CLIMATE_PRESSURE_FACTOR,
    UNREST_CONQUEST_START,
    UNREST_DECAY_PER_TURN,
    UNREST_CRISIS_DURATION,
    UNREST_CRISIS_INCOME_FACTOR,
    UNREST_CRISIS_TREASURY_HIT,
    UNREST_CRITICAL_THRESHOLD,
    UNREST_DISTURBANCE_DURATION,
    UNREST_DISTURBANCE_INCOME_FACTOR,
    UNREST_DISTURBANCE_TREASURY_HIT,
    UNREST_EVENT_ATTACK_PROJECTION_PENALTY,
    UNREST_EXPANSION_START,
    UNREST_FRONTIER_BURDEN_FACTOR,
    UNREST_FRONTIER_PRESSURE,
    UNREST_INCOME_MIN_FACTOR,
    UNREST_INTEGRATION_PRESSURE_FACTOR,
    UNREST_MAINTENANCE_MAX_FACTOR,
    UNREST_MAX,
    UNREST_MODERATE_THRESHOLD,
    REBEL_FULL_INDEPENDENCE_THRESHOLD,
    REBEL_INDEPENDENCE_TREASURY_BONUS,
    REBEL_INDEPENDENCE_PER_EXTRA_REGION,
    REBEL_INDEPENDENCE_PER_TURN,
    REBEL_MATURE_GOVERNMENT_TYPE,
    REBEL_PARENT_RECLAIM_MAX_BONUS,
    REBEL_RECURSIVE_UNREST_REDUCTION,
    REBEL_SECESSION_COOLDOWN_TURNS,
    REBEL_STARTING_TREASURY,
    REBEL_STARTING_UNREST,
    UNREST_SECESSION_CRISIS_TURNS,
    UNREST_SECESSION_RESOURCE_LOSS,
    UNREST_SECESSION_THRESHOLD,
)
from src.diplomacy import seed_rebel_origin_relationship
from src.models import (
    Ethnicity,
    Event,
    Faction,
    FactionIdentity,
    GOVERNMENT_FORMS_BY_TIER,
    LanguageProfile,
    Region,
    WorldState,
    get_default_government_form,
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
    format_resource_map,
    get_legacy_region_resource_value,
    get_region_resource_summary,
    normalize_capacity_map,
    normalize_resource_map,
    seed_region_resource_profile,
)
from src.terrain import get_terrain_profile


HOMELAND_INTEGRATION_SCORE = 10.0
CORE_INTEGRATION_SCORE = 6.0
CONQUEST_INTEGRATION_SCORE = 1.0
PER_TURN_FRONTIER_GAIN = 1.0
PER_TURN_CORE_GAIN = 0.35
SURPLUS_RESOURCE_YIELD = 2.5
SURPLUS_CONNECTION_YIELD = 0.15
SURPLUS_POPULATION_PRESSURE = 90.0
SURPLUS_GROWTH_FACTOR = 0.003
SURPLUS_MAX_GROWTH_BONUS = 0.018
SURPLUS_MIN_GROWTH_PENALTY = -0.012
SETTLEMENT_LEVELS = ("wild", "rural", "town", "city")
POLITY_TIER_ORDER = ("band", "tribe", "chiefdom", "state")
SURPLUS_TERRAIN_PRODUCTIVITY = {
    "plains": 1.6,
    "riverland": 1.8,
    "coast": 0.8,
    "forest": 0.4,
    "hills": 0.2,
    "highland": -0.6,
    "marsh": -0.8,
    "steppe": 1.0,
}
POLITY_TIER_MODIFIERS = {
    "band": {
        "income_factor": 0.75,
        "maintenance_factor": 0.70,
        "integration_factor": 0.65,
        "stability_factor": 0.90,
        "attack_bias": -1,
        "realm_size_unrest_factor": 1.40,
    },
    "tribe": {
        "income_factor": 0.95,
        "maintenance_factor": 0.90,
        "integration_factor": 1.00,
        "stability_factor": 1.00,
        "attack_bias": 0,
        "realm_size_unrest_factor": 1.10,
    },
    "chiefdom": {
        "income_factor": 1.05,
        "maintenance_factor": 1.00,
        "integration_factor": 1.05,
        "stability_factor": 1.08,
        "attack_bias": 1,
        "realm_size_unrest_factor": 0.95,
    },
    "state": {
        "income_factor": 1.15,
        "maintenance_factor": 1.10,
        "integration_factor": 1.15,
        "stability_factor": 1.16,
        "attack_bias": 1,
        "realm_size_unrest_factor": 0.85,
    },
}
GOVERNMENT_FORM_MODIFIERS = {
    "leader": {
        "income_factor": 0.95,
        "stability_factor": 0.92,
        "attack_bias": 1,
        "integration_factor": 0.95,
    },
    "council": {
        "income_factor": 1.00,
        "stability_factor": 1.06,
        "attack_bias": 0,
        "integration_factor": 1.00,
    },
    "assembly": {
        "income_factor": 0.98,
        "stability_factor": 1.10,
        "attack_bias": -1,
        "integration_factor": 1.02,
    },
    "monarchy": {
        "income_factor": 1.03,
        "stability_factor": 0.98,
        "attack_bias": 1,
        "integration_factor": 1.05,
    },
    "republic": {
        "income_factor": 1.08,
        "stability_factor": 1.04,
        "attack_bias": 0,
        "integration_factor": 1.08,
    },
    "oligarchy": {
        "income_factor": 1.10,
        "stability_factor": 0.94,
        "attack_bias": 0,
        "integration_factor": 0.96,
    },
}
REGIME_AGITATION_GOVERNMENT_FORM_BIAS = {
    "leader": 0.14,
    "council": -0.08,
    "assembly": -0.16,
    "monarchy": 0.16,
    "republic": -0.10,
    "oligarchy": 0.12,
}
REGIME_AGITATION_DIPLOMATIC_FORMS = {"council", "assembly", "republic"}
REBEL_CONFLICT_SECESSION = "secession"
REBEL_CONFLICT_CIVIL_WAR = "civil_war"
CIVIL_WAR_AFFINITY_THRESHOLD = 0.65
CIVIL_WAR_SUCCESSOR_FORMS = {
    ("band", "leader"): "council",
    ("band", "council"): "leader",
    ("tribe", "leader"): "council",
    ("tribe", "council"): "assembly",
    ("tribe", "assembly"): "leader",
    ("chiefdom", "leader"): "council",
    ("chiefdom", "council"): "monarchy",
    ("chiefdom", "monarchy"): "council",
    ("state", "council"): "monarchy",
    ("state", "assembly"): "monarchy",
    ("state", "monarchy"): "republic",
    ("state", "republic"): "monarchy",
    ("state", "oligarchy"): "republic",
}
CIVIL_WAR_REGIME_LABELS = {
    ("band", "leader"): "Warband",
    ("band", "council"): "Council",
    ("tribe", "leader"): "Chieftaincy",
    ("tribe", "council"): "Council",
    ("tribe", "assembly"): "Assembly",
    ("chiefdom", "leader"): "Chieftaincy",
    ("chiefdom", "council"): "Council",
    ("chiefdom", "monarchy"): "Monarchy",
    ("state", "council"): "Council State",
    ("state", "assembly"): "Assembly State",
    ("state", "monarchy"): "Kingdom",
    ("state", "republic"): "Republic",
    ("state", "oligarchy"): "Oligarchy",
}

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
RESOURCE_FRONTIER_DISTRIBUTION_PENALTY = 0.18
RESOURCE_LOW_SETTLEMENT_DISTRIBUTION_PENALTY = 0.08
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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _ensure_region_resource_state(region: Region) -> None:
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
        return 0.9 + (region.extractive_level * 0.4) + (region.infrastructure_level * 0.12)
    return 0.95 + (region.infrastructure_level * 0.1)


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
    _ensure_region_resource_state(region)
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
) -> dict[str, dict[str, float | int | str | None]]:
    anchor_names = _get_owned_resource_anchor_names(world, faction_name)
    if not anchor_names:
        return {}

    route_map: dict[str, dict[str, float | int | str | None]] = {}
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


def _build_world_resource_route_maps(world: WorldState) -> dict[str, dict[str, dict[str, float | int | str | None]]]:
    return {
        faction_name: build_faction_resource_route_map(world, faction_name)
        for faction_name in world.factions
    }


def get_region_internal_distribution_state(
    region: Region,
    world: WorldState | None = None,
    *,
    faction_route_map: dict[str, dict[str, float | int | str | None]] | None = None,
) -> dict[str, float | int | str | None]:
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
    faction_route_map: dict[str, dict[str, float | int | str | None]] | None = None,
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
    faction_route_map: dict[str, dict[str, float | int | str | None]] | None = None,
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
    faction_route_map: dict[str, dict[str, float | int | str | None]] | None = None,
) -> None:
    _ensure_region_resource_state(region)
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
    _ensure_region_resource_state(region)
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
    faction_route_map: dict[str, dict[str, float | int | str | None]] | None = None,
) -> float:
    if world is not None and faction_route_map is None and any(region.resource_effective_output.values()):
        return _get_taxable_value_from_output(normalize_resource_map(region.resource_effective_output))
    if world is None and any(region.resource_output.values()):
        return _get_taxable_value_from_output(normalize_resource_map(region.resource_output))

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
        _ensure_region_resource_state(region)
        if advance_resources:
            advance_region_domesticable_resources(region)
        refresh_region_resource_state(
            region,
            world,
            faction_route_map=faction_route_maps.get(region.owner or "", {}),
        )
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
        derived_capacity = build_empty_capacity_map()
        derived_capacity[CAPACITY_FOOD_SECURITY] = round(
            faction.resource_effective_access[RESOURCE_GRAIN] + faction.resource_effective_access[RESOURCE_WILD_FOOD],
            3,
        )
        derived_capacity[CAPACITY_MOBILITY] = round(faction.resource_effective_access[RESOURCE_HORSES], 3)
        derived_capacity[CAPACITY_METAL] = round(faction.resource_effective_access[RESOURCE_COPPER], 3)
        derived_capacity[CAPACITY_CONSTRUCTION] = round(
            faction.resource_effective_access[RESOURCE_TIMBER] + faction.resource_effective_access[RESOURCE_STONE],
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
        faction.derived_capacity = normalize_capacity_map(derived_capacity)

        demand = get_faction_resource_demand(world, faction_name)
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
            shortages[key] = round(max(0.0, demand_value - access_value), 3)
        faction.resource_shortages = shortages


def initialize_region_resources(world: WorldState) -> None:
    for region in world.regions.values():
        seed_region_resource_profile(region)
    update_faction_resource_economy(world, advance_resources=False)


def apply_region_resource_damage(
    region: Region,
    damage_by_resource: dict[str, float],
) -> None:
    _ensure_region_resource_state(region)
    for resource_name, damage_amount in damage_by_resource.items():
        current_damage = region.resource_damage.get(resource_name, 0.0)
        region.resource_damage[resource_name] = round(
            _clamp(current_damage + damage_amount, 0.0, RESOURCE_MAX_DAMAGE),
            3,
        )


def get_faction_polity_modifiers(faction: Faction | None) -> dict[str, float]:
    if faction is None:
        return POLITY_TIER_MODIFIERS["tribe"]
    return POLITY_TIER_MODIFIERS.get(
        faction.polity_tier,
        POLITY_TIER_MODIFIERS["tribe"],
    )


def get_faction_government_form_modifiers(faction: Faction | None) -> dict[str, float]:
    if faction is None:
        return GOVERNMENT_FORM_MODIFIERS["council"]
    return GOVERNMENT_FORM_MODIFIERS.get(
        faction.government_form,
        GOVERNMENT_FORM_MODIFIERS["council"],
    )


def get_faction_income_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    return polity["income_factor"] * form["income_factor"]


def get_faction_maintenance_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    return polity["maintenance_factor"]


def get_faction_integration_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    return polity["integration_factor"] * form["integration_factor"]


def get_faction_stability_modifier(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    form = get_faction_government_form_modifiers(faction)
    return polity["stability_factor"] * form["stability_factor"]


def get_faction_realm_size_unrest_factor(faction: Faction | None) -> float:
    polity = get_faction_polity_modifiers(faction)
    return polity["realm_size_unrest_factor"]


def _normalize_region_ethnic_composition(region: Region) -> None:
    if region.population <= 0:
        region.ethnic_composition = {}
        return
    composition = {
        ethnicity: count
        for ethnicity, count in region.ethnic_composition.items()
        if count > 0
    }
    if not composition:
        region.ethnic_composition = {}
        return
    total = sum(composition.values())
    scaled: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    assigned = 0
    for ethnicity, count in composition.items():
        scaled_value = (count / total) * region.population
        whole = int(scaled_value)
        scaled[ethnicity] = whole
        assigned += whole
        remainders.append((scaled_value - whole, ethnicity))
    for _fraction, ethnicity in sorted(remainders, reverse=True)[: max(0, region.population - assigned)]:
        scaled[ethnicity] += 1
    region.ethnic_composition = {
        ethnicity: count
        for ethnicity, count in scaled.items()
        if count > 0
    }


def register_ethnicity(
    world: WorldState,
    ethnicity_name: str,
    *,
    language_family: str = "",
    parent_ethnicity: str | None = None,
    origin_faction: str | None = None,
    language_profile: LanguageProfile | None = None,
) -> None:
    world.ethnicities.setdefault(
        ethnicity_name,
        Ethnicity(
            name=ethnicity_name,
            language_family=language_family or ethnicity_name,
            parent_ethnicity=parent_ethnicity,
            origin_faction=origin_faction,
            language_profile=deepcopy(language_profile) if language_profile is not None else LanguageProfile(family_name=language_family or ethnicity_name),
        ),
    )


def seed_region_ethnicity(region: Region, ethnicity_name: str) -> None:
    if region.population <= 0:
        region.ethnic_composition = {}
        return
    region.ethnic_composition = {ethnicity_name: region.population}


def get_region_dominant_ethnicity(region: Region) -> str | None:
    if not region.ethnic_composition:
        return None
    return max(
        region.ethnic_composition.items(),
        key=lambda item: (item[1], item[0]),
    )[0]


def get_region_owner_primary_ethnicity(region: Region, world: WorldState) -> str | None:
    if region.owner is None or region.owner not in world.factions:
        return None
    return world.factions[region.owner].primary_ethnicity


def get_region_ruling_ethnic_affinity(
    region: Region,
    world: WorldState,
    faction_name: str | None = None,
) -> float:
    if region.population <= 0:
        return 0.0

    faction_name = faction_name or region.owner
    if faction_name is None or faction_name not in world.factions:
        return 0.0

    primary_ethnicity = world.factions[faction_name].primary_ethnicity
    if not primary_ethnicity:
        return 0.0

    return _clamp(
        region.ethnic_composition.get(primary_ethnicity, 0) / max(1, region.population),
        0.0,
        1.0,
    )


def faction_has_ethnic_claim(
    world: WorldState,
    region: Region,
    faction_name: str | None,
) -> bool:
    if faction_name is None or faction_name not in world.factions:
        return False
    dominant_ethnicity = get_region_dominant_ethnicity(region)
    if dominant_ethnicity is None:
        return False
    return world.factions[faction_name].primary_ethnicity == dominant_ethnicity


def get_region_ethnic_claimants(region: Region, world: WorldState) -> list[str]:
    dominant_ethnicity = get_region_dominant_ethnicity(region)
    if dominant_ethnicity is None:
        return []
    return sorted(
        [
            faction_name
            for faction_name, faction in world.factions.items()
            if faction.primary_ethnicity == dominant_ethnicity
        ],
    )


def get_faction_ethnic_claims(world: WorldState, faction_name: str) -> list[str]:
    if faction_name not in world.factions:
        return []
    return sorted(
        [
            region.name
            for region in world.regions.values()
            if faction_has_ethnic_claim(world, region, faction_name)
        ],
    )


def factions_have_same_ethnicity_regime_tension(
    world: WorldState,
    faction_a_name: str | None,
    faction_b_name: str | None,
) -> bool:
    if (
        faction_a_name is None
        or faction_b_name is None
        or faction_a_name == faction_b_name
        or faction_a_name not in world.factions
        or faction_b_name not in world.factions
    ):
        return False

    faction_a = world.factions[faction_a_name]
    faction_b = world.factions[faction_b_name]
    if (
        faction_a.primary_ethnicity is None
        or faction_b.primary_ethnicity is None
        or faction_a.primary_ethnicity != faction_b.primary_ethnicity
    ):
        return False

    return (
        faction_a.government_form != faction_b.government_form
        or (faction_a.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR and faction_a.origin_faction == faction_b_name)
        or (faction_b.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR and faction_b.origin_faction == faction_a_name)
    )


def get_same_ethnicity_regime_rivals(world: WorldState, faction_name: str | None) -> list[str]:
    if faction_name is None or faction_name not in world.factions:
        return []

    owned_region_counts = get_owned_region_counts(world)
    return sorted(
        [
            other_name
            for other_name in world.factions
            if other_name != faction_name
            and owned_region_counts.get(other_name, 0) > 0
            and factions_have_same_ethnicity_regime_tension(world, faction_name, other_name)
        ]
    )


def get_region_regime_contestation_unrest_modifier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions or region.population <= 0:
        return 0.0

    owner = world.factions[region.owner]
    if owner.primary_ethnicity is None:
        return 0.0
    if get_region_dominant_ethnicity(region) != owner.primary_ethnicity:
        return 0.0
    if get_region_ruling_ethnic_affinity(region, world) < 0.6:
        return 0.0

    rivals = get_same_ethnicity_regime_rivals(world, region.owner)
    if not rivals:
        return 0.0

    modifier = REGIME_CONTESTATION_UNREST_BASE
    status = get_region_core_status(region)
    if status == "homeland":
        modifier += REGIME_CONTESTATION_HOMELAND_UNREST_BONUS
    elif status == "core":
        modifier += REGIME_CONTESTATION_CORE_UNREST_BONUS
    return modifier


def get_region_external_regime_agitators(region: Region, world: WorldState) -> list[str]:
    if region.owner is None or region.owner not in world.factions or region.population <= 0:
        return []

    owner = world.factions[region.owner]
    if owner.primary_ethnicity is None:
        return []
    if get_region_dominant_ethnicity(region) != owner.primary_ethnicity:
        return []
    if get_region_ruling_ethnic_affinity(region, world) < 0.5:
        return []

    agitators: set[str] = set()
    for neighbor_name in region.neighbors:
        neighbor_owner = world.regions[neighbor_name].owner
        if neighbor_owner is None or neighbor_owner == region.owner:
            continue
        if factions_have_same_ethnicity_regime_tension(world, region.owner, neighbor_owner):
            agitators.add(neighbor_owner)
    return sorted(agitators)


def get_regime_agitation_sponsor_factor(
    world: WorldState,
    sponsor_name: str,
) -> float:
    sponsor = world.factions.get(sponsor_name)
    if sponsor is None:
        return 1.0

    treasury_bonus = min(
        REGIME_AGITATION_TREASURY_MAX_BONUS,
        sponsor.treasury * REGIME_AGITATION_TREASURY_FACTOR,
    )
    war_bias = (sponsor.doctrine_profile.war_posture - 0.5) * REGIME_AGITATION_WAR_POSTURE_FACTOR
    insularity_bias = (0.5 - sponsor.doctrine_profile.insularity) * REGIME_AGITATION_INSULARITY_FACTOR
    return _clamp(
        1.0 + treasury_bonus + war_bias + insularity_bias,
        REGIME_AGITATION_MIN_SPONSOR_FACTOR,
        REGIME_AGITATION_MAX_SPONSOR_FACTOR,
    )


def get_regime_agitation_government_bias(
    world: WorldState,
    sponsor_name: str,
) -> float:
    sponsor = world.factions.get(sponsor_name)
    if sponsor is None:
        return 0.0
    return REGIME_AGITATION_GOVERNMENT_FORM_BIAS.get(sponsor.government_form, 0.0)


def get_regime_agitation_sponsor_mode(
    world: WorldState,
    sponsor_name: str,
    *,
    owner_name: str | None = None,
) -> str:
    from src.diplomacy import get_relationship_state

    sponsor_factor = get_regime_agitation_sponsor_factor(world, sponsor_name)
    sponsor = world.factions.get(sponsor_name)
    effective_factor = sponsor_factor + get_regime_agitation_government_bias(
        world,
        sponsor_name,
    )
    is_claimant = (
        sponsor is not None
        and owner_name is not None
        and sponsor.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR
        and not sponsor.proto_state
        and sponsor.origin_faction == owner_name
    )
    if sponsor is not None and owner_name is not None:
        relationship = get_relationship_state(world, sponsor_name, owner_name)
        if (
            sponsor.government_form in REGIME_AGITATION_DIPLOMATIC_FORMS
            and relationship.status != "rival"
            and relationship.score > DIPLOMACY_RIVAL_THRESHOLD
        ):
            return "none"
    if (
        is_claimant
        and effective_factor >= 1.05
    ):
        return "heavy"
    if effective_factor >= REGIME_AGITATION_HEAVY_MODE_THRESHOLD:
        return "heavy"
    if is_claimant and effective_factor >= REGIME_AGITATION_LOW_MODE_THRESHOLD:
        return "standard"
    if effective_factor <= REGIME_AGITATION_LOW_MODE_THRESHOLD:
        return "low"
    return "standard"


def get_regime_agitation_mode_multipliers(mode: str) -> dict[str, float]:
    if mode == "none":
        return {
            "pressure": 0.0,
            "cost": 0.0,
            "backlash": 0.0,
        }
    if mode == "heavy":
        return {
            "pressure": REGIME_AGITATION_HEAVY_PRESSURE_MULTIPLIER,
            "cost": REGIME_AGITATION_HEAVY_COST_MULTIPLIER,
            "backlash": REGIME_AGITATION_HEAVY_BACKLASH_MULTIPLIER,
        }
    if mode == "low":
        return {
            "pressure": REGIME_AGITATION_LOW_PRESSURE_MULTIPLIER,
            "cost": REGIME_AGITATION_LOW_COST_MULTIPLIER,
            "backlash": REGIME_AGITATION_LOW_BACKLASH_MULTIPLIER,
        }
    return {
        "pressure": 1.0,
        "cost": 1.0,
        "backlash": 1.0,
    }


def get_region_external_regime_agitation_breakdown(
    region: Region,
    world: WorldState,
) -> dict[str, dict[str, float | str]]:
    agitators = get_region_external_regime_agitators(region, world)
    if not agitators:
        return {}

    owner_name = region.owner
    contributions: dict[str, dict[str, float | str]] = {}
    for agitator_name in agitators:
        mode = get_regime_agitation_sponsor_mode(
            world,
            agitator_name,
            owner_name=owner_name,
        )
        if mode == "none":
            continue
        mode_multipliers = get_regime_agitation_mode_multipliers(mode)
        sponsor_factor = get_regime_agitation_sponsor_factor(world, agitator_name)
        base_contribution = REGIME_AGITATION_UNREST_PER_SPONSOR * sponsor_factor
        agitator = world.factions.get(agitator_name)
        claimant_bonus = 0.0
        if (
            agitator is not None
            and agitator.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR
            and not agitator.proto_state
            and agitator.origin_faction == owner_name
        ):
            claimant_bonus = REGIME_AGITATION_CLAIMANT_BONUS
        contribution = (base_contribution + claimant_bonus) * mode_multipliers["pressure"]
        contributions[agitator_name] = {
            "pressure": round(contribution, 4),
            "mode": mode,
            "sponsor_factor": round(sponsor_factor, 3),
            "cost_multiplier": mode_multipliers["cost"],
            "backlash_multiplier": mode_multipliers["backlash"],
        }
    return contributions


def get_region_external_regime_agitation_modifier(region: Region, world: WorldState) -> float:
    contributions = get_region_external_regime_agitation_breakdown(region, world)
    if not contributions:
        return 0.0
    return min(
        REGIME_AGITATION_MAX,
        sum(float(details["pressure"]) for details in contributions.values()),
    )


def _choose_regime_agitation_backlash_region(
    world: WorldState,
    sponsor_name: str,
) -> Region | None:
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == sponsor_name
    ]
    if not owned_regions:
        return None

    homeland_regions = [
        region
        for region in owned_regions
        if get_region_core_status(region) == "homeland"
    ]
    if homeland_regions:
        return max(
            homeland_regions,
            key=lambda region: (
                region.integration_score,
                get_region_taxable_value(region, world),
                region.name,
            ),
        )

    core_regions = [
        region
        for region in owned_regions
        if get_region_core_status(region) == "core"
    ]
    if core_regions:
        return max(
            core_regions,
            key=lambda region: (
                region.integration_score,
                get_region_taxable_value(region, world),
                region.name,
            ),
        )

    return max(
        owned_regions,
        key=lambda region: (
            region.integration_score,
            get_region_taxable_value(region, world),
            region.name,
        ),
    )


def _apply_regime_agitation_sponsor_costs(
    world: WorldState,
    sponsor_pressures: dict[str, dict[str, float | str]],
) -> dict[str, dict[str, float | int | str | None]]:
    sponsor_costs: dict[str, dict[str, float | int | str | None]] = {}
    for sponsor_name, details in sponsor_pressures.items():
        sponsor = world.factions.get(sponsor_name)
        if sponsor is None:
            continue
        pressure = float(details.get("pressure", 0.0))
        mode = str(details.get("mode", "standard"))
        cost_multiplier = float(details.get("cost_multiplier", 1.0))
        backlash_multiplier = float(details.get("backlash_multiplier", 1.0))

        treasury_cost = min(
            sponsor.treasury,
            max(1, int(round(pressure * REGIME_AGITATION_TREASURY_COST_FACTOR * cost_multiplier))),
        ) if pressure > 0 else 0
        sponsor.treasury -= treasury_cost

        backlash_region = _choose_regime_agitation_backlash_region(world, sponsor_name)
        backlash_unrest = round(
            pressure * REGIME_AGITATION_HOMEFRONT_UNREST_FACTOR * backlash_multiplier,
            2,
        )
        if backlash_region is not None and backlash_unrest > 0:
            set_region_unrest(backlash_region, backlash_region.unrest + backlash_unrest)

        sponsor_costs[sponsor_name] = {
            "mode": mode,
            "treasury_cost": treasury_cost,
            "treasury_after": sponsor.treasury,
            "backlash_region": backlash_region.name if backlash_region is not None else None,
            "backlash_unrest": backlash_unrest if backlash_region is not None else 0.0,
        }
    return sponsor_costs


def _emit_regime_agitation_event(world: WorldState, region: Region) -> None:
    sponsor_pressures = get_region_external_regime_agitation_breakdown(region, world)
    agitators = sorted(sponsor_pressures)
    agitation = get_region_external_regime_agitation_modifier(region, world)
    if not agitators or agitation <= 0:
        return

    sponsor_costs = _apply_regime_agitation_sponsor_costs(world, sponsor_pressures)
    claimant_sponsors = [
        faction_name
        for faction_name in agitators
        if (
            faction_name in world.factions
            and world.factions[faction_name].rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR
            and not world.factions[faction_name].proto_state
            and world.factions[faction_name].origin_faction == region.owner
        )
    ]
    lead_sponsor = max(
        sponsor_pressures.items(),
        key=lambda item: (float(item[1]["pressure"]), item[0]),
    )[0]
    world.events.append(Event(
        turn=world.turn,
        type="regime_agitation",
        faction=region.owner,
        region=region.name,
        details={
            "sponsors": agitators,
            "lead_sponsor": lead_sponsor,
            "sponsor_pressures": sponsor_pressures,
            "lead_sponsor_mode": sponsor_pressures[lead_sponsor]["mode"],
            "sponsor_costs": sponsor_costs,
            "claimant_sponsors": claimant_sponsors,
            "agitation_pressure": round(agitation, 3),
            "event_level": region.unrest_event_level,
            "unrest": round(region.unrest, 2),
        },
        tags=[
            "unrest",
            "agitation",
            "regime",
            *(["civil_war"] if claimant_sponsors else []),
        ],
        significance=agitation,
    ))


def get_region_ethnic_integration_multiplier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 1.0
    if region.homeland_faction_id == region.owner:
        return 1.0
    multiplier = ETHNIC_INTEGRATION_MIN_MULTIPLIER + get_region_ruling_ethnic_affinity(region, world)
    if faction_has_ethnic_claim(world, region, region.owner):
        multiplier += ETHNIC_CLAIM_INTEGRATION_BONUS
    return multiplier


def get_region_ethnic_unrest_modifier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.0
    if region.homeland_faction_id == region.owner:
        return 0.0

    affinity = get_region_ruling_ethnic_affinity(region, world)
    if affinity >= ETHNIC_UNREST_CALMING_THRESHOLD:
        modifier = ETHNIC_UNREST_CALMING_EFFECT
    elif affinity >= ETHNIC_UNREST_NEUTRAL_THRESHOLD:
        modifier = 0.0
    elif affinity >= ETHNIC_UNREST_SEVERE_THRESHOLD:
        modifier = ETHNIC_UNREST_LOW_AFFINITY_PRESSURE
    else:
        modifier = ETHNIC_UNREST_SEVERE_AFFINITY_PRESSURE
    if faction_has_ethnic_claim(world, region, region.owner):
        modifier -= ETHNIC_CLAIM_UNREST_REDUCTION
    return modifier


def change_region_population(region: Region, amount: int) -> int:
    previous_population = region.population
    if previous_population <= 0 and amount <= 0:
        return 0
    region.population = max(0, region.population + amount)
    _normalize_region_ethnic_composition(region)
    return region.population - previous_population


def apply_region_population_loss(region: Region, ratio: float, *, minimum_loss: int = 1) -> int:
    if region.population <= 0:
        return 0
    loss = max(minimum_loss, int(round(region.population * max(0.0, ratio))))
    return -change_region_population(region, -loss)


def transfer_region_population(source: Region, target: Region, amount: int) -> int:
    if amount <= 0 or source.population <= 0:
        return 0
    amount = min(amount, source.population)
    source_total = source.population
    source_composition = {
        ethnicity: count
        for ethnicity, count in source.ethnic_composition.items()
        if count > 0
    }
    if not source_composition:
        return 0

    moved_counts: dict[str, int] = {}
    assigned = 0
    remainders: list[tuple[float, str]] = []
    for ethnicity, count in source_composition.items():
        moved_value = (count / source_total) * amount
        whole = min(count, int(moved_value))
        moved_counts[ethnicity] = whole
        assigned += whole
        remainders.append((moved_value - whole, ethnicity))
    for _fraction, ethnicity in sorted(remainders, reverse=True):
        if assigned >= amount:
            break
        available = source_composition[ethnicity] - moved_counts[ethnicity]
        if available <= 0:
            continue
        moved_counts[ethnicity] += 1
        assigned += 1

    moved_total = sum(moved_counts.values())
    if moved_total <= 0:
        return 0

    source.population -= moved_total
    target.population += moved_total
    for ethnicity, count in moved_counts.items():
        remaining = source.ethnic_composition.get(ethnicity, 0) - count
        if remaining > 0:
            source.ethnic_composition[ethnicity] = remaining
        elif ethnicity in source.ethnic_composition:
            del source.ethnic_composition[ethnicity]
        target.ethnic_composition[ethnicity] = target.ethnic_composition.get(ethnicity, 0) + count

    _normalize_region_ethnic_composition(source)
    _normalize_region_ethnic_composition(target)
    return moved_total


def estimate_region_population(
    resources: int,
    neighbor_count: int,
    owner: str | None = None,
) -> int:
    if owner is None:
        return 0
    estimate = (
        POPULATION_BASE
        + (resources * POPULATION_PER_RESOURCE)
        + (neighbor_count * POPULATION_PER_CONNECTION)
    )
    estimate += POPULATION_STARTING_OWNER_BONUS
    return max(POPULATION_MINIMUM, estimate)


def estimate_region_population_from_resource_profile(
    region: Region,
    *,
    owner: str | None = None,
) -> int:
    _ensure_region_resource_state(region)
    owner_name = owner if owner is not None else region.owner
    resource_potential = get_legacy_region_resource_value(
        None,
        fixed_endowments=region.resource_fixed_endowments,
        wild_endowments=region.resource_wild_endowments,
        suitability=region.resource_suitability,
        established=region.resource_established,
    )
    return estimate_region_population(
        resource_potential,
        len(region.neighbors),
        owner=owner_name,
    )


def get_region_productive_capacity(region: Region, world: WorldState | None = None) -> float:
    _ensure_region_resource_state(region)
    terrain_profile = get_terrain_profile(region)
    terrain_productivity = sum(
        SURPLUS_TERRAIN_PRODUCTIVITY.get(tag, 0.0)
        for tag in terrain_profile["terrain_tags"]
    )
    productive_capacity = (
        get_region_taxable_value(region, world)
        + min(1.5, len(region.neighbors) * SURPLUS_CONNECTION_YIELD)
        + max(-0.8, terrain_productivity * 0.35)
    )
    return round(max(0.0, productive_capacity), 2)


def get_region_population_pressure(region: Region) -> float:
    if region.population <= 0:
        return 0.0
    return round(region.population / SURPLUS_POPULATION_PRESSURE, 2)


def get_region_surplus(region: Region, world: WorldState | None = None) -> float:
    surplus = get_region_productive_capacity(region, world) - get_region_population_pressure(region)
    return round(surplus, 2)


def get_region_surplus_label(region: Region, world: WorldState | None = None) -> str:
    surplus = get_region_surplus(region, world)
    if surplus >= 4.0:
        return "abundant"
    if surplus >= 1.0:
        return "stable"
    if surplus > -1.0:
        return "strained"
    return "deficit"


def get_region_settlement_level(region: Region, world: WorldState | None = None) -> str:
    if region.owner is None or region.population <= 0:
        return "wild"

    surplus = get_region_surplus(region, world)
    core_status = get_region_core_status(region)
    unrest = region.unrest
    ownership_turns = region.ownership_turns

    if (
        region.population >= 320
        and surplus >= 2.5
        and unrest < 3.5
        and core_status in {"homeland", "core"}
        and (core_status == "homeland" or ownership_turns >= 6)
    ):
        return "city"

    if (
        region.population >= 160
        and surplus >= 1.5
        and unrest < 5.0
        and (core_status in {"homeland", "core"} or ownership_turns >= 3)
    ):
        return "town"

    if region.population >= 35 and surplus >= -0.5 and unrest < 8.0:
        return "rural"

    return "wild"


def update_region_settlement_levels(world: WorldState) -> None:
    for region in world.regions.values():
        region.settlement_level = get_region_settlement_level(region, world)


def get_faction_settlement_profile(world: WorldState, faction_name: str) -> dict[str, float | int]:
    profile = {
        "owned_regions": 0,
        "population": 0,
        "total_surplus": 0.0,
        "wild_regions": 0,
        "rural_regions": 0,
        "town_regions": 0,
        "city_regions": 0,
    }

    for region in world.regions.values():
        if region.owner != faction_name:
            continue
        profile["owned_regions"] += 1
        profile["population"] += region.population
        profile["total_surplus"] += get_region_surplus(region, world)
        settlement_level = region.settlement_level
        if settlement_level == "city":
            profile["city_regions"] += 1
        elif settlement_level == "town":
            profile["town_regions"] += 1
        elif settlement_level == "rural":
            profile["rural_regions"] += 1
        else:
            profile["wild_regions"] += 1

    profile["total_surplus"] = round(profile["total_surplus"], 2)
    return profile


def _qualifies_for_tribe(profile: dict[str, float | int]) -> bool:
    return profile["owned_regions"] >= 1 and (
        profile["rural_regions"] >= 1
        or profile["town_regions"] >= 1
        or profile["city_regions"] >= 1
    )


def _qualifies_for_chiefdom(profile: dict[str, float | int]) -> bool:
    return (
        profile["owned_regions"] >= 2
        and profile["population"] >= 250
        and profile["total_surplus"] >= 2.5
        and (profile["town_regions"] + profile["city_regions"]) >= 1
    )


def _qualifies_for_state(profile: dict[str, float | int]) -> bool:
    return (
        profile["owned_regions"] >= 3
        and profile["population"] >= 500
        and profile["total_surplus"] >= 6.0
        and profile["city_regions"] >= 1
        and (profile["town_regions"] + profile["city_regions"]) >= 2
    )


def get_next_polity_tier(
    current_tier: str,
    profile: dict[str, float | int],
) -> str:
    if current_tier == "band" and _qualifies_for_tribe(profile):
        return "tribe"
    if current_tier == "tribe" and _qualifies_for_chiefdom(profile):
        return "chiefdom"
    if current_tier == "chiefdom" and _qualifies_for_state(profile):
        return "state"
    return current_tier


def update_faction_polity_tiers(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        if faction.identity is None:
            continue

        current_tier = faction.polity_tier
        profile = get_faction_settlement_profile(world, faction_name)
        next_tier = get_next_polity_tier(current_tier, profile)
        if next_tier == current_tier:
            continue

        current_form = faction.government_form
        if current_form not in GOVERNMENT_FORMS_BY_TIER[next_tier]:
            current_form = get_default_government_form(next_tier)

        prior_display_name = faction.identity.display_name
        refresh_display_name = prior_display_name == faction.identity.default_display_name()
        old_government_type = faction.government_type
        faction.identity.set_government_structure(
            next_tier,
            current_form,
            update_display_name=refresh_display_name,
        )
        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            set_region_unrest(
                region,
                max(0.0, region.unrest - POLITY_ADVANCEMENT_UNREST_REDUCTION),
            )

        world.events.append(Event(
            turn=world.turn,
            type="polity_advance",
            faction=faction_name,
            details={
                "old_polity_tier": current_tier,
                "new_polity_tier": next_tier,
                "old_government_type": old_government_type,
                "new_government_type": faction.government_type,
                "town_regions": profile["town_regions"],
                "city_regions": profile["city_regions"],
                "population": profile["population"],
                "total_surplus": profile["total_surplus"],
            },
            tags=["government", "polity", "advancement"],
            significance=float(POLITY_TIER_ORDER.index(next_tier)),
        ))


def update_region_populations(world: WorldState) -> None:
    for region in world.regions.values():
        if region.population <= 0:
            continue
        growth_factor = POPULATION_GROWTH_PER_TURN
        if region.owner is None:
            growth_factor *= POPULATION_UNOWNED_GROWTH_FACTOR
        unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
        growth_factor -= unrest_ratio * POPULATION_UNREST_GROWTH_PENALTY * POPULATION_GROWTH_PER_TURN
        surplus_growth_modifier = _clamp(
            get_region_surplus(region, world) * SURPLUS_GROWTH_FACTOR,
            SURPLUS_MIN_GROWTH_PENALTY,
            SURPLUS_MAX_GROWTH_BONUS,
        )
        if surplus_growth_modifier > 0:
            surplus_growth_modifier *= (1.0 - unrest_ratio)
        growth_factor += surplus_growth_modifier

        if region.owner in world.factions:
            food_shortage = world.factions[region.owner].resource_shortages.get(
                CAPACITY_FOOD_SECURITY,
                0.0,
            )
            if food_shortage > 0:
                growth_factor -= min(0.02, food_shortage * 0.01)

        change = int(round(region.population * growth_factor))
        if change == 0 and growth_factor > 0:
            change = 1
        if change != 0:
            change_region_population(region, change)


def get_region_core_status(region: Region) -> str:
    if region.owner is None:
        return "frontier"
    if region.homeland_faction_id == region.owner:
        return "homeland"
    if region.integration_score >= CORE_INTEGRATION_SCORE:
        return "core"
    return "frontier"


def get_region_core_defense_bonus(region: Region) -> int:
    status = get_region_core_status(region)
    if status == "homeland":
        return 2
    if status == "core":
        return 1
    return 0


def get_region_climate_affinity(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.5
    from src.doctrine import get_faction_climate_affinity

    return get_faction_climate_affinity(world.factions[region.owner], region.climate)


def get_region_income_factor(region: Region) -> float:
    status = get_region_core_status(region)
    if status == "homeland":
        return HOMELAND_INCOME_FACTOR
    if status == "core":
        return CORE_INCOME_FACTOR
    return FRONTIER_INCOME_FACTOR


def get_faction_frontier_burden(world: WorldState, faction_name: str) -> float:
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]
    if not owned_regions:
        return 0.0

    frontier_regions = sum(
        1
        for region in owned_regions
        if get_region_core_status(region) == "frontier"
    )
    return frontier_regions / len(owned_regions)


def get_region_unrest_income_factor(region: Region) -> float:
    unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
    income_factor = 1.0 - ((1.0 - UNREST_INCOME_MIN_FACTOR) * unrest_ratio)
    if region.unrest_event_level == "disturbance":
        income_factor *= UNREST_DISTURBANCE_INCOME_FACTOR
    elif region.unrest_event_level == "crisis":
        income_factor *= UNREST_CRISIS_INCOME_FACTOR
    return income_factor


def get_region_climate_income_factor(region: Region, world: WorldState) -> float:
    affinity = get_region_climate_affinity(region, world)
    return CLIMATE_INCOME_MIN_FACTOR + (
        (CLIMATE_INCOME_MAX_FACTOR - CLIMATE_INCOME_MIN_FACTOR) * affinity
    )


def get_region_effective_income(region: Region, world: WorldState | None = None) -> int:
    income_factor = get_region_income_factor(region)
    taxable_value = get_region_taxable_value(region, world)
    if world is not None and region.owner in world.factions:
        income_factor *= get_faction_income_modifier(world.factions[region.owner])
    return int(round(taxable_value * income_factor))


def get_region_climate_maintenance_factor(region: Region, world: WorldState) -> float:
    affinity = get_region_climate_affinity(region, world)
    return CLIMATE_MAINTENANCE_MAX_FACTOR - (
        (CLIMATE_MAINTENANCE_MAX_FACTOR - CLIMATE_MAINTENANCE_MIN_FACTOR) * affinity
    )


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


def get_region_climate_integration_modifier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.0
    if region.homeland_faction_id == region.owner:
        return 0.0

    affinity = get_region_climate_affinity(region, world)
    status = get_region_core_status(region)
    centered_affinity = (affinity - 0.5) * 2

    if status == "frontier":
        return centered_affinity * CLIMATE_FRONTIER_INTEGRATION_CLIMATE_FACTOR

    return centered_affinity * CLIMATE_CORE_INTEGRATION_CLIMATE_FACTOR


def get_region_attack_projection_modifier(
    region: Region,
    *,
    world: WorldState | None = None,
    faction_name: str | None = None,
) -> int:
    modifier = 0
    if get_region_core_status(region) == "frontier":
        modifier -= FRONTIER_ATTACK_PROJECTION_PENALTY

    unrest_penalty = int(
        round(_clamp(region.unrest / UNREST_MAX, 0.0, 1.0) * UNREST_ATTACK_PROJECTION_MAX_PENALTY)
    )
    modifier -= unrest_penalty
    if region.unrest_event_level in {"disturbance", "crisis"}:
        modifier -= UNREST_EVENT_ATTACK_PROJECTION_PENALTY

    if world is not None and faction_name is not None and faction_name in world.factions:
        from src.doctrine import get_faction_climate_affinity

        climate_affinity = get_faction_climate_affinity(world.factions[faction_name], region.climate)
        climate_penalty = int(round((1.0 - climate_affinity) * CLIMATE_ATTACK_PROJECTION_MAX_PENALTY))
        modifier -= climate_penalty

    return modifier


def set_region_integration(
    region: Region,
    *,
    owner: str | None,
    score: float,
    ownership_turns: int,
    core_status: str | None = None,
) -> None:
    region.integrated_owner = owner
    region.integration_score = score
    region.ownership_turns = ownership_turns
    region.core_status = core_status or get_region_core_status(region)


def set_region_unrest(region: Region, unrest: float) -> None:
    region.unrest = round(_clamp(unrest, 0.0, UNREST_MAX), 2)


def clear_region_unrest_event(region: Region) -> None:
    region.unrest_event_level = "none"
    region.unrest_event_turns_remaining = 0


def set_region_unrest_event(region: Region, *, level: str, duration: int) -> None:
    region.unrest_event_level = level
    region.unrest_event_turns_remaining = duration


def get_region_unrest_event_cost(region: Region) -> int:
    if region.unrest_event_level == "crisis":
        return UNREST_CRISIS_TREASURY_HIT
    if region.unrest_event_level == "disturbance":
        return UNREST_DISTURBANCE_TREASURY_HIT
    return 0


def reset_region_crisis_streak(region: Region) -> None:
    region.unrest_crisis_streak = 0


def set_region_secession_cooldown(region: Region, turns: int) -> None:
    region.secession_cooldown_turns = max(0, turns)


def _normalize_rebel_name_seed(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _letters_only(value: str) -> str:
    return "".join(character for character in (value or "") if character.isalpha())


def _extract_name_fragments(value: str) -> list[str]:
    normalized = _letters_only(value).lower()
    if len(normalized) < 4:
        return [normalized] if normalized else []
    fragments = [
        normalized[:3],
        normalized[:4],
        normalized[-3:],
        normalized[-4:],
        normalized[1:4],
    ]
    unique_fragments: list[str] = []
    for fragment in fragments:
        if len(fragment) >= 2 and fragment not in unique_fragments:
            unique_fragments.append(fragment)
    return unique_fragments


def _to_title_case_root(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:].lower()


def _generate_successor_ethnicity_name(
    world: WorldState,
    parent_ethnicity: str,
    faction_name: str,
) -> str:
    parent_profile = world.ethnicities.get(parent_ethnicity).language_profile if parent_ethnicity in world.ethnicities else LanguageProfile()
    rng = random.Random(f"{parent_ethnicity}:{faction_name}:{world.turn}")

    onsets = parent_profile.onsets or ["ka", "sa", "va", "ta", "no"]
    middles = parent_profile.middles or ["a", "e", "i", "o", "u", "ae", "ia"]
    suffixes = parent_profile.suffixes or ["ar", "an", "en", "or", "ri", "var"]
    fragments = parent_profile.seed_fragments or [_letters_only(parent_ethnicity).lower() or "novan"]

    fragment = rng.choice(fragments)
    onset = rng.choice(onsets)
    middle = rng.choice(middles)
    suffix = rng.choice(suffixes)
    endings = ["ri", "vi", "ra", "ta", "ni", "len", "var", "sar"]

    pattern = rng.choice(("profile_blend", "fragment_soften", "compound"))
    if pattern == "profile_blend":
        candidate = f"{onset[: max(1, min(3, len(onset)))]}{middle}{fragment[-max(2, min(4, len(fragment))):]}{rng.choice(endings)}"
    elif pattern == "fragment_soften":
        candidate = f"{fragment[: max(2, min(4, len(fragment)))]}{middle}{suffix}"
    else:
        candidate = f"{onset[:2]}{fragment[max(1, len(fragment) // 3): max(3, len(fragment) // 3 + 3)]}{suffix}"

    candidate = _to_title_case_root(re.sub(r"[^A-Za-z]", "", candidate))
    while candidate in world.ethnicities:
        candidate = f"{candidate}n"
    return candidate


def _build_successor_language_profile(
    parent_profile: LanguageProfile,
    successor_ethnicity: str,
) -> LanguageProfile:
    successor_fragments = _extract_name_fragments(successor_ethnicity)
    return LanguageProfile(
        family_name=parent_profile.family_name or successor_ethnicity,
        onsets=(parent_profile.onsets + successor_fragments[:3])[:12],
        middles=parent_profile.middles[:12],
        suffixes=(parent_profile.suffixes + [fragment[-3:] for fragment in successor_fragments if len(fragment) >= 3])[:12],
        seed_fragments=(parent_profile.seed_fragments + successor_fragments)[:16],
        style_notes=parent_profile.style_notes[:4],
    )


def _split_successor_ethnicity_in_regions(
    world: WorldState,
    faction_name: str,
    parent_ethnicity: str,
    successor_ethnicity: str,
) -> tuple[int, int]:
    successor_total = 0
    parent_total = 0

    for region in world.regions.values():
        if region.owner != faction_name or region.population <= 0:
            continue

        parent_count = region.ethnic_composition.get(parent_ethnicity, 0)
        if parent_count <= 0:
            parent_count = region.population
            region.ethnic_composition[parent_ethnicity] = parent_count

        successor_count = max(
            region.population // 2,
            int(round(region.population * 0.6)),
        )
        successor_count = min(successor_count, max(1, parent_count - 1) if parent_count > 1 else parent_count)
        if successor_count <= 0:
            continue

        region.ethnic_composition[parent_ethnicity] = max(
            0,
            region.ethnic_composition.get(parent_ethnicity, 0) - successor_count,
        )
        region.ethnic_composition[successor_ethnicity] = (
            region.ethnic_composition.get(successor_ethnicity, 0) + successor_count
        )
        _normalize_region_ethnic_composition(region)
        successor_total += region.ethnic_composition.get(successor_ethnicity, 0)
        parent_total += region.ethnic_composition.get(parent_ethnicity, 0)

    return successor_total, parent_total


def _build_rebel_faction_name(world: WorldState, region: Region) -> str:
    base_name = _normalize_rebel_name_seed(f"{region.ui_name} Rebels")
    candidate = base_name
    suffix = 2
    while candidate in world.factions:
        candidate = f"{base_name} {suffix}"
        suffix += 1
    return candidate


def _next_dynamic_internal_id(world: WorldState) -> str:
    existing_ids = {
        faction.internal_id
        for faction in world.factions.values()
    }
    next_index = 1
    while f"Faction{next_index}" in existing_ids:
        next_index += 1
    return f"Faction{next_index}"


def get_owned_region_counts(world: WorldState) -> dict[str, int]:
    counts = {faction_name: 0 for faction_name in world.factions}
    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1
    return counts


def _find_extinct_ethnic_restoration_faction(
    world: WorldState,
    region: Region,
    former_owner: str,
) -> str | None:
    if region.population <= 0 or not region.ethnic_composition:
        return None

    owned_region_counts = get_owned_region_counts(world)
    ranked_ethnicities = sorted(
        region.ethnic_composition.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    for ethnicity_name, population in ranked_ethnicities:
        if population <= 0:
            continue
        for faction_name, faction in world.factions.items():
            if faction_name == former_owner:
                continue
            if faction.primary_ethnicity != ethnicity_name:
                continue
            if owned_region_counts.get(faction_name, 0) > 0:
                continue
            if faction.is_rebel and faction.proto_state:
                continue
            return faction_name
    return None


def _restore_extinct_faction(
    world: WorldState,
    faction_name: str,
    *,
    former_owner: str,
    region_name: str,
) -> None:
    faction = world.factions[faction_name]
    faction.treasury = REBEL_STARTING_TREASURY
    faction.starting_treasury = REBEL_STARTING_TREASURY
    faction.proto_state = False
    faction.rebel_age = 0
    faction.independence_score = (
        REBEL_FULL_INDEPENDENCE_THRESHOLD
        if faction.is_rebel
        else 0.0
    )
    if faction.doctrine_state.homeland_region is None:
        faction.doctrine_state.homeland_region = region_name
        faction.doctrine_state.homeland_climate = world.regions[region_name].climate
        faction.doctrine_state.homeland_terrain_tags = list(world.regions[region_name].terrain_tags)
    if faction.origin_faction is None and faction.is_rebel:
        faction.origin_faction = former_owner


def _find_adjacent_rebel_destination(
    world: WorldState,
    region: Region,
    former_owner: str,
    conflict_type: str,
) -> str | None:
    for neighbor_name in region.neighbors:
        neighbor_owner = world.regions[neighbor_name].owner
        if neighbor_owner is None or neighbor_owner == former_owner:
            continue
        if neighbor_owner not in world.factions:
            continue
        neighbor_faction = world.factions[neighbor_owner]
        if (
            neighbor_faction.is_rebel
            and neighbor_faction.origin_faction == former_owner
            and neighbor_faction.rebel_conflict_type == conflict_type
        ):
            return neighbor_owner
    return None


def _determine_rebel_conflict_type(
    world: WorldState,
    region: Region,
    former_owner: str,
) -> str:
    former_faction = world.factions.get(former_owner)
    if former_faction is None or former_faction.primary_ethnicity is None:
        return REBEL_CONFLICT_SECESSION

    if get_region_dominant_ethnicity(region) != former_faction.primary_ethnicity:
        return REBEL_CONFLICT_SECESSION

    if region.homeland_faction_id == former_owner:
        return REBEL_CONFLICT_CIVIL_WAR

    if (
        region.core_status in {"core", "homeland"}
        and get_region_ruling_ethnic_affinity(region, world) >= CIVIL_WAR_AFFINITY_THRESHOLD
    ):
        return REBEL_CONFLICT_CIVIL_WAR

    return REBEL_CONFLICT_SECESSION


def _choose_civil_war_successor_structure(
    world: WorldState,
    former_owner: str,
) -> tuple[str, str]:
    former_faction = world.factions.get(former_owner)
    if former_faction is None:
        return "tribe", get_default_government_form("tribe")

    polity_tier = former_faction.polity_tier
    government_form = former_faction.government_form
    successor_form = CIVIL_WAR_SUCCESSOR_FORMS.get((polity_tier, government_form))
    if successor_form in GOVERNMENT_FORMS_BY_TIER.get(polity_tier, ()):
        return polity_tier, successor_form

    for candidate in GOVERNMENT_FORMS_BY_TIER.get(polity_tier, ()):
        if candidate != government_form:
            return polity_tier, candidate
    return polity_tier, get_default_government_form(polity_tier)


def _get_civil_war_display_name(
    culture_name: str,
    polity_tier: str,
    government_form: str,
    fallback_government_type: str,
) -> str:
    regime_label = CIVIL_WAR_REGIME_LABELS.get(
        (polity_tier, government_form),
        fallback_government_type,
    )
    return f"{culture_name} {regime_label}".strip()


def create_rebel_faction(world: WorldState, region: Region, former_owner: str) -> tuple[str, bool]:
    from src.doctrine import initialize_rebel_faction_doctrine

    restored_faction_name = _find_extinct_ethnic_restoration_faction(
        world,
        region,
        former_owner,
    )
    if restored_faction_name is not None:
        _restore_extinct_faction(
            world,
            restored_faction_name,
            former_owner=former_owner,
            region_name=region.name,
        )
        return restored_faction_name, True

    rebel_name = _build_rebel_faction_name(world, region)
    former_faction = world.factions[former_owner]
    conflict_type = _determine_rebel_conflict_type(world, region, former_owner)
    inherited_ethnicity = former_faction.primary_ethnicity
    parent_language_profile = (
        deepcopy(former_faction.identity.language_profile)
        if former_faction.identity is not None
        else LanguageProfile(family_name=inherited_ethnicity or former_owner)
    )
    if conflict_type == REBEL_CONFLICT_CIVIL_WAR:
        polity_tier, government_form = _choose_civil_war_successor_structure(
            world,
            former_owner,
        )
        culture_name = former_faction.culture_name
        generation_method = "civil_war_claimant"
    else:
        polity_tier, government_form = "state", "council"
        culture_name = _normalize_rebel_name_seed(region.ui_name)
        generation_method = "rebel_secession"
    rebel_identity = FactionIdentity(
        internal_id=_next_dynamic_internal_id(world),
        culture_name=culture_name,
        polity_tier=polity_tier,
        government_form=government_form,
        government_type="Rebels",
        display_name=rebel_name,
        language_profile=parent_language_profile,
        generation_method=generation_method,
        inspirations=[former_owner],
    )
    world.factions[rebel_name] = Faction(
        name=rebel_name,
        treasury=REBEL_STARTING_TREASURY,
        identity=rebel_identity,
        starting_treasury=REBEL_STARTING_TREASURY,
        primary_ethnicity=inherited_ethnicity,
        is_rebel=True,
        origin_faction=former_owner,
        rebel_conflict_type=conflict_type,
        rebel_age=0,
        independence_score=0.0,
        proto_state=True,
    )
    initialize_rebel_faction_doctrine(
        world,
        rebel_name,
        former_owner,
        region.name,
    )
    seed_rebel_origin_relationship(world, rebel_name, former_owner)
    return rebel_name, False


def _is_multi_region_rebellion_candidate(
    world: WorldState,
    region: Region,
    former_owner: str,
    conflict_type: str,
) -> bool:
    if region.owner != former_owner:
        return False
    if region.population <= 0:
        return False
    if region.homeland_faction_id == former_owner:
        return False
    if region.secession_cooldown_turns > 0:
        return False
    if _determine_rebel_conflict_type(world, region, former_owner) != conflict_type:
        return False
    return (
        region.unrest_event_level in {"disturbance", "crisis"}
        or region.unrest >= UNREST_MODERATE_THRESHOLD
    )


def _transfer_region_to_rebellion(
    world: WorldState,
    region: Region,
    rebel_faction_name: str,
) -> dict[str, int | str]:
    resources_before = region.resources
    taxable_before = get_region_taxable_value(region, world)
    population_before = region.population
    unrest_before = round(region.unrest, 2)
    apply_region_resource_damage(
        region,
        {
            RESOURCE_GRAIN: 0.08,
            RESOURCE_HORSES: 0.06,
            RESOURCE_WILD_FOOD: 0.04,
            RESOURCE_TIMBER: 0.07,
            RESOURCE_COPPER: 0.05,
            RESOURCE_STONE: 0.05,
        },
    )
    population_loss = apply_region_population_loss(region, POPULATION_SECESSION_LOSS)
    region.owner = rebel_faction_name
    set_region_integration(
        region,
        owner=rebel_faction_name,
        score=CORE_INTEGRATION_SCORE,
        ownership_turns=1,
        core_status="core",
    )
    set_region_unrest(region, REBEL_STARTING_UNREST)
    clear_region_unrest_event(region)
    reset_region_crisis_streak(region)
    set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
    refresh_region_resource_state(region, world)
    return {
        "region": region.name,
        "resource_change": region.resources - resources_before,
        "taxable_change": round(get_region_taxable_value(region, world) - taxable_before, 2),
        "population_before": population_before,
        "population_after": region.population,
        "population_loss": population_loss,
        "unrest_before": unrest_before,
    }


def _collect_multi_region_rebellion_joiners(
    world: WorldState,
    seed_region_name: str,
    former_owner: str,
    conflict_type: str,
) -> list[str]:
    queue = [seed_region_name]
    seen = {seed_region_name}
    joined_regions: list[str] = []

    while queue:
        region_name = queue.pop(0)
        region = world.regions[region_name]
        for neighbor_name in region.neighbors:
            if neighbor_name in seen:
                continue
            seen.add(neighbor_name)
            neighbor = world.regions[neighbor_name]
            if not _is_multi_region_rebellion_candidate(
                world,
                neighbor,
                former_owner,
                conflict_type,
            ):
                continue
            joined_regions.append(neighbor_name)
            queue.append(neighbor_name)

    return joined_regions


def mature_rebel_faction(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    if not faction.is_rebel or not faction.proto_state:
        return

    origin_faction = faction.origin_faction
    conflict_type = faction.rebel_conflict_type or REBEL_CONFLICT_SECESSION
    parent_ethnicity = (
        world.factions[origin_faction].primary_ethnicity
        if origin_faction in world.factions
        else faction.primary_ethnicity
    )
    successor_ethnicity = None
    successor_language_profile = None
    successor_population = 0
    parent_population = 0
    if (
        conflict_type == REBEL_CONFLICT_SECESSION
        and parent_ethnicity is not None
    ):
        parent_language_profile = (
            deepcopy(world.ethnicities[parent_ethnicity].language_profile)
            if parent_ethnicity in world.ethnicities
            else LanguageProfile(family_name=parent_ethnicity)
        )
        successor_ethnicity = _generate_successor_ethnicity_name(
            world,
            parent_ethnicity,
            faction_name,
        )
        successor_language_profile = _build_successor_language_profile(
            parent_language_profile,
            successor_ethnicity,
        )
        register_ethnicity(
            world,
            successor_ethnicity,
            language_family=parent_ethnicity,
            parent_ethnicity=parent_ethnicity,
            origin_faction=faction_name,
            language_profile=successor_language_profile,
        )
        successor_population, parent_population = _split_successor_ethnicity_in_regions(
            world,
            faction_name,
            parent_ethnicity,
            successor_ethnicity,
        )
        faction.primary_ethnicity = successor_ethnicity

    faction.proto_state = False
    faction.treasury += REBEL_INDEPENDENCE_TREASURY_BONUS
    if faction.identity is not None:
        if conflict_type == REBEL_CONFLICT_CIVIL_WAR:
            if origin_faction in world.factions:
                faction.identity.culture_name = world.factions[origin_faction].culture_name
                if world.factions[origin_faction].identity is not None:
                    faction.identity.language_profile = deepcopy(
                        world.factions[origin_faction].identity.language_profile
                    )
            faction.identity.set_government_structure(
                faction.identity.polity_tier,
                faction.identity.government_form,
            )
            faction.identity.display_name = _get_civil_war_display_name(
                faction.identity.culture_name,
                faction.identity.polity_tier,
                faction.identity.government_form,
                faction.identity.government_type,
            )
        else:
            if successor_ethnicity is not None:
                faction.identity.culture_name = successor_ethnicity
                faction.identity.language_profile = deepcopy(successor_language_profile)
            faction.identity.set_government_structure(
                "state",
                "council",
                government_type=REBEL_MATURE_GOVERNMENT_TYPE,
            )
            faction.identity.display_name = faction.identity.culture_name

    world.events.append(Event(
        turn=world.turn,
        type="rebel_independence",
        faction=faction_name,
        details={
            "origin_faction": faction.origin_faction,
            "conflict_type": conflict_type,
            "civil_war": conflict_type == REBEL_CONFLICT_CIVIL_WAR,
            "rebel_age": faction.rebel_age,
            "independence_score": round(faction.independence_score, 2),
            "government_type": faction.government_type,
            "parent_ethnicity": parent_ethnicity,
            "successor_ethnicity": successor_ethnicity,
            "successor_population": successor_population,
            "parent_population": parent_population,
        },
        impact={
            "treasury_after": faction.treasury,
            "treasury_change": REBEL_INDEPENDENCE_TREASURY_BONUS,
            "proto_state": False,
            "primary_ethnicity": faction.primary_ethnicity,
        },
        tags=["rebel", "independence", "statehood", conflict_type],
        significance=faction.independence_score,
    ))


def get_rebel_reclaim_bonus(
    attacker_faction_name: str,
    defender_faction_name: str | None,
    world: WorldState,
) -> int:
    if defender_faction_name is None or defender_faction_name not in world.factions:
        return 0

    defender_faction = world.factions[defender_faction_name]
    if (
        not defender_faction.is_rebel
        or defender_faction.origin_faction != attacker_faction_name
        or not defender_faction.proto_state
    ):
        return 0

    independence_ratio = min(
        1.0,
        defender_faction.independence_score / max(0.1, REBEL_FULL_INDEPENDENCE_THRESHOLD),
    )
    bonus = int(round(REBEL_PARENT_RECLAIM_MAX_BONUS * (1.0 - independence_ratio)))
    return max(0, bonus)


def update_rebel_faction_status(world: WorldState) -> None:
    owned_region_counts = get_owned_region_counts(world)

    for faction_name, faction in world.factions.items():
        if not faction.is_rebel:
            continue

        owned_regions = owned_region_counts.get(faction_name, 0)
        if owned_regions <= 0:
            continue

        faction.rebel_age += 1
        faction.independence_score = round(
            min(
                REBEL_FULL_INDEPENDENCE_THRESHOLD,
                faction.independence_score
                + REBEL_INDEPENDENCE_PER_TURN
                + max(0, owned_regions - 1) * REBEL_INDEPENDENCE_PER_EXTRA_REGION,
            ),
            2,
        )
        if (
            faction.proto_state
            and faction.independence_score >= REBEL_FULL_INDEPENDENCE_THRESHOLD
        ):
            mature_rebel_faction(world, faction_name)


def initialize_heartlands(world: WorldState) -> None:
    owned_counts: dict[str, int] = {}

    for region_name, region in sorted(world.regions.items()):
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.unrest = 0.0
            clear_region_unrest_event(region)
            reset_region_crisis_streak(region)
            region.ownership_turns = 0
            continue

        owned_count = owned_counts.get(region.owner, 0)
        if owned_count == 0:
            region.homeland_faction_id = region.owner
            set_region_integration(
                region,
                owner=region.owner,
                score=HOMELAND_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="homeland",
            )
        else:
            set_region_integration(
                region,
                owner=region.owner,
                score=CORE_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="core",
            )
        owned_counts[region.owner] = owned_count + 1
        region.unrest = 0.0
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)


def handle_region_owner_change(region: Region, new_owner: str | None) -> None:
    previous_owner = region.owner
    if previous_owner == new_owner:
        return

    region.owner = new_owner
    if previous_owner is not None and new_owner is not None:
        region.conquest_count += 1

    if new_owner is None:
        set_region_integration(
            region,
            owner=None,
            score=0.0,
            ownership_turns=0,
            core_status="frontier",
        )
        set_region_unrest(region, 0.0)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
        return

    base_score = HOMELAND_INTEGRATION_SCORE if region.homeland_faction_id == new_owner else CONQUEST_INTEGRATION_SCORE
    base_status = "homeland" if region.homeland_faction_id == new_owner else "frontier"
    set_region_integration(
        region,
        owner=new_owner,
        score=base_score,
        ownership_turns=1,
        core_status=base_status,
    )
    if region.homeland_faction_id == new_owner:
        set_region_unrest(region, 0.0)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
    elif previous_owner is None:
        set_region_unrest(region, UNREST_EXPANSION_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
    else:
        set_region_unrest(region, UNREST_CONQUEST_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)


def get_region_unrest_pressure(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.0
    if region.homeland_faction_id == region.owner:
        return -UNREST_DECAY_PER_TURN

    owner_faction = world.factions[region.owner]
    climate_affinity = get_region_climate_affinity(region, world)
    climate_pressure = (1.0 - climate_affinity) * UNREST_CLIMATE_PRESSURE_FACTOR
    integration_gap = max(0.0, CORE_INTEGRATION_SCORE - region.integration_score) / CORE_INTEGRATION_SCORE
    integration_pressure = integration_gap * UNREST_INTEGRATION_PRESSURE_FACTOR
    frontier_pressure = (
        UNREST_FRONTIER_PRESSURE
        if get_region_core_status(region) == "frontier"
        else 0.0
    )
    frontier_burden = (
        get_faction_frontier_burden(world, region.owner)
        * UNREST_FRONTIER_BURDEN_FACTOR
        * get_faction_realm_size_unrest_factor(owner_faction)
    )
    ethnic_pressure = get_region_ethnic_unrest_modifier(region, world)
    regime_pressure = get_region_regime_contestation_unrest_modifier(region, world)
    external_regime_pressure = get_region_external_regime_agitation_modifier(region, world)
    stability_divisor = max(0.5, get_faction_stability_modifier(owner_faction))
    return (
        climate_pressure
        + integration_pressure
        + frontier_pressure
        + frontier_burden
        + ethnic_pressure
        + regime_pressure
        + external_regime_pressure
    ) / stability_divisor - UNREST_DECAY_PER_TURN


def resolve_unrest_events(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            clear_region_unrest_event(region)
            continue
        if region.unrest_event_turns_remaining > 0:
            continue

        if region.unrest >= UNREST_CRITICAL_THRESHOLD:
            set_region_unrest_event(region, level="crisis", duration=UNREST_CRISIS_DURATION)
        elif region.unrest >= UNREST_MODERATE_THRESHOLD:
            set_region_unrest_event(region, level="disturbance", duration=UNREST_DISTURBANCE_DURATION)
        else:
            continue

        _emit_regime_agitation_event(world, region)
        faction = world.factions[region.owner]
        treasury_hit = min(get_region_unrest_event_cost(region), faction.treasury)
        faction.treasury -= treasury_hit
        world.events.append(Event(
            turn=world.turn,
            type=f"unrest_{region.unrest_event_level}",
            faction=region.owner,
            region=region.name,
            details={
                "unrest": round(region.unrest, 2),
                "event_level": region.unrest_event_level,
                "duration": region.unrest_event_turns_remaining,
            },
            impact={
                "treasury_change": -treasury_hit,
                "treasury_after": faction.treasury,
                "integration_stalled": region.unrest_event_level == "crisis",
            },
            tags=["unrest", region.unrest_event_level],
            significance=region.unrest,
        ))


def apply_unrest_secession(world: WorldState, region: Region) -> None:
    if region.owner is None:
        return

    former_owner = region.owner
    conflict_type = _determine_rebel_conflict_type(world, region, former_owner)
    adjacent_rebel = _find_adjacent_rebel_destination(
        world,
        region,
        former_owner,
        conflict_type,
    )
    restored_faction = False
    joined_existing_rebellion = adjacent_rebel is not None
    if adjacent_rebel is not None:
        rebel_faction_name = adjacent_rebel
    else:
        rebel_faction_name, restored_faction = create_rebel_faction(world, region, former_owner)
        if restored_faction:
            conflict_type = "restoration"
        else:
            conflict_type = world.factions[rebel_faction_name].rebel_conflict_type or conflict_type

    seed_transfer = _transfer_region_to_rebellion(world, region, rebel_faction_name)
    joined_region_names = _collect_multi_region_rebellion_joiners(
        world,
        region.name,
        former_owner,
        conflict_type if conflict_type != "restoration" else REBEL_CONFLICT_SECESSION,
    )
    joined_region_transfers = [
        _transfer_region_to_rebellion(world, world.regions[joined_region_name], rebel_faction_name)
        for joined_region_name in joined_region_names
    ]
    total_resource_change = seed_transfer["resource_change"] + sum(
        transfer["resource_change"]
        for transfer in joined_region_transfers
    )
    total_population_before = seed_transfer["population_before"] + sum(
        transfer["population_before"]
        for transfer in joined_region_transfers
    )
    total_population_after = seed_transfer["population_after"] + sum(
        transfer["population_after"]
        for transfer in joined_region_transfers
    )

    world.events.append(Event(
        turn=world.turn,
        type="unrest_secession",
        faction=former_owner,
        region=region.name,
        details={
            "former_owner": former_owner,
            "rebel_faction": rebel_faction_name,
            "conflict_type": conflict_type,
            "civil_war": conflict_type == REBEL_CONFLICT_CIVIL_WAR,
            "restored_faction": rebel_faction_name if restored_faction else None,
            "restoration": restored_faction,
            "joined_existing_rebellion": joined_existing_rebellion,
            "revived_ethnicity": (
                world.factions[rebel_faction_name].primary_ethnicity
                if restored_faction
                else None
            ),
            "restoration_region_count": (
                len(
                    [
                        other_region
                        for other_region in world.regions.values()
                        if (
                            other_region.owner != former_owner
                            and get_region_dominant_ethnicity(other_region)
                            == world.factions[rebel_faction_name].primary_ethnicity
                        )
                    ]
                )
                if restored_faction
                else 0
            ),
            "unrest": seed_transfer["unrest_before"],
            "population_before": seed_transfer["population_before"],
            "population_after": region.population,
            "population_loss": seed_transfer["population_loss"],
            "joined_regions": joined_region_names,
            "joined_region_count": len(joined_region_names),
            "joined_region_population_loss": sum(
                transfer["population_loss"]
                for transfer in joined_region_transfers
            ),
        },
        impact={
            "owner_after": rebel_faction_name,
            "resource_change": total_resource_change,
            "new_resources": region.resources,
            "population_change": total_population_after - total_population_before,
            "population_after": total_population_after,
            "joined_region_count": len(joined_region_names),
        },
        tags=[
            "unrest",
            "secession" if conflict_type != REBEL_CONFLICT_CIVIL_WAR else "civil_war",
            "collapse",
            *(["regional_uprising"] if joined_region_names else []),
            *(["restoration", "revival"] if restored_faction else []),
        ],
        significance=UNREST_SECESSION_THRESHOLD,
    ))


def update_region_integration(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.unrest = 0.0
            clear_region_unrest_event(region)
            region.ownership_turns = 0
            reset_region_crisis_streak(region)
            set_region_secession_cooldown(region, 0)
            continue

        if region.secession_cooldown_turns > 0:
            region.secession_cooldown_turns -= 1

        if region.integrated_owner != region.owner:
            handle_region_owner_change(region, region.owner)
            continue

        if region.homeland_faction_id == region.owner:
            region.integration_score = max(region.integration_score, HOMELAND_INTEGRATION_SCORE)
            region.ownership_turns += 1
            region.core_status = "homeland"
            set_region_unrest(region, region.unrest - UNREST_DECAY_PER_TURN)
            reset_region_crisis_streak(region)
            if region.unrest_event_turns_remaining > 0:
                region.unrest_event_turns_remaining -= 1
                if region.unrest_event_turns_remaining <= 0:
                    clear_region_unrest_event(region)
            continue

        region.ownership_turns += 1
        if region.unrest_event_level == "crisis":
            region.unrest_crisis_streak += 1
            apply_region_population_loss(
                region,
                POPULATION_UNREST_CRISIS_LOSS,
                minimum_loss=1,
            )
        else:
            reset_region_crisis_streak(region)

        if region.unrest_event_level != "crisis":
            climate_modifier = get_region_climate_integration_modifier(region, world)
            ethnic_multiplier = get_region_ethnic_integration_multiplier(region, world)
            government_multiplier = get_faction_integration_modifier(
                world.factions.get(region.owner),
            )
            if region.integration_score < CORE_INTEGRATION_SCORE:
                base_gain = PER_TURN_FRONTIER_GAIN
            else:
                base_gain = PER_TURN_CORE_GAIN
            region.integration_score += max(
                0.0,
                (base_gain * ethnic_multiplier * government_multiplier) + climate_modifier,
            )
        region.core_status = get_region_core_status(region)
        set_region_unrest(region, region.unrest + get_region_unrest_pressure(region, world))
        owner_faction = world.factions.get(region.owner)
        if owner_faction is not None and owner_faction.is_rebel:
            if (
                region.unrest_event_level == "crisis"
                and region.unrest_crisis_streak >= UNREST_SECESSION_CRISIS_TURNS
                and region.unrest >= UNREST_SECESSION_THRESHOLD
            ):
                set_region_unrest(
                    region,
                    max(
                        UNREST_CRITICAL_THRESHOLD - 0.5,
                        region.unrest - REBEL_RECURSIVE_UNREST_REDUCTION,
                    ),
                )
                clear_region_unrest_event(region)
                reset_region_crisis_streak(region)
            if region.unrest_event_turns_remaining > 0:
                region.unrest_event_turns_remaining -= 1
                if region.unrest_event_turns_remaining <= 0:
                    clear_region_unrest_event(region)
            continue
        if (
            region.unrest_event_level == "crisis"
            and region.secession_cooldown_turns <= 0
            and region.unrest_crisis_streak >= UNREST_SECESSION_CRISIS_TURNS
            and region.unrest >= UNREST_SECESSION_THRESHOLD
        ):
            apply_unrest_secession(world, region)
            continue
        if region.unrest_event_turns_remaining > 0:
            region.unrest_event_turns_remaining -= 1
            if region.unrest_event_turns_remaining <= 0:
                clear_region_unrest_event(region)


def build_region_snapshot(world: WorldState) -> dict[str, dict]:
    return {
        region_name: {
            "owner": region.owner,
            "resources": region.resources,
            "resource_fixed_endowments": normalize_resource_map(region.resource_fixed_endowments),
            "resource_wild_endowments": normalize_resource_map(region.resource_wild_endowments),
            "resource_suitability": normalize_resource_map(region.resource_suitability),
            "resource_established": normalize_resource_map(region.resource_established),
            "resource_output": normalize_resource_map(region.resource_output),
            "resource_effective_output": normalize_resource_map(region.resource_effective_output),
            "resource_damage": normalize_resource_map(region.resource_damage),
            "resource_isolation_factor": round(region.resource_isolation_factor, 3),
            "resource_route_depth": region.resource_route_depth,
            "resource_route_cost": round(region.resource_route_cost, 3),
            "resource_route_anchor": region.resource_route_anchor,
            "resource_route_bottleneck": round(region.resource_route_bottleneck, 3),
            "resource_profile": get_region_resource_summary(
                fixed_endowments=region.resource_fixed_endowments,
                wild_endowments=region.resource_wild_endowments,
                established=region.resource_established,
                output=region.resource_output,
            )["resource_profile"],
            "resource_output_summary": get_region_resource_summary(
                fixed_endowments=region.resource_fixed_endowments,
                wild_endowments=region.resource_wild_endowments,
                established=region.resource_established,
                output=region.resource_effective_output or region.resource_output,
            )["resource_output"],
            "taxable_value": get_region_taxable_value(region, world),
            "infrastructure_level": round(region.infrastructure_level, 2),
            "agriculture_level": round(region.agriculture_level, 2),
            "pastoral_level": round(region.pastoral_level, 2),
            "extractive_level": round(region.extractive_level, 2),
            "population": region.population,
            "productive_capacity": get_region_productive_capacity(region, world),
            "population_pressure": get_region_population_pressure(region),
            "surplus": get_region_surplus(region, world),
            "surplus_label": get_region_surplus_label(region, world),
            "ethnic_composition": dict(region.ethnic_composition),
            "dominant_ethnicity": get_region_dominant_ethnicity(region),
            "ethnic_claimants": get_region_ethnic_claimants(region, world),
            "owner_primary_ethnicity": get_region_owner_primary_ethnicity(region, world),
            "owner_has_ethnic_claim": faction_has_ethnic_claim(world, region, region.owner),
            "ruling_ethnic_affinity": round(get_region_ruling_ethnic_affinity(region, world), 2),
            "external_regime_agitators": get_region_external_regime_agitators(region, world),
            "external_regime_agitation": round(get_region_external_regime_agitation_modifier(region, world), 3),
            "display_name": region.display_name,
            "founding_name": region.founding_name,
            "original_namer_faction_id": region.original_namer_faction_id,
            "terrain_tags": list(region.terrain_tags),
            "climate": region.climate,
            "homeland_faction_id": region.homeland_faction_id,
            "integrated_owner": region.integrated_owner,
            "integration_score": round(region.integration_score, 2),
            "core_status": region.core_status,
            "settlement_level": region.settlement_level,
            "unrest": round(region.unrest, 2),
            "unrest_event_level": region.unrest_event_level,
            "unrest_event_turns_remaining": region.unrest_event_turns_remaining,
            "unrest_crisis_streak": region.unrest_crisis_streak,
        }
        for region_name, region in world.regions.items()
    }


def initialize_region_history(world: WorldState) -> None:
    world.region_history = [deepcopy(build_region_snapshot(world))]


def record_region_history(world: WorldState) -> None:
    world.region_history.append(deepcopy(build_region_snapshot(world)))
