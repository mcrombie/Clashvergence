from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from src.models import Event, Faction, Region, WorldState
from src.region_state import get_region_core_status
from src.resources import (
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_LIVESTOCK,
    RESOURCE_SALT,
    RESOURCE_TEXTILES,
    RESOURCE_TIMBER,
)


TECH_IRRIGATION_METHODS = "irrigation_methods"
TECH_PASTORAL_BREEDING = "pastoral_breeding"
TECH_COPPER_WORKING = "copper_working"
TECH_ROAD_ADMINISTRATION = "road_administration"
TECH_MARKET_ACCOUNTING = "market_accounting"
TECH_ORGANIZED_LEVIES = "organized_levies"
TECH_TEMPLE_RECORDKEEPING = "temple_recordkeeping"


@dataclass(frozen=True)
class TechnologyDefinition:
    key: str
    label: str
    category: str
    description: str


TECHNOLOGY_DEFINITIONS = {
    TECH_IRRIGATION_METHODS: TechnologyDefinition(
        key=TECH_IRRIGATION_METHODS,
        label="Irrigation Methods",
        category="agriculture",
        description="Water management, canal upkeep, and field scheduling.",
    ),
    TECH_PASTORAL_BREEDING: TechnologyDefinition(
        key=TECH_PASTORAL_BREEDING,
        label="Pastoral Breeding",
        category="agriculture",
        description="Herd selection, foddering, and managed breeding stock.",
    ),
    TECH_COPPER_WORKING: TechnologyDefinition(
        key=TECH_COPPER_WORKING,
        label="Copper Working",
        category="metallurgy",
        description="Ore selection, smelting practice, and tool production.",
    ),
    TECH_ROAD_ADMINISTRATION: TechnologyDefinition(
        key=TECH_ROAD_ADMINISTRATION,
        label="Road Administration",
        category="logistics",
        description="Route maintenance, way stations, and corridor standards.",
    ),
    TECH_MARKET_ACCOUNTING: TechnologyDefinition(
        key=TECH_MARKET_ACCOUNTING,
        label="Market Accounting",
        category="commerce",
        description="Weights, ledgers, storage claims, and exchange routines.",
    ),
    TECH_ORGANIZED_LEVIES: TechnologyDefinition(
        key=TECH_ORGANIZED_LEVIES,
        label="Organized Levies",
        category="military",
        description="Muster rolls, drill habits, and supply obligations.",
    ),
    TECH_TEMPLE_RECORDKEEPING: TechnologyDefinition(
        key=TECH_TEMPLE_RECORDKEEPING,
        label="Temple Recordkeeping",
        category="institutions",
        description="Sacred archives, tribute lists, and ritual calendars.",
    ),
}

ALL_TECHNOLOGIES = tuple(TECHNOLOGY_DEFINITIONS)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def build_empty_technology_map() -> dict[str, float]:
    return {technology_key: 0.0 for technology_key in ALL_TECHNOLOGIES}


def normalize_technology_map(technology_map: dict[str, float] | None) -> dict[str, float]:
    normalized = build_empty_technology_map()
    if technology_map is None:
        return normalized
    for technology_key in ALL_TECHNOLOGIES:
        normalized[technology_key] = round(
            _clamp(float(technology_map.get(technology_key, 0.0)), 0.0, 1.0),
            3,
        )
    return normalized


def ensure_region_technology_state(region: Region) -> None:
    region.technology_presence = normalize_technology_map(region.technology_presence)
    region.technology_adoption = normalize_technology_map(region.technology_adoption)
    region.technology_pressure = normalize_technology_map(region.technology_pressure)


def ensure_faction_technology_state(faction: Faction) -> None:
    faction.known_technologies = normalize_technology_map(faction.known_technologies)
    faction.institutional_technologies = normalize_technology_map(
        faction.institutional_technologies
    )


def get_technology_label(technology_key: str) -> str:
    definition = TECHNOLOGY_DEFINITIONS.get(technology_key)
    if definition is not None:
        return definition.label
    return technology_key.replace("_", " ").title()


def get_region_technology_adoption(region: Region, technology_key: str) -> float:
    return float((region.technology_adoption or {}).get(technology_key, 0.0))


