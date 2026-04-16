from __future__ import annotations


CLIMATE_RULES = {
    "temperate": {
        "label": "Temperate",
    },
    "oceanic": {
        "label": "Oceanic",
    },
    "cold": {
        "label": "Cold",
    },
    "arid": {
        "label": "Arid",
    },
    "steppe": {
        "label": "Steppe",
    },
    "tropical": {
        "label": "Tropical",
    },
}


def normalize_climate(climate: str | None) -> str:
    normalized = climate or "temperate"
    if normalized not in CLIMATE_RULES:
        raise ValueError(f"Unsupported climate: {normalized}")
    return normalized


def format_climate_label(climate: str | None) -> str:
    normalized = normalize_climate(climate)
    return CLIMATE_RULES[normalized]["label"]
