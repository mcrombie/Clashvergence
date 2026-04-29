from __future__ import annotations

from src.models import Region, WorldState
from src.region_state import get_region_core_status
from src.resources import (
    RESOURCE_COPPER,
    RESOURCE_SALT,
    RESOURCE_STONE,
    RESOURCE_TEXTILES,
    RESOURCE_TIMBER,
)
from src.technology import (
    ALL_TECHNOLOGIES,
    TECH_COPPER_WORKING,
    TECH_MARKET_ACCOUNTING,
    TECH_ORGANIZED_LEVIES,
    TECH_TEMPLE_RECORDKEEPING,
    get_region_technology_adoption,
)

URBAN_NONE = "none"
URBAN_CAPITAL = "capital"
URBAN_CRAFT_CENTER = "craft_center"
URBAN_PORT_CITY = "port_city"
URBAN_TEMPLE_CITY = "temple_city"
URBAN_FRONTIER_FORT = "frontier_fort"
URBAN_MINING_TOWN = "mining_town"
URBAN_SCHOLARLY_HUB = "scholarly_hub"
URBAN_MARKET_TOWN = "market_town"

ALL_URBAN_SPECIALIZATIONS = (
    URBAN_NONE,
    URBAN_CAPITAL,
    URBAN_CRAFT_CENTER,
    URBAN_PORT_CITY,
    URBAN_TEMPLE_CITY,
    URBAN_FRONTIER_FORT,
    URBAN_MINING_TOWN,
    URBAN_SCHOLARLY_HUB,
    URBAN_MARKET_TOWN,
)

URBAN_SPECIALIZATION_LABELS = {
    URBAN_NONE: "None",
    URBAN_CAPITAL: "Capital",
    URBAN_CRAFT_CENTER: "Craft Center",
    URBAN_PORT_CITY: "Port City",
    URBAN_TEMPLE_CITY: "Temple City",
    URBAN_FRONTIER_FORT: "Frontier Fort",
    URBAN_MINING_TOWN: "Mining Town",
    URBAN_SCHOLARLY_HUB: "Scholarly Hub",
    URBAN_MARKET_TOWN: "Market Town",
}

URBAN_ROLE_THRESHOLD = 0.85

URBAN_BASE_EFFECTS = {
    URBAN_CAPITAL: {
        "administrative_support_bonus": 0.14,
        "administrative_capacity_bonus": 0.1,
        "taxable_value_bonus": 0.16,
        "tools_output_factor": 0.03,
        "urban_surplus_factor": 0.1,
        "trade_value_factor": 0.05,
        "technology_pressure_bonus": 0.008,
        "extraction_output_factor": 0.0,
        "pilgrimage_factor": 0.03,
        "clergy_support_bonus": 0.0,
    },
    URBAN_CRAFT_CENTER: {
        "administrative_support_bonus": 0.03,
        "administrative_capacity_bonus": 0.02,
        "taxable_value_bonus": 0.14,
        "tools_output_factor": 0.12,
        "urban_surplus_factor": 0.03,
        "trade_value_factor": 0.04,
        "technology_pressure_bonus": 0.009,
        "extraction_output_factor": 0.0,
        "pilgrimage_factor": 0.0,
        "clergy_support_bonus": 0.0,
    },
    URBAN_PORT_CITY: {
        "administrative_support_bonus": 0.04,
        "administrative_capacity_bonus": 0.02,
        "taxable_value_bonus": 0.11,
        "tools_output_factor": 0.02,
        "urban_surplus_factor": 0.06,
        "trade_value_factor": 0.16,
        "technology_pressure_bonus": 0.006,
        "extraction_output_factor": 0.0,
        "pilgrimage_factor": 0.0,
        "clergy_support_bonus": 0.0,
    },
    URBAN_TEMPLE_CITY: {
        "administrative_support_bonus": 0.05,
        "administrative_capacity_bonus": 0.03,
        "taxable_value_bonus": 0.05,
        "tools_output_factor": 0.0,
        "urban_surplus_factor": 0.04,
        "trade_value_factor": 0.02,
        "technology_pressure_bonus": 0.014,
        "extraction_output_factor": 0.0,
        "pilgrimage_factor": 0.16,
        "clergy_support_bonus": 0.012,
    },
    URBAN_FRONTIER_FORT: {
        "administrative_support_bonus": 0.1,
        "administrative_capacity_bonus": 0.03,
        "taxable_value_bonus": 0.02,
        "tools_output_factor": 0.0,
        "urban_surplus_factor": 0.0,
        "trade_value_factor": 0.0,
        "technology_pressure_bonus": 0.004,
        "extraction_output_factor": 0.04,
        "pilgrimage_factor": 0.0,
        "clergy_support_bonus": 0.0,
    },
    URBAN_MINING_TOWN: {
        "administrative_support_bonus": 0.03,
        "administrative_capacity_bonus": 0.01,
        "taxable_value_bonus": 0.07,
        "tools_output_factor": 0.08,
        "urban_surplus_factor": 0.0,
        "trade_value_factor": 0.02,
        "technology_pressure_bonus": 0.004,
        "extraction_output_factor": 0.14,
        "pilgrimage_factor": 0.0,
        "clergy_support_bonus": 0.0,
    },
    URBAN_SCHOLARLY_HUB: {
        "administrative_support_bonus": 0.03,
        "administrative_capacity_bonus": 0.04,
        "taxable_value_bonus": 0.05,
        "tools_output_factor": 0.02,
        "urban_surplus_factor": 0.05,
        "trade_value_factor": 0.03,
        "technology_pressure_bonus": 0.024,
        "extraction_output_factor": 0.0,
        "pilgrimage_factor": 0.02,
        "clergy_support_bonus": 0.004,
    },
    URBAN_MARKET_TOWN: {
        "administrative_support_bonus": 0.02,
        "administrative_capacity_bonus": 0.01,
        "taxable_value_bonus": 0.09,
        "tools_output_factor": 0.01,
        "urban_surplus_factor": 0.06,
        "trade_value_factor": 0.11,
        "technology_pressure_bonus": 0.005,
        "extraction_output_factor": 0.0,
        "pilgrimage_factor": 0.0,
        "clergy_support_bonus": 0.0,
    },
}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def format_urban_specialization(role: str | None) -> str:
    return URBAN_SPECIALIZATION_LABELS.get(role or URBAN_NONE, str(role).replace("_", " ").title())