def get_region_technology_presence(region: Region, technology_key: str) -> float:
    return float((region.technology_presence or {}).get(technology_key, 0.0))


def get_faction_institutional_technology(
    faction: Faction | None,
    technology_key: str,
) -> float:
    if faction is None:
        return 0.0
    return float((faction.institutional_technologies or {}).get(technology_key, 0.0))


def get_region_institutional_technology(
    region: Region,
    world: WorldState | None,
    technology_key: str,
) -> float:
    if world is None or region.owner not in world.factions:
        return 0.0
    return get_faction_institutional_technology(world.factions[region.owner], technology_key)


def format_technology_map(
    technology_map: dict[str, float] | None,
    *,
    limit: int = 3,
    threshold: float = 0.05,
) -> str:
    ranked = [
        (technology_key, value)
        for technology_key, value in (technology_map or {}).items()
        if value >= threshold
    ]
    ranked.sort(key=lambda item: (-item[1], get_technology_label(item[0])))
    if not ranked:
        return "None"
    return ", ".join(
        f"{get_technology_label(technology_key)} {value:.2f}"
        for technology_key, value in ranked[:limit]
    )


def _settlement_factor(region: Region) -> float:
    return {
        "wild": 0.18,
        "rural": 0.42,
        "town": 0.72,
        "city": 1.0,
    }.get(region.settlement_level, 0.35)


def _stability_factor(region: Region) -> float:
    factor = 1.0
    factor -= min(0.45, float(region.unrest or 0.0) * 0.045)
    if region.unrest_event_level == "disturbance":
        factor -= 0.12
    elif region.unrest_event_level == "crisis":
        factor -= 0.28
    food_consumption = max(0.2, float(region.food_consumption or 0.0))
    factor -= min(0.22, float(region.food_deficit or 0.0) / food_consumption * 0.22)
    return _clamp(factor, 0.18, 1.08)


def _institutional_factor(region: Region, world: WorldState | None) -> float:
    if world is None or region.owner not in world.factions:
        return 0.32
    faction = world.factions[region.owner]
    factor = 0.45
    factor += max(0.0, float(faction.administrative_efficiency or 1.0) - 0.55) * 0.42
    factor += max(0.0, float(faction.administrative_reach or 1.0) - 0.55) * 0.24
    factor += max(0.0, float(region.administrative_support or 0.0)) * 0.12
    if faction.polity_tier == "state":
        factor += 0.12
    elif faction.polity_tier == "chiefdom":
        factor += 0.06
    if get_region_core_status(region) == "homeland":
        factor += 0.08
    elif get_region_core_status(region) == "core":
        factor += 0.04
    return _clamp(factor, 0.22, 1.18)


