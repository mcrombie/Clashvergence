from __future__ import annotations

from collections.abc import Mapping


RESOURCE_GRAIN = "grain"
RESOURCE_HORSES = "horses"
RESOURCE_WILD_FOOD = "wild_food"
RESOURCE_TIMBER = "timber"
RESOURCE_COPPER = "copper"
RESOURCE_STONE = "stone"

DOMESTICABLE_RESOURCES = (
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
)
WILD_RESOURCES = (
    RESOURCE_WILD_FOOD,
    RESOURCE_TIMBER,
)
EXTRACTIVE_RESOURCES = (
    RESOURCE_COPPER,
    RESOURCE_STONE,
)
ALL_RESOURCES = (
    *DOMESTICABLE_RESOURCES,
    *WILD_RESOURCES,
    *EXTRACTIVE_RESOURCES,
)

CAPACITY_FOOD_SECURITY = "food_security"
CAPACITY_MOBILITY = "mobility_capacity"
CAPACITY_CONSTRUCTION = "construction_capacity"
CAPACITY_METAL = "metal_capacity"
CAPACITY_TAXABLE_VALUE = "taxable_value"
ALL_CAPACITIES = (
    CAPACITY_FOOD_SECURITY,
    CAPACITY_MOBILITY,
    CAPACITY_CONSTRUCTION,
    CAPACITY_METAL,
    CAPACITY_TAXABLE_VALUE,
)

RESOURCE_LABELS = {
    RESOURCE_GRAIN: "Grain",
    RESOURCE_HORSES: "Horses",
    RESOURCE_WILD_FOOD: "Wild Food",
    RESOURCE_TIMBER: "Timber",
    RESOURCE_COPPER: "Copper",
    RESOURCE_STONE: "Stone",
}

RESOURCE_VALUE_WEIGHTS = {
    RESOURCE_GRAIN: 1.25,
    RESOURCE_HORSES: 0.95,
    RESOURCE_WILD_FOOD: 1.05,
    RESOURCE_TIMBER: 0.8,
    RESOURCE_COPPER: 1.35,
    RESOURCE_STONE: 0.75,
}

TERRAIN_RESOURCE_PROFILES = {
    "plains": {
        RESOURCE_GRAIN: 0.9,
        RESOURCE_HORSES: 0.65,
        RESOURCE_WILD_FOOD: 0.25,
        RESOURCE_TIMBER: 0.1,
        RESOURCE_STONE: 0.1,
    },
    "riverland": {
        RESOURCE_GRAIN: 1.0,
        RESOURCE_HORSES: 0.2,
        RESOURCE_WILD_FOOD: 0.85,
        RESOURCE_TIMBER: 0.15,
        RESOURCE_STONE: 0.1,
    },
    "coast": {
        RESOURCE_GRAIN: 0.45,
        RESOURCE_HORSES: 0.2,
        RESOURCE_WILD_FOOD: 0.95,
        RESOURCE_TIMBER: 0.2,
        RESOURCE_STONE: 0.05,
    },
    "forest": {
        RESOURCE_GRAIN: 0.4,
        RESOURCE_HORSES: 0.25,
        RESOURCE_WILD_FOOD: 0.8,
        RESOURCE_TIMBER: 1.0,
        RESOURCE_STONE: 0.2,
    },
    "hills": {
        RESOURCE_GRAIN: 0.22,
        RESOURCE_HORSES: 0.45,
        RESOURCE_WILD_FOOD: 0.45,
        RESOURCE_TIMBER: 0.25,
        RESOURCE_COPPER: 0.8,
        RESOURCE_STONE: 0.9,
    },
    "highland": {
        RESOURCE_GRAIN: 0.1,
        RESOURCE_HORSES: 0.15,
        RESOURCE_WILD_FOOD: 0.35,
        RESOURCE_TIMBER: 0.2,
        RESOURCE_COPPER: 1.0,
        RESOURCE_STONE: 1.0,
    },
    "marsh": {
        RESOURCE_GRAIN: 0.18,
        RESOURCE_HORSES: 0.05,
        RESOURCE_WILD_FOOD: 0.78,
        RESOURCE_TIMBER: 0.18,
    },
    "steppe": {
        RESOURCE_GRAIN: 0.55,
        RESOURCE_HORSES: 0.95,
        RESOURCE_WILD_FOOD: 0.22,
        RESOURCE_TIMBER: 0.05,
        RESOURCE_STONE: 0.08,
    },
}