def _settlement_factor(region: Region) -> float:
    return {
        "wild": 0.0,
        "rural": 0.28,
        "town": 0.72,
        "city": 1.0,
    }.get(region.settlement_level, 0.0)


def _urban_eligible(region: Region) -> bool:
    return region.owner is not None and region.population > 0 and region.settlement_level in {"town", "city"}


def _owned_regions(world: WorldState, faction_name: str) -> list[Region]:
    return [region for region in world.regions.values() if region.owner == faction_name]


def _foreign_neighbor_count(region: Region, world: WorldState) -> int:
    return sum(
        1
        for neighbor_name in region.neighbors
        if world.regions[neighbor_name].owner is not None
        and world.regions[neighbor_name].owner != region.owner
    )


def _urban_population_factor(region: Region) -> float:
    return min(1.25, max(0.0, float(region.population or 0)) / 420.0)


def _average_technology(region: Region) -> float:
    if not ALL_TECHNOLOGIES:
        return 0.0
    return sum(
        float((region.technology_adoption or {}).get(technology_key, 0.0))
        for technology_key in ALL_TECHNOLOGIES
    ) / len(ALL_TECHNOLOGIES)


def score_capital_candidate(region: Region, world: WorldState) -> float:
    if region.owner is None or region.population <= 0:
        return 0.0
    core_status = get_region_core_status(region)
    score = (
        _settlement_factor(region) * 1.15
        + _urban_population_factor(region) * 0.95
        + float(region.administrative_support or 0.0) * 1.2
        + float(region.infrastructure_level or 0.0) * 0.34
        + float(region.road_level or 0.0) * 0.28
        + float(region.market_level or 0.0) * 0.22
        + float(region.integration_score or 0.0) * 0.035
    )
    if core_status == "homeland":
        score += 1.0
    elif core_status == "core":
        score += 0.55
    score -= min(0.9, float(region.unrest or 0.0) * 0.1)
    return round(max(0.0, score), 3)


def choose_faction_capital(world: WorldState, faction_name: str) -> str | None:
    candidates = [
        (score_capital_candidate(region, world), region.name)
        for region in _owned_regions(world, faction_name)
    ]
    candidates = [candidate for candidate in candidates if candidate[0] > 0.0]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[1]