def _resource_readiness(region: Region, technology_key: str) -> float:
    if technology_key == TECH_IRRIGATION_METHODS:
        water_bonus = 0.28 if any(tag in region.terrain_tags for tag in ("riverland", "marsh", "coast")) else 0.0
        return _clamp(
            region.resource_suitability.get(RESOURCE_GRAIN, 0.0) * 0.58
            + region.resource_established.get(RESOURCE_GRAIN, 0.0) * 0.28
            + region.irrigation_level * 0.12
            + water_bonus,
            0.0,
            1.0,
        )
    if technology_key == TECH_PASTORAL_BREEDING:
        return _clamp(
            region.resource_suitability.get(RESOURCE_LIVESTOCK, 0.0) * 0.42
            + region.resource_suitability.get(RESOURCE_HORSES, 0.0) * 0.34
            + region.resource_established.get(RESOURCE_LIVESTOCK, 0.0) * 0.2
            + region.resource_established.get(RESOURCE_HORSES, 0.0) * 0.18
            + region.pasture_level * 0.1,
            0.0,
            1.0,
        )
    if technology_key == TECH_COPPER_WORKING:
        return _clamp(
            region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0) * 0.72
            + region.resource_effective_output.get(RESOURCE_COPPER, 0.0) * 0.18
            + region.copper_mine_level * 0.14
            + region.extractive_level * 0.08,
            0.0,
            1.0,
        )
    if technology_key == TECH_ROAD_ADMINISTRATION:
        return _clamp(
            region.road_level * 0.32
            + region.infrastructure_level * 0.28
            + _settlement_factor(region) * 0.24
            + max(0.0, 1.0 - float(region.resource_isolation_factor or 0.0)) * 0.16,
            0.0,
            1.0,
        )
    if technology_key == TECH_MARKET_ACCOUNTING:
        return _clamp(
            region.market_level * 0.34
            + region.storehouse_level * 0.14
            + region.trade_throughput * 0.018
            + region.trade_foreign_flow * 0.045
            + region.resource_suitability.get(RESOURCE_TEXTILES, 0.0) * 0.12
            + region.resource_fixed_endowments.get(RESOURCE_SALT, 0.0) * 0.12
            + _settlement_factor(region) * 0.18,
            0.0,
            1.0,
        )
    if technology_key == TECH_ORGANIZED_LEVIES:
        return _clamp(
            min(1.0, region.population / 360.0) * 0.32
            + region.resource_effective_output.get(RESOURCE_COPPER, 0.0) * 0.08
            + region.resource_effective_output.get(RESOURCE_HORSES, 0.0) * 0.08
            + _settlement_factor(region) * 0.18
            + (0.16 if get_region_core_status(region) in {"homeland", "core"} else 0.04),
            0.0,
            1.0,
        )
    if technology_key == TECH_TEMPLE_RECORDKEEPING:
        return _clamp(
            region.shrine_level * 0.34
            + region.pilgrimage_value * 0.16
            + _settlement_factor(region) * 0.22
            + (0.18 if region.sacred_religion else 0.0)
            + region.market_level * 0.08,
            0.0,
            1.0,
        )
    return 0.0


def _intrinsic_seed(region: Region, technology_key: str) -> float:
    readiness = _resource_readiness(region, technology_key)
    if technology_key == TECH_IRRIGATION_METHODS and "riverland" in region.terrain_tags:
        readiness += 0.12
    if technology_key == TECH_PASTORAL_BREEDING and "steppe" in region.terrain_tags:
        readiness += 0.12
    if technology_key == TECH_COPPER_WORKING and region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0) > 0.35:
        readiness += 0.1
    if technology_key == TECH_MARKET_ACCOUNTING and region.trade_gateway_role != "none":
        readiness += 0.08
    return _clamp(readiness * 0.34, 0.0, 0.38)


def _owned_regions(world: WorldState, faction_name: str) -> list[Region]:
    return [region for region in world.regions.values() if region.owner == faction_name]


def _weighted_average(values: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _value, weight in values)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in values) / total_weight


def _region_institutional_weight(region: Region) -> float:
    weight = 0.35 + _settlement_factor(region)
    if get_region_core_status(region) == "homeland":
        weight += 0.5
    elif get_region_core_status(region) == "core":
        weight += 0.25
    weight += min(0.28, region.administrative_support * 0.18)
    weight -= min(0.3, region.administrative_autonomy * 0.12)
    return max(0.1, weight)


def _refresh_faction_technology_state(world: WorldState, *, emit_events: bool) -> None:
    for faction_name, faction in world.factions.items():
        ensure_faction_technology_state(faction)
        regions = _owned_regions(world, faction_name)
        previous_institutional = dict(faction.institutional_technologies)
        if not regions:
            faction.known_technologies = build_empty_technology_map()
            faction.institutional_technologies = build_empty_technology_map()
            continue

        known = build_empty_technology_map()
        institutional = build_empty_technology_map()
        institution_multiplier = _clamp(
            0.55
            + max(0.0, float(faction.administrative_efficiency or 1.0) - 0.55) * 0.36
            + max(0.0, float(faction.administrative_reach or 1.0) - 0.55) * 0.24
            + (0.1 if faction.polity_tier == "state" else 0.05 if faction.polity_tier == "chiefdom" else 0.0),
            0.35,
            1.15,
        )
        for technology_key in ALL_TECHNOLOGIES:
            known[technology_key] = round(
                max(
                    mean(region.technology_presence.get(technology_key, 0.0) for region in regions),
                    mean(region.technology_adoption.get(technology_key, 0.0) for region in regions),
                ),
                3,
            )
            target = _weighted_average(
                [
                    (
                        region.technology_adoption.get(technology_key, 0.0),
                        _region_institutional_weight(region),
                    )
                    for region in regions
                ]
            )
            current = faction.institutional_technologies.get(technology_key, 0.0)
            next_value = current + ((target * institution_multiplier) - current) * 0.18
            institutional[technology_key] = round(_clamp(next_value, 0.0, 1.0), 3)

            if (
                emit_events
                and previous_institutional.get(technology_key, 0.0) < 0.45
                and institutional[technology_key] >= 0.45
            ):
                world.events.append(Event(
                    turn=world.turn,
                    type="technology_institutionalized",
                    faction=faction_name,
                    details={
                        "technology": technology_key,
                        "technology_label": get_technology_label(technology_key),
                        "institutional_level": institutional[technology_key],
                    },
                    tags=["technology", "institutionalization", technology_key],
                    significance=institutional[technology_key],
                ))

        faction.known_technologies = normalize_technology_map(known)
        faction.institutional_technologies = normalize_technology_map(institutional)


