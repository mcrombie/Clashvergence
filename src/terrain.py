from __future__ import annotations

from src.models import Region


TERRAIN_RULES = {
    "plains": {
        "label": "Plains",
        "label_component": "Plains",
        "expansion_modifier": 1,
        "defense_modifier": 0,
        "economic_modifier": 0,
        "name_cues": ["Field", "Plain", "Reach"],
    },
    "forest": {
        "label": "Forest",
        "label_component": "Forest",
        "expansion_modifier": -1,
        "defense_modifier": 1,
        "economic_modifier": 0,
        "name_cues": ["Grove", "Hollow", "Wood"],
    },
    "hills": {
        "label": "Hills",
        "label_component": "Hill",
        "expansion_modifier": -1,
        "defense_modifier": 1,
        "economic_modifier": 0,
        "name_cues": ["Down", "Hill", "Rise"],
    },
    "highland": {
        "label": "Highland",
        "label_component": "Highland",
        "expansion_modifier": -2,
        "defense_modifier": 2,
        "economic_modifier": 0,
        "name_cues": ["Crown", "Height", "Ridge"],
    },
    "riverland": {
        "label": "Riverland",
        "label_component": "Riverland",
        "expansion_modifier": 1,
        "defense_modifier": 0,
        "economic_modifier": 1,
        "name_cues": ["Banks", "Ford", "Wash"],
    },
    "coast": {
        "label": "Coast",
        "label_component": "Coastal",
        "expansion_modifier": 0,
        "defense_modifier": 0,
        "economic_modifier": 1,
        "name_cues": ["Bay", "Cape", "Reach"],
    },
    "marsh": {
        "label": "Marsh",
        "label_component": "Marsh",
        "expansion_modifier": -2,
        "defense_modifier": 1,
        "economic_modifier": -1,
        "name_cues": ["Bog", "Fen", "Mire"],
    },
    "steppe": {
        "label": "Steppe",
        "label_component": "Steppe",
        "expansion_modifier": 1,
        "defense_modifier": 0,
        "economic_modifier": 0,
        "name_cues": ["Grass", "Plain", "Steppe"],
    },
}

TERRAIN_DISPLAY_ORDER = [
    "coast",
    "riverland",
    "highland",
    "hills",
    "marsh",
    "forest",
    "steppe",
    "plains",
]


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def normalize_terrain_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return ["plains"]

    normalized: list[str] = []
    for tag in tags:
        if tag not in TERRAIN_RULES:
            raise ValueError(f"Unsupported terrain tag: {tag}")
        if tag not in normalized:
            normalized.append(tag)

    return sorted(
        normalized,
        key=lambda tag: (
            TERRAIN_DISPLAY_ORDER.index(tag)
            if tag in TERRAIN_DISPLAY_ORDER
            else len(TERRAIN_DISPLAY_ORDER),
            tag,
        ),
    )


def format_terrain_label(tags: list[str] | None) -> str:
    normalized = normalize_terrain_tags(tags)
    if len(normalized) == 1:
        return TERRAIN_RULES[normalized[0]]["label"]
    return " ".join(TERRAIN_RULES[tag]["label_component"] for tag in normalized)


def get_terrain_profile(tags_or_region: Region | list[str] | None) -> dict:
    if isinstance(tags_or_region, Region):
        normalized = normalize_terrain_tags(tags_or_region.terrain_tags)
    else:
        normalized = normalize_terrain_tags(tags_or_region)

    expansion_modifier = 0
    defense_modifier = 0
    economic_modifier = 0
    name_cues: list[str] = []

    for tag in normalized:
        rules = TERRAIN_RULES[tag]
        expansion_modifier += rules["expansion_modifier"]
        defense_modifier += rules["defense_modifier"]
        economic_modifier += rules["economic_modifier"]
        for cue in rules["name_cues"]:
            if cue not in name_cues:
                name_cues.append(cue)

    return {
        "terrain_tags": normalized,
        "terrain_label": format_terrain_label(normalized),
        "expansion_modifier": _clamp(expansion_modifier, -3, 3),
        "defense_modifier": _clamp(defense_modifier, 0, 4),
        "economic_modifier": _clamp(economic_modifier, -2, 2),
        "name_cues": name_cues,
    }

