from __future__ import annotations

from collections.abc import Mapping


RESOURCE_GRAIN = "grain"
RESOURCE_LIVESTOCK = "livestock"
RESOURCE_HORSES = "horses"
RESOURCE_WILD_FOOD = "wild_food"
RESOURCE_TIMBER = "timber"
RESOURCE_COPPER = "copper"
RESOURCE_STONE = "stone"
RESOURCE_SALT = "salt"
RESOURCE_TEXTILES = "textiles"

DOMESTICABLE_RESOURCES = (
    RESOURCE_GRAIN,
    RESOURCE_LIVESTOCK,
    RESOURCE_HORSES,
    RESOURCE_TEXTILES,
)
WILD_RESOURCES = (
    RESOURCE_WILD_FOOD,
    RESOURCE_TIMBER,
)
EXTRACTIVE_RESOURCES = (
    RESOURCE_COPPER,
    RESOURCE_STONE,
    RESOURCE_SALT,
)
FOOD_RESOURCES = (
    RESOURCE_GRAIN,
    RESOURCE_LIVESTOCK,
    RESOURCE_WILD_FOOD,
)
CONSTRUCTION_RESOURCES = (
    RESOURCE_TIMBER,
    RESOURCE_STONE,
)
STRATEGIC_RESOURCES = (
    RESOURCE_HORSES,
    RESOURCE_COPPER,
)
COMMERCIAL_RESOURCES = (
    RESOURCE_SALT,
    RESOURCE_TEXTILES,
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
    RESOURCE_LIVESTOCK: "Livestock",
    RESOURCE_HORSES: "Horses",
    RESOURCE_WILD_FOOD: "Wild Food",
    RESOURCE_TIMBER: "Timber",
    RESOURCE_COPPER: "Copper",
    RESOURCE_STONE: "Stone",
    RESOURCE_SALT: "Salt",
    RESOURCE_TEXTILES: "Textiles",
}

RESOURCE_VALUE_WEIGHTS = {
    RESOURCE_GRAIN: 1.25,
    RESOURCE_LIVESTOCK: 1.1,
    RESOURCE_HORSES: 0.95,
    RESOURCE_WILD_FOOD: 1.05,
    RESOURCE_TIMBER: 0.8,
    RESOURCE_COPPER: 1.35,
    RESOURCE_STONE: 0.75,
    RESOURCE_SALT: 1.15,
    RESOURCE_TEXTILES: 1.2,
}