def initialize_technology_state(world: WorldState) -> None:
    for region in world.regions.values():
        ensure_region_technology_state(region)
        for technology_key in ALL_TECHNOLOGIES:
            seed = _intrinsic_seed(region, technology_key)
            if region.owner is not None:
                seed += 0.04 * _settlement_factor(region)
            region.technology_presence[technology_key] = round(_clamp(seed, 0.0, 0.5), 3)
            region.technology_adoption[technology_key] = round(
                _clamp(seed * _resource_readiness(region, technology_key), 0.0, 0.42),
                3,
            )
            region.technology_pressure[technology_key] = 0.0
    _refresh_faction_technology_state(world, emit_events=False)


def _adjacent_technology_pressure(
    world: WorldState,
    region: Region,
    technology_key: str,
) -> float:
    values = []
    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        values.append(neighbor.technology_adoption.get(technology_key, 0.0) * 0.018)
        values.append(neighbor.technology_presence.get(technology_key, 0.0) * 0.008)
    return sum(values)


def _trade_technology_pressure(
    world: WorldState,
    region: Region,
    technology_key: str,
) -> float:
    pressure = 0.0
    pressure += min(0.035, float(region.trade_throughput or 0.0) * 0.0018)
    pressure += min(0.04, float(region.trade_foreign_flow or 0.0) * 0.012)
    pressure += min(0.025, float(region.trade_import_value or 0.0) * 0.004)
    if region.trade_gateway_role != "none":
        pressure += 0.008
    if region.trade_foreign_partner_region in world.regions:
        partner = world.regions[region.trade_foreign_partner_region]
        pressure += partner.technology_adoption.get(technology_key, 0.0) * 0.04
    if region.trade_route_parent in world.regions:
        parent = world.regions[region.trade_route_parent]
        pressure += parent.technology_adoption.get(technology_key, 0.0) * 0.012
    return pressure


def _institutional_technology_pressure(
    world: WorldState,
    region: Region,
    technology_key: str,
) -> float:
    if region.owner not in world.factions:
        return 0.0
    faction = world.factions[region.owner]
    institutional = faction.institutional_technologies.get(technology_key, 0.0)
    known = faction.known_technologies.get(technology_key, 0.0)
    return institutional * 0.035 + known * 0.012