CLIMATE_RESOURCE_MODIFIERS = {
    "temperate": {
        RESOURCE_GRAIN: 0.05,
        RESOURCE_WILD_FOOD: 0.05,
        RESOURCE_TIMBER: 0.05,
    },
    "oceanic": {
        RESOURCE_GRAIN: 0.08,
        RESOURCE_WILD_FOOD: 0.15,
        RESOURCE_TIMBER: 0.08,
    },
    "cold": {
        RESOURCE_GRAIN: -0.12,
        RESOURCE_HORSES: -0.08,
        RESOURCE_WILD_FOOD: 0.04,
        RESOURCE_TIMBER: 0.05,
        RESOURCE_STONE: 0.04,
    },
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def build_empty_resource_map() -> dict[str, float]:
    return {resource_name: 0.0 for resource_name in ALL_RESOURCES}


def build_empty_capacity_map() -> dict[str, float]:
    return {capacity_name: 0.0 for capacity_name in ALL_CAPACITIES}


def normalize_resource_map(resource_map: Mapping[str, float] | None) -> dict[str, float]:
    normalized = build_empty_resource_map()
    if resource_map is None:
        return normalized
    for resource_name in ALL_RESOURCES:
        normalized[resource_name] = round(float(resource_map.get(resource_name, 0.0)), 3)
    return normalized


def normalize_capacity_map(capacity_map: Mapping[str, float] | None) -> dict[str, float]:
    normalized = build_empty_capacity_map()
    if capacity_map is None:
        return normalized
    for capacity_name in ALL_CAPACITIES:
        normalized[capacity_name] = round(float(capacity_map.get(capacity_name, 0.0)), 3)
    return normalized


def get_resource_label(resource_name: str) -> str:
    return RESOURCE_LABELS.get(resource_name, resource_name.replace("_", " ").title())


def format_resource_map(resource_map: Mapping[str, float] | None, *, limit: int = 3) -> str:
    if not resource_map:
        return "None"
    ranked = [
        (resource_name, amount)
        for resource_name, amount in resource_map.items()
        if amount > 0
    ]
    if not ranked:
        return "None"
    ranked.sort(key=lambda item: (-item[1], get_resource_label(item[0])))
    return ", ".join(
        f"{get_resource_label(resource_name)} {amount:.1f}"
        for resource_name, amount in ranked[:limit]
    )


def get_region_resource_summary(
    *,
    fixed_endowments: Mapping[str, float] | None = None,
    wild_endowments: Mapping[str, float] | None = None,
    established: Mapping[str, float] | None = None,
    output: Mapping[str, float] | None = None,
) -> dict[str, str]:
    fixed_text = format_resource_map(fixed_endowments, limit=2)
    wild_text = format_resource_map(wild_endowments, limit=2)
    established_text = format_resource_map(established, limit=2)
    output_text = format_resource_map(output, limit=3)
    parts = []
    if fixed_text != "None":
        parts.append(f"Fixed: {fixed_text}")
    if wild_text != "None":
        parts.append(f"Wild: {wild_text}")
    if established_text != "None":
        parts.append(f"Established: {established_text}")
    return {
        "resource_profile": " | ".join(parts) if parts else "No notable resources",
        "resource_output": output_text,
    }


def _get_terrain_resource_values(terrain_tags: list[str]) -> dict[str, float]:
    totals = build_empty_resource_map()
    if not terrain_tags:
        terrain_tags = ["plains"]
    for terrain_tag in terrain_tags:
        profile = TERRAIN_RESOURCE_PROFILES.get(terrain_tag, {})
        for resource_name, amount in profile.items():
            if resource_name in DOMESTICABLE_RESOURCES:
                totals[resource_name] = max(totals[resource_name], amount)
            else:
                totals[resource_name] += amount
    return totals


def _apply_climate_modifiers(resource_values: dict[str, float], climate: str) -> dict[str, float]:
    adjusted = resource_values.copy()
    for resource_name, modifier in CLIMATE_RESOURCE_MODIFIERS.get(climate, {}).items():
        adjusted[resource_name] = adjusted.get(resource_name, 0.0) + modifier
    return adjusted


def seed_region_resource_profile(region) -> None:
    terrain_values = _get_terrain_resource_values(list(region.terrain_tags))
    climate_values = _apply_climate_modifiers(terrain_values, region.climate)

    fixed_endowments = build_empty_resource_map()
    wild_endowments = build_empty_resource_map()
    suitability = build_empty_resource_map()

    for resource_name in DOMESTICABLE_RESOURCES:
        suitability[resource_name] = round(
            _clamp(climate_values.get(resource_name, 0.0), 0.0, 1.0),
            3,
        )

    for resource_name in WILD_RESOURCES:
        wild_endowments[resource_name] = round(
            _clamp(climate_values.get(resource_name, 0.0), 0.0, 2.5),
            3,
        )

    for resource_name in EXTRACTIVE_RESOURCES:
        fixed_endowments[resource_name] = round(
            _clamp(climate_values.get(resource_name, 0.0), 0.0, 2.0),
            3,
        )

    established = build_empty_resource_map()
    if region.owner is not None:
        grain_suitability = suitability[RESOURCE_GRAIN]
        if grain_suitability >= 0.35:
            established[RESOURCE_GRAIN] = round(
                _clamp(max(0.45, grain_suitability * 0.75), 0.0, 1.0),
                3,
            )
        horse_suitability = suitability[RESOURCE_HORSES]
        if horse_suitability >= 0.55:
            established[RESOURCE_HORSES] = round(
                _clamp(max(0.22, horse_suitability * 0.45), 0.0, 0.8),
                3,
            )

    region.resource_fixed_endowments = fixed_endowments
    region.resource_wild_endowments = wild_endowments
    region.resource_suitability = suitability
    region.resource_established = established
    region.resource_output = build_empty_resource_map()


def get_legacy_region_resource_value(
    output: Mapping[str, float] | None,
    *,
    fixed_endowments: Mapping[str, float] | None = None,
    wild_endowments: Mapping[str, float] | None = None,
    suitability: Mapping[str, float] | None = None,
    established: Mapping[str, float] | None = None,
) -> int:
    total_value = 0.0
    for resource_name, amount in (output or {}).items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0)

    for resource_name, amount in (fixed_endowments or {}).items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.55

    for resource_name, amount in (wild_endowments or {}).items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.3

    for resource_name, amount in (suitability or {}).items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.45

    for resource_name, amount in (established or {}).items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.5

    if total_value <= 0:
        return 0
    return max(1, int(round(total_value / 1.8)))