def _score_port_city(region: Region, world: WorldState) -> float:
    if not _urban_eligible(region):
        return 0.0
    has_water = "coast" in region.terrain_tags or "riverland" in region.terrain_tags
    has_gateway = region.trade_gateway_role != "none"
    if not has_water and not has_gateway:
        return 0.0
    score = (
        _settlement_factor(region) * 0.65
        + float(region.market_level or 0.0) * 0.36
        + float(region.storehouse_level or 0.0) * 0.25
        + float(region.road_level or 0.0) * 0.12
        + min(1.2, float(region.trade_throughput or 0.0) * 0.035)
        + min(1.1, float(region.trade_foreign_flow or 0.0) * 0.38)
        + min(0.9, float(region.trade_foreign_value or 0.0) * 0.22)
        + min(0.7, float(region.trade_value_bonus or 0.0) * 0.12)
    )
    if region.trade_gateway_role == "sea_gateway":
        score += 0.58
    elif region.trade_gateway_role != "none":
        score += 0.42
    elif has_water:
        score += 0.22
    return round(max(0.0, score), 3)


def _score_mining_town(region: Region) -> float:
    if not _urban_eligible(region):
        return 0.0
    extractive_output = (
        float(region.resource_effective_output.get(RESOURCE_COPPER, 0.0))
        + float(region.resource_effective_output.get(RESOURCE_STONE, 0.0))
        + float(region.resource_effective_output.get(RESOURCE_SALT, 0.0))
        + float(region.resource_effective_output.get(RESOURCE_TIMBER, 0.0)) * 0.55
    )
    extractive_site = (
        float(region.copper_mine_level or 0.0)
        + float(region.stone_quarry_level or 0.0)
        + float(region.extractive_level or 0.0)
        + float(region.logging_camp_level or 0.0) * 0.6
    )
    endowment = (
        float(region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0))
        + float(region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0))
        + float(region.resource_fixed_endowments.get(RESOURCE_SALT, 0.0))
        + float(region.resource_wild_endowments.get(RESOURCE_TIMBER, 0.0)) * 0.45
    )
    return round(
        max(0.0, _settlement_factor(region) * 0.42 + extractive_output * 0.44 + extractive_site * 0.38 + endowment * 0.24),
        3,
    )


def _score_temple_city(region: Region) -> float:
    if not _urban_eligible(region):
        return 0.0
    score = (
        _settlement_factor(region) * 0.55
        + float(region.shrine_level or 0.0) * 0.75
        + float(region.pilgrimage_value or 0.0) * 0.38
        + get_region_technology_adoption(region, TECH_TEMPLE_RECORDKEEPING) * 0.55
        + float(region.market_level or 0.0) * 0.1
    )
    if region.sacred_religion:
        score += 0.55
    return round(max(0.0, score), 3)


def _score_frontier_fort(region: Region, world: WorldState) -> float:
    if not _urban_eligible(region):
        return 0.0
    frontier = get_region_core_status(region) == "frontier"
    border_pressure = _foreign_neighbor_count(region, world)
    if not frontier and border_pressure <= 0:
        return 0.0
    score = (
        _settlement_factor(region) * 0.45
        + float(region.road_level or 0.0) * 0.32
        + float(region.infrastructure_level or 0.0) * 0.22
        + get_region_technology_adoption(region, TECH_ORGANIZED_LEVIES) * 0.42
        + min(0.9, border_pressure * 0.24)
    )
    if frontier:
        score += 0.45
    return round(max(0.0, score), 3)


def _score_craft_center(region: Region) -> float:
    if not _urban_eligible(region):
        return 0.0
    craft_inputs = (
        float(region.resource_effective_output.get(RESOURCE_TEXTILES, 0.0))
        + float(region.resource_effective_output.get(RESOURCE_SALT, 0.0)) * 0.45
        + float(region.resource_effective_output.get(RESOURCE_COPPER, 0.0)) * 0.55
        + float(region.resource_effective_output.get(RESOURCE_TIMBER, 0.0)) * 0.35
    )
    return round(
        max(
            0.0,
            _settlement_factor(region) * 0.52
            + float(region.market_level or 0.0) * 0.34
            + float(region.storehouse_level or 0.0) * 0.26
            + float(region.infrastructure_level or 0.0) * 0.24
            + craft_inputs * 0.22
            + get_region_technology_adoption(region, TECH_COPPER_WORKING) * 0.18
            + get_region_technology_adoption(region, TECH_MARKET_ACCOUNTING) * 0.2,
        ),
        3,
    )


def _score_scholarly_hub(region: Region) -> float:
    if not _urban_eligible(region):
        return 0.0
    return round(
        max(
            0.0,
            _settlement_factor(region) * 0.48
            + _average_technology(region) * 1.15
            + get_region_technology_adoption(region, TECH_TEMPLE_RECORDKEEPING) * 0.32
            + get_region_technology_adoption(region, TECH_MARKET_ACCOUNTING) * 0.22
            + float(region.shrine_level or 0.0) * 0.12
            + float(region.market_level or 0.0) * 0.18,
        ),
        3,
    )


