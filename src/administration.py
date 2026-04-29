from __future__ import annotations

from src.config import (
    ADMIN_BASE_CAPACITY_PER_REGION,
    ADMIN_BURDEN_CORE,
    ADMIN_BURDEN_FRONTIER,
    ADMIN_BURDEN_HOMELAND,
    ADMIN_DISTANCE_PER_ROUTE_DEPTH,
    ADMIN_FOREIGN_BORDER_DISTANCE,
    ADMIN_HOSTILE_BORDER_DISTANCE,
    ADMIN_LEGITIMACY_WEIGHT,
    ADMIN_MOBILITY_CAPACITY_FACTOR,
    ADMIN_OVEREXTENSION_PENALTY_FACTOR,
    ADMIN_POPULATION_BURDEN_FACTOR,
    ADMIN_POPULATION_BURDEN_MAX,
    ADMIN_RELIGIOUS_LEGITIMACY_WEIGHT,
    ADMIN_SUPPORT_CAPACITY_FACTOR,
    ADMIN_SUPPORT_INFRASTRUCTURE_FACTOR,
    ADMIN_SUPPORT_INTEGRATION_FACTOR,
    ADMIN_SUPPORT_MARKET_FACTOR,
    ADMIN_SUPPORT_ROAD_FACTOR,
    ADMIN_SUPPORT_SETTLEMENT_BONUSES,
    ADMIN_SUPPORT_STOREHOUSE_FACTOR,
    ADMIN_TAXABLE_CAPACITY_FACTOR,
    ADMIN_UNREST_BURDEN_FACTOR,
)
from src.diplomacy import get_relationship_status
from src.governance import (
    get_faction_administrative_capacity_modifier,
    get_faction_administrative_reach_modifier,
)
from src.internal_politics import get_faction_elite_effects
from src.models import Region, WorldState
from src.region_state import get_region_core_status
from src.technology import (
    TECH_ROAD_ADMINISTRATION,
    TECH_TEMPLE_RECORDKEEPING,
    get_faction_institutional_technology,
    get_region_institutional_technology,
    get_region_technology_adoption,
)
from src.urban import get_faction_urban_capacity_bonus, get_region_urban_effects


def get_region_administrative_support(region: Region) -> float:
    support = ADMIN_SUPPORT_SETTLEMENT_BONUSES.get(region.settlement_level, 0.0)
    support += region.infrastructure_level * ADMIN_SUPPORT_INFRASTRUCTURE_FACTOR
    support += region.road_level * ADMIN_SUPPORT_ROAD_FACTOR
    support += region.market_level * ADMIN_SUPPORT_MARKET_FACTOR
    support += region.storehouse_level * ADMIN_SUPPORT_STOREHOUSE_FACTOR
    support += region.integration_score * ADMIN_SUPPORT_INTEGRATION_FACTOR
    support += get_region_technology_adoption(region, TECH_ROAD_ADMINISTRATION) * 0.05
    support += get_region_technology_adoption(region, TECH_TEMPLE_RECORDKEEPING) * 0.06
    support += get_region_urban_effects(region).get("administrative_support_bonus", 0.0)
    status = get_region_core_status(region)
    if status == "homeland":
        support += 0.18
    elif status == "core":
        support += 0.08
    return round(max(0.0, support), 3)


def get_region_administrative_distance(region: Region, world: WorldState) -> float:
    if region.owner is None or get_region_core_status(region) == "homeland":
        return 0.0

    distance = float(region.resource_route_depth or 0) * ADMIN_DISTANCE_PER_ROUTE_DEPTH
    if not region.resource_route_depth:
        distance += 0.1 if get_region_core_status(region) == "frontier" else 0.04
    if region.resource_route_mode in {"sea", "river"}:
        distance = max(0.0, distance - 0.04)

    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None or neighbor.owner == region.owner:
            continue
        distance += ADMIN_FOREIGN_BORDER_DISTANCE
        relation = get_relationship_status(world, region.owner, neighbor.owner)
        if relation in {"rival", "war", "truce"}:
            distance += ADMIN_HOSTILE_BORDER_DISTANCE

    return round(min(1.8, distance), 3)


def get_region_administrative_burden(region: Region, world: WorldState) -> float:
    status = get_region_core_status(region)
    burden = {
        "homeland": ADMIN_BURDEN_HOMELAND,
        "core": ADMIN_BURDEN_CORE,
        "frontier": ADMIN_BURDEN_FRONTIER,
    }.get(status, ADMIN_BURDEN_FRONTIER)
    burden += get_region_administrative_distance(region, world)
    burden += min(
        ADMIN_POPULATION_BURDEN_MAX,
        max(0.0, region.population) * ADMIN_POPULATION_BURDEN_FACTOR,
    )
    burden += region.unrest * ADMIN_UNREST_BURDEN_FACTOR
    if region.unrest_event_level == "disturbance":
        burden += 0.12
    elif region.unrest_event_level == "crisis":
        burden += 0.24
    return round(max(0.35, burden), 3)


