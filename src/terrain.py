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
SEASONAL_TERRAIN_ATTACK_PROJECTION_MODIFIERS = {
    "riverland": {"Spring": -1, "Autumn": 1},
    "marsh": {"Spring": -2, "Summer": -1, "Winter": 1},
    "highland": {"Winter": -2, "Summer": 1},
    "forest": {"Winter": -1},
    "coast": {"Summer": 1, "Winter": -1},
    "steppe": {"Summer": 1, "Winter": -1},
}
SEASONAL_TERRAIN_DEFENSE_BONUSES = {
    "riverland": {"Spring": 2, "Autumn": -1},
    "marsh": {"Spring": 2, "Summer": 1, "Winter": -1},
    "highland": {"Winter": 2, "Summer": -1},
    "forest": {"Winter": 1},
    "coast": {"Winter": 1},
}
SEASONAL_TERRAIN_UNREST_OFFSETS = {
    "riverland": {"Spring": 0.06, "Autumn": -0.05},
    "highland": {"Winter": 0.12, "Autumn": -0.03},
    "forest": {"Winter": 0.05},
    "coast": {"Summer": -0.03, "Autumn": -0.02},
    "plains": {"Autumn": -0.04},
    "marsh": {"Spring": 0.08, "Summer": 0.03},
}
SEASONAL_TERRAIN_MIGRATION_ATTRACTION_OFFSETS = {
    "riverland": {"Spring": -0.12, "Autumn": 0.18},
    "coast": {"Summer": 0.06, "Autumn": 0.04, "Winter": -0.05},
    "highland": {"Winter": -0.14, "Summer": 0.03},
    "forest": {"Winter": -0.06},
    "marsh": {"Spring": -0.14, "Summer": -0.08},
}
SEASONAL_TERRAIN_MIGRATION_CAPACITY_OFFSETS = {
    "riverland": {"Spring": -0.16, "Autumn": 0.12},
    "coast": {"Summer": 0.05, "Winter": -0.04},
    "highland": {"Winter": -0.16},
    "forest": {"Winter": -0.07},
    "marsh": {"Spring": -0.18, "Summer": -0.10},
}
SEASONAL_TERRAIN_CONTEXT_NOTES = {
    "general": {
        "riverland": {
            "Spring": "Spring flooding is making the riverland slow and muddy.",
            "Autumn": "Post-harvest river traffic is opening the riverland back up.",
        },
        "highland": {
            "Winter": "Winter hardship is biting hard across the highland routes.",
            "Summer": "Summer weather is easing movement across the highlands.",
        },
        "coast": {
            "Summer": "Summer sailing weather is favoring the coast.",
            "Winter": "Winter seas are making the coast less reliable.",
        },
        "marsh": {
            "Spring": "Spring wetness is bogging down the marsh approaches.",
        },
        "forest": {
            "Winter": "Winter cover and cold are making the forests harder to manage.",
        },
        "plains": {
            "Autumn": "The autumn harvest is steadying the plains.",
        },
    },
    "attack": {
        "riverland": {
            "Spring": "Spring flooding and mud are slowing any advance through the riverland.",
            "Autumn": "Autumn waters are more navigable, making the riverland easier to contest.",
        },
        "highland": {
            "Winter": "Winter cold and elevation are hardening the highland defenses.",
            "Summer": "Summer weather is softening the usual highland barrier.",
        },
        "coast": {
            "Winter": "Winter seas are complicating coastal operations.",
            "Summer": "Summer sailing is helping movement along the coast.",
        },
        "marsh": {
            "Spring": "Spring wet ground is turning the marsh into a serious obstacle.",
        },
    },
    "migration": {
        "riverland": {
            "Spring": "Spring flooding is discouraging ordinary movement into the riverland.",
            "Autumn": "Post-harvest traffic is drawing migrants back toward the riverland.",
        },
        "highland": {
            "Winter": "Winter exposure is making the highlands a poor destination for settlers.",
        },
        "coast": {
            "Summer": "Summer trade is making the coast more attractive to movers.",
            "Winter": "Winter seas are dampening coastal movement.",
        },
        "marsh": {
            "Spring": "The marsh is especially difficult to move through in spring.",
        },
    },
    "unrest": {
        "highland": {
            "Winter": "Winter isolation is sharpening strain in the highlands.",
        },
        "riverland": {
            "Spring": "Spring flooding is adding friction in the riverland communities.",
            "Autumn": "The harvest season is calming the riverland somewhat.",
        },
        "plains": {
            "Autumn": "The harvest season is easing pressure across the plains.",
        },
        "coast": {
            "Summer": "Summer traffic is taking a little pressure off the coast.",
        },
        "forest": {
            "Winter": "Winter hardship is putting extra strain on the forests.",
        },
    },
}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _normalize_tags_from_input(tags_or_region: Region | list[str] | None) -> list[str]:
    if isinstance(tags_or_region, Region):
        return normalize_terrain_tags(tags_or_region.terrain_tags)
    return normalize_terrain_tags(tags_or_region)