def _score_market_town(region: Region) -> float:
    if not _urban_eligible(region):
        return 0.0
    return round(
        max(
            0.0,
            _settlement_factor(region) * 0.5
            + float(region.market_level or 0.0) * 0.45
            + float(region.storehouse_level or 0.0) * 0.18
            + min(1.0, float(region.trade_throughput or 0.0) * 0.04)
            + min(0.9, float(region.trade_hub_value or 0.0) * 0.2)
            + min(0.7, float(region.trade_value_bonus or 0.0) * 0.1),
        ),
        3,
    )


def score_region_urban_roles(region: Region, world: WorldState) -> dict[str, float]:
    return {
        URBAN_CRAFT_CENTER: _score_craft_center(region),
        URBAN_PORT_CITY: _score_port_city(region, world),
        URBAN_TEMPLE_CITY: _score_temple_city(region),
        URBAN_FRONTIER_FORT: _score_frontier_fort(region, world),
        URBAN_MINING_TOWN: _score_mining_town(region),
        URBAN_SCHOLARLY_HUB: _score_scholarly_hub(region),
        URBAN_MARKET_TOWN: _score_market_town(region),
    }


def choose_region_urban_specialization(region: Region, world: WorldState) -> tuple[str, float]:
    if region.owner is not None and region.owner in world.factions:
        if world.factions[region.owner].capital_region == region.name and _urban_eligible(region):
            return URBAN_CAPITAL, score_capital_candidate(region, world)
    scores = score_region_urban_roles(region, world)
    role, score = max(scores.items(), key=lambda item: (item[1], item[0]))
    if score < URBAN_ROLE_THRESHOLD:
        return URBAN_NONE, 0.0
    return role, score


def get_region_urban_network_value(region: Region) -> float:
    if region.urban_specialization == URBAN_NONE:
        return 0.0
    network_value = (
        0.24
        + _settlement_factor(region) * 0.5
        + float(region.urban_specialization_score or 0.0) * 0.22
        + float(region.market_level or 0.0) * 0.1
        + float(region.road_level or 0.0) * 0.08
        + float(region.storehouse_level or 0.0) * 0.06
        + min(0.5, float(region.trade_value_bonus or 0.0) * 0.05)
        + float(region.administrative_support or 0.0) * 0.08
    )
    network_value -= min(0.55, float(region.unrest or 0.0) * 0.045)
    return round(_clamp(network_value, 0.0, 3.5), 3)


def build_empty_urban_specialization_counts() -> dict[str, int]:
    return {role: 0 for role in ALL_URBAN_SPECIALIZATIONS}


def get_region_urban_effects(region: Region) -> dict[str, float]:
    base_effects = URBAN_BASE_EFFECTS.get(region.urban_specialization or URBAN_NONE, {})
    network_scale = _clamp(0.65 + (float(region.urban_network_value or 0.0) * 0.2), 0.5, 1.45)
    return {
        effect_name: round(effect_value * network_scale, 4)
        for effect_name, effect_value in base_effects.items()
    }


def get_faction_urban_capacity_bonus(world: WorldState, faction_name: str) -> float:
    faction = world.factions[faction_name]
    urban_value = max(0.0, float(faction.urban_network_value or 0.0))
    capital_bonus = 0.0
    if faction.capital_region in world.regions:
        capital_bonus = get_region_urban_effects(world.regions[faction.capital_region]).get(
            "administrative_capacity_bonus",
            0.0,
        )
    return round(min(0.42, urban_value * 0.035 + capital_bonus), 4)


def update_urban_specializations(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        faction.capital_region = choose_faction_capital(world, faction_name)
        faction.urban_network_value = 0.0
        faction.urban_specialization_counts = build_empty_urban_specialization_counts()

    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            region.urban_specialization = URBAN_NONE
            region.urban_specialization_score = 0.0
            region.urban_network_value = 0.0
            continue
        role, score = choose_region_urban_specialization(region, world)
        region.urban_specialization = role
        region.urban_specialization_score = round(score, 3)
        region.urban_network_value = get_region_urban_network_value(region)
        faction = world.factions[region.owner]
        faction.urban_specialization_counts.setdefault(role, 0)
        faction.urban_specialization_counts[role] += 1
        faction.urban_network_value = round(
            faction.urban_network_value + region.urban_network_value,
            3,
        )