def update_technology_diffusion(world: WorldState) -> None:
    from src.urban import get_region_urban_effects

    for region in world.regions.values():
        ensure_region_technology_state(region)
    for faction in world.factions.values():
        ensure_faction_technology_state(faction)

    previous_adoption = {
        region.name: dict(region.technology_adoption)
        for region in world.regions.values()
    }
    next_presence = {}
    next_adoption = {}
    next_pressure = {}

    for region in world.regions.values():
        region_presence = build_empty_technology_map()
        region_adoption = build_empty_technology_map()
        region_pressure = build_empty_technology_map()
        stability = _stability_factor(region)
        institutional_factor = _institutional_factor(region, world)
        density_factor = _settlement_factor(region)

        for technology_key in ALL_TECHNOLOGIES:
            readiness = _resource_readiness(region, technology_key)
            pressure = (
                _intrinsic_seed(region, technology_key) * 0.035
                + _adjacent_technology_pressure(world, region, technology_key)
                + _trade_technology_pressure(world, region, technology_key)
                + _institutional_technology_pressure(world, region, technology_key)
                + density_factor * 0.006
                + get_region_urban_effects(region).get("technology_pressure_bonus", 0.0)
            )
            pressure *= _clamp(0.65 + stability * 0.45, 0.25, 1.1)
            current_presence = region.technology_presence.get(technology_key, 0.0)
            presence = current_presence + pressure * (1.0 - current_presence)

            current_adoption = region.technology_adoption.get(technology_key, 0.0)
            adoption_target = min(presence, readiness) * institutional_factor * _clamp(0.65 + density_factor, 0.7, 1.45)
            adoption_gain = max(0.0, adoption_target - current_adoption)
            adoption = current_adoption + adoption_gain * 0.16 * stability
            if stability < 0.38 and current_adoption > readiness * 0.7:
                adoption -= min(0.012, (0.38 - stability) * 0.025)

            region_pressure[technology_key] = round(_clamp(pressure, 0.0, 1.0), 3)
            region_presence[technology_key] = round(_clamp(presence, 0.0, 1.0), 3)
            region_adoption[technology_key] = round(_clamp(adoption, 0.0, 1.0), 3)

            if (
                previous_adoption[region.name].get(technology_key, 0.0) < 0.5
                and region_adoption[technology_key] >= 0.5
                and region.owner is not None
            ):
                world.events.append(Event(
                    turn=world.turn,
                    type="technology_adoption",
                    faction=region.owner,
                    region=region.name,
                    details={
                        "technology": technology_key,
                        "technology_label": get_technology_label(technology_key),
                        "adoption": region_adoption[technology_key],
                    },
                    tags=["technology", "adoption", technology_key],
                    significance=region_adoption[technology_key],
                ))

        next_presence[region.name] = region_presence
        next_adoption[region.name] = region_adoption
        next_pressure[region.name] = region_pressure

    for region_name, region in world.regions.items():
        region.technology_presence = next_presence[region_name]
        region.technology_adoption = next_adoption[region_name]
        region.technology_pressure = next_pressure[region_name]

    _refresh_faction_technology_state(world, emit_events=True)


def apply_development_technology_experience(
    region: Region,
    project_type: str,
    resource_focus: str | None = None,
) -> None:
    ensure_region_technology_state(region)
    project_technology_map = {
        "build_irrigation": TECH_IRRIGATION_METHODS,
        "expand_irrigation": TECH_IRRIGATION_METHODS,
        "improve_agriculture": TECH_IRRIGATION_METHODS,
        "introduce_livestock": TECH_PASTORAL_BREEDING,
        "introduce_horses": TECH_PASTORAL_BREEDING,
        "establish_pasture": TECH_PASTORAL_BREEDING,
        "expand_pasture": TECH_PASTORAL_BREEDING,
        "improve_pastoralism": TECH_PASTORAL_BREEDING,
        "build_copper_mine": TECH_COPPER_WORKING,
        "expand_copper_mine": TECH_COPPER_WORKING,
        "improve_extraction": TECH_COPPER_WORKING if resource_focus == RESOURCE_COPPER else None,
        "build_road_station": TECH_ROAD_ADMINISTRATION,
        "improve_road": TECH_ROAD_ADMINISTRATION,
        "improve_infrastructure": TECH_ROAD_ADMINISTRATION,
        "build_market": TECH_MARKET_ACCOUNTING,
        "expand_market": TECH_MARKET_ACCOUNTING,
        "build_storehouse": TECH_MARKET_ACCOUNTING,
        "expand_storehouse": TECH_MARKET_ACCOUNTING,
    }
    technology_key = project_technology_map.get(project_type)
    if technology_key is None:
        return
    readiness = _resource_readiness(region, technology_key)
    region.technology_presence[technology_key] = round(
        _clamp(region.technology_presence.get(technology_key, 0.0) + 0.08, 0.0, 1.0),
        3,
    )
    region.technology_adoption[technology_key] = round(
        _clamp(
            region.technology_adoption.get(technology_key, 0.0) + max(0.025, readiness * 0.06),
            0.0,
            1.0,
        ),
        3,
    )