def _sum_seasonal_offsets(
    mapping: dict[str, dict[str, float]],
    tags_or_region: Region | list[str] | None,
    season_name: str,
) -> float:
    total = 0.0
    for tag in _normalize_tags_from_input(tags_or_region):
        total += mapping.get(tag, {}).get(season_name, 0.0)
    return total


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
    normalized = _normalize_tags_from_input(tags_or_region)

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


def get_seasonal_terrain_attack_projection_modifier(
    tags_or_region: Region | list[str] | None,
    season_name: str,
) -> int:
    return _clamp(
        int(round(_sum_seasonal_offsets(SEASONAL_TERRAIN_ATTACK_PROJECTION_MODIFIERS, tags_or_region, season_name))),
        -3,
        3,
    )


def get_seasonal_terrain_defense_bonus(
    tags_or_region: Region | list[str] | None,
    season_name: str,
) -> int:
    return _clamp(
        int(round(_sum_seasonal_offsets(SEASONAL_TERRAIN_DEFENSE_BONUSES, tags_or_region, season_name))),
        -2,
        3,
    )


def get_seasonal_terrain_unrest_multiplier(
    tags_or_region: Region | list[str] | None,
    season_name: str,
) -> float:
    return max(
        0.8,
        min(1.25, 1.0 + _sum_seasonal_offsets(SEASONAL_TERRAIN_UNREST_OFFSETS, tags_or_region, season_name)),
    )


def get_seasonal_terrain_migration_attraction_multiplier(
    tags_or_region: Region | list[str] | None,
    season_name: str,
) -> float:
    return max(
        0.75,
        min(1.25, 1.0 + _sum_seasonal_offsets(SEASONAL_TERRAIN_MIGRATION_ATTRACTION_OFFSETS, tags_or_region, season_name)),
    )


def get_seasonal_terrain_migration_capacity_multiplier(
    tags_or_region: Region | list[str] | None,
    season_name: str,
) -> float:
    return max(
        0.7,
        min(1.25, 1.0 + _sum_seasonal_offsets(SEASONAL_TERRAIN_MIGRATION_CAPACITY_OFFSETS, tags_or_region, season_name)),
    )


def get_seasonal_terrain_note(
    tags_or_region: Region | list[str] | None,
    season_name: str,
    *,
    context: str = "general",
) -> str:
    context_notes = SEASONAL_TERRAIN_CONTEXT_NOTES.get(context, {})
    notes: list[str] = []
    for tag in _normalize_tags_from_input(tags_or_region):
        note = context_notes.get(tag, {}).get(season_name)
        if note and note not in notes:
            notes.append(note)
    if not notes and context != "general":
        return get_seasonal_terrain_note(tags_or_region, season_name, context="general")
    return " ".join(notes[:2])