TERRAIN_RESOURCE_PROFILES = {
    "plains": {
        RESOURCE_GRAIN: 0.9,
        RESOURCE_LIVESTOCK: 0.75,
        RESOURCE_HORSES: 0.65,
        RESOURCE_WILD_FOOD: 0.25,
        RESOURCE_TIMBER: 0.1,
        RESOURCE_STONE: 0.1,
        RESOURCE_TEXTILES: 0.25,
    },
    "riverland": {
        RESOURCE_GRAIN: 1.0,
        RESOURCE_LIVESTOCK: 0.58,
        RESOURCE_HORSES: 0.2,
        RESOURCE_WILD_FOOD: 0.85,
        RESOURCE_TIMBER: 0.15,
        RESOURCE_STONE: 0.1,
        RESOURCE_TEXTILES: 0.45,
    },
    "coast": {
        RESOURCE_GRAIN: 0.45,
        RESOURCE_LIVESTOCK: 0.4,
        RESOURCE_HORSES: 0.2,
        RESOURCE_WILD_FOOD: 0.95,
        RESOURCE_TIMBER: 0.2,
        RESOURCE_STONE: 0.05,
        RESOURCE_SALT: 1.0,
        RESOURCE_TEXTILES: 0.55,
    },
    "forest": {
        RESOURCE_GRAIN: 0.4,
        RESOURCE_LIVESTOCK: 0.35,
        RESOURCE_HORSES: 0.25,
        RESOURCE_WILD_FOOD: 0.8,
        RESOURCE_TIMBER: 1.0,
        RESOURCE_STONE: 0.2,
        RESOURCE_TEXTILES: 0.18,
    },
    "hills": {
        RESOURCE_GRAIN: 0.22,
        RESOURCE_LIVESTOCK: 0.45,
        RESOURCE_HORSES: 0.45,
        RESOURCE_WILD_FOOD: 0.45,
        RESOURCE_TIMBER: 0.25,
        RESOURCE_COPPER: 0.8,
        RESOURCE_STONE: 0.9,
        RESOURCE_SALT: 0.2,
    },
    "highland": {
        RESOURCE_GRAIN: 0.1,
        RESOURCE_LIVESTOCK: 0.22,
        RESOURCE_HORSES: 0.15,
        RESOURCE_WILD_FOOD: 0.35,
        RESOURCE_TIMBER: 0.2,
        RESOURCE_COPPER: 1.0,
        RESOURCE_STONE: 1.0,
        RESOURCE_SALT: 0.35,
    },
    "marsh": {
        RESOURCE_GRAIN: 0.18,
        RESOURCE_LIVESTOCK: 0.22,
        RESOURCE_HORSES: 0.05,
        RESOURCE_WILD_FOOD: 0.78,
        RESOURCE_TIMBER: 0.18,
        RESOURCE_SALT: 0.28,
        RESOURCE_TEXTILES: 0.15,
    },
    "steppe": {
        RESOURCE_GRAIN: 0.55,
        RESOURCE_LIVESTOCK: 0.82,
        RESOURCE_HORSES: 0.95,
        RESOURCE_WILD_FOOD: 0.22,
        RESOURCE_TIMBER: 0.05,
        RESOURCE_STONE: 0.08,
        RESOURCE_SALT: 0.12,
        RESOURCE_TEXTILES: 0.12,
    },
}

CLIMATE_RESOURCE_MODIFIERS = {
    "temperate": {
        RESOURCE_GRAIN: 0.05,
        RESOURCE_LIVESTOCK: 0.04,
        RESOURCE_WILD_FOOD: 0.05,
        RESOURCE_TIMBER: 0.05,
        RESOURCE_TEXTILES: 0.06,
    },
    "oceanic": {
        RESOURCE_GRAIN: 0.08,
        RESOURCE_LIVESTOCK: 0.03,
        RESOURCE_WILD_FOOD: 0.15,
        RESOURCE_TIMBER: 0.08,
        RESOURCE_SALT: 0.05,
        RESOURCE_TEXTILES: 0.08,
    },
    "cold": {
        RESOURCE_GRAIN: -0.12,
        RESOURCE_LIVESTOCK: 0.05,
        RESOURCE_HORSES: -0.08,
        RESOURCE_WILD_FOOD: 0.04,
        RESOURCE_TIMBER: 0.05,
        RESOURCE_STONE: 0.04,
        RESOURCE_SALT: 0.06,
        RESOURCE_TEXTILES: -0.08,
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
        livestock_suitability = suitability[RESOURCE_LIVESTOCK]
        if livestock_suitability >= 0.4:
            established[RESOURCE_LIVESTOCK] = round(
                _clamp(max(0.28, livestock_suitability * 0.55), 0.0, 0.9),
                3,
            )
        horse_suitability = suitability[RESOURCE_HORSES]
        if horse_suitability >= 0.55:
            established[RESOURCE_HORSES] = round(
                _clamp(max(0.22, horse_suitability * 0.45), 0.0, 0.8),
                3,
            )
        textile_suitability = suitability[RESOURCE_TEXTILES]
        if textile_suitability >= 0.22:
            fiber_support = (
                established[RESOURCE_GRAIN] * 0.12
                + established[RESOURCE_LIVESTOCK] * 0.22
            )
            established[RESOURCE_TEXTILES] = round(
                _clamp(
                    max(0.14, textile_suitability * 0.3 + fiber_support),
                    0.0,
                    0.75,
                ),
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