def refresh_administrative_state(world: WorldState) -> None:
    per_faction_support: dict[str, float] = {}
    per_faction_distance: dict[str, float] = {}
    per_faction_regions: dict[str, int] = {}

    for faction in world.factions.values():
        faction.administrative_capacity = 0.0
        faction.administrative_load = 0.0
        faction.administrative_efficiency = 1.0
        faction.administrative_reach = 1.0
        faction.administrative_overextension = 0.0
        faction.administrative_overextension_penalty = 0.0

    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            region.administrative_burden = 0.0
            region.administrative_support = 0.0
            region.administrative_distance = 0.0
            region.administrative_autonomy = 0.0
            region.administrative_tax_capture = 1.0
            continue

        owner_name = region.owner
        region.administrative_support = get_region_administrative_support(region)
        region.administrative_distance = get_region_administrative_distance(region, world)
        region.administrative_burden = get_region_administrative_burden(region, world)
        region.administrative_autonomy = 0.0
        region.administrative_tax_capture = 1.0

        per_faction_support[owner_name] = (
            per_faction_support.get(owner_name, 0.0) + region.administrative_support
        )
        per_faction_distance[owner_name] = (
            per_faction_distance.get(owner_name, 0.0) + region.administrative_distance
        )
        per_faction_regions[owner_name] = per_faction_regions.get(owner_name, 0) + 1
        world.factions[owner_name].administrative_load = round(
            world.factions[owner_name].administrative_load + region.administrative_burden,
            3,
        )

    for faction_name, faction in world.factions.items():
        region_count = per_faction_regions.get(faction_name, 0)
        if region_count <= 0:
            continue
        average_support = per_faction_support.get(faction_name, 0.0) / region_count
        average_distance = per_faction_distance.get(faction_name, 0.0) / region_count
        legitimacy_support = (
            0.78
            + (float(faction.succession.legitimacy or 0.0) * ADMIN_LEGITIMACY_WEIGHT)
            + (
                float(faction.religion.religious_legitimacy or 0.0)
                * ADMIN_RELIGIOUS_LEGITIMACY_WEIGHT
            )
        )
        capacity = (
            region_count
            * ADMIN_BASE_CAPACITY_PER_REGION
            * get_faction_administrative_capacity_modifier(faction)
            * (1.0 + (average_support * ADMIN_SUPPORT_CAPACITY_FACTOR))
            * legitimacy_support
        )
        capacity += (
            max(0.0, float(faction.derived_capacity.get("mobility_capacity", 0.0)))
            * ADMIN_MOBILITY_CAPACITY_FACTOR
        )
        capacity += (
            max(0.0, float(faction.derived_capacity.get("taxable_value", 0.0)))
            * ADMIN_TAXABLE_CAPACITY_FACTOR
        )
        capacity *= 1.0 + get_faction_urban_capacity_bonus(world, faction_name)
        capacity *= 1.0 + get_faction_elite_effects(faction).get("administrative_capacity_factor", 0.0)
        capacity *= (
            1.0
            + get_faction_institutional_technology(faction, TECH_TEMPLE_RECORDKEEPING) * 0.08
            + get_faction_institutional_technology(faction, TECH_ROAD_ADMINISTRATION) * 0.05
        )

        load = max(0.01, float(faction.administrative_load or 0.0))
        efficiency = max(0.45, min(1.15, capacity / load))
        reach = max(
            0.45,
            min(
                1.15,
                (1.02 - (average_distance * 0.28) + (average_support * 0.06))
                * get_faction_administrative_reach_modifier(faction),
            ),
        )
        reach *= 1.0 + get_faction_elite_effects(faction).get("administrative_reach_factor", 0.0)
        reach = max(0.35, min(1.18, reach))
        overextension = max(0.0, load - capacity)

        faction.administrative_capacity = round(capacity, 3)
        faction.administrative_efficiency = round(efficiency, 3)
        faction.administrative_reach = round(reach, 3)
        faction.administrative_overextension = round(overextension, 3)
        faction.administrative_overextension_penalty = round(
            overextension * ADMIN_OVEREXTENSION_PENALTY_FACTOR,
            2,
        )

        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            autonomy = max(
                0.0,
                region.administrative_burden
                - (
                    0.62
                    + (region.administrative_support * 0.9)
                    + (efficiency * 0.85)
                    + (reach * 0.35)
                ),
            )
            tax_capture = (
                (efficiency * 0.78)
                + (reach * 0.18)
                + (region.administrative_support * 0.14)
                - (autonomy * 0.16)
            )
            tax_capture += get_region_institutional_technology(
                region,
                world,
                TECH_TEMPLE_RECORDKEEPING,
            ) * 0.035
            status = get_region_core_status(region)
            if status == "homeland":
                tax_capture += 0.05
            elif status == "core":
                tax_capture += 0.02
            elif status == "frontier":
                tax_capture -= 0.04
            region.administrative_autonomy = round(min(2.5, autonomy), 3)
            region.administrative_tax_capture = round(max(0.42, min(1.05, tax_capture)), 3)
