from __future__ import annotations

import random
from typing import Any


SEASON_NAMES = ("Spring", "Summer", "Autumn", "Winter")
TURNS_PER_YEAR = 1
SEASONAL_TIME_STEP_YEARS = 1.0 / TURNS_PER_YEAR

ANNUAL_CAMPAIGN_MODIFIERS = {
    "Spring": 0.5,
    "Summer": 1.0,
    "Autumn": 0.2,
    "Winter": -0.5,
}

ANNUAL_FOOD_VARIANCE = {
    "Spring": 0.0,
    "Summer": 0.05,
    "Autumn": 0.10,
    "Winter": -0.18,
}

DEFAULT_ANNUAL_SEASON_WEIGHTS = {
    "Spring": 0.30,
    "Summer": 0.30,
    "Autumn": 0.30,
    "Winter": 0.10,
}

CLIMATE_ANNUAL_SEASON_WEIGHTS = {
    "tropical": {"Spring": 0.28, "Summer": 0.34, "Autumn": 0.38, "Winter": 0.0},
    "arid": {"Spring": 0.22, "Summer": 0.42, "Autumn": 0.30, "Winter": 0.06},
    "temperate": {"Spring": 0.34, "Summer": 0.24, "Autumn": 0.34, "Winter": 0.08},
    "continental": {"Spring": 0.22, "Summer": 0.28, "Autumn": 0.22, "Winter": 0.28},
    "polar": {"Spring": 0.10, "Summer": 0.18, "Autumn": 0.12, "Winter": 0.60},
}


def _climate_band(climate: str | None) -> str:
    normalized = (climate or "").strip()
    if not normalized:
        return "temperate"
    first = normalized[0].upper()
    if first == "A":
        return "tropical"
    if first == "B":
        return "arid"
    if first == "C":
        return "temperate"
    if first == "D":
        return "continental"
    if first == "E":
        return "polar"
    legacy = normalized.lower()
    if legacy in {"tropical", "jungle"}:
        return "tropical"
    if legacy in {"arid", "desert", "steppe"}:
        return "arid"
    if legacy in {"cold", "subarctic"}:
        return "continental"
    if legacy in {"polar", "tundra"}:
        return "polar"
    return "temperate"


def _weighted_season_choice(weights: dict[str, float], *, seed: str) -> str:
    rng = random.Random(seed)
    seasons = [season for season in SEASON_NAMES if weights.get(season, 0.0) > 0]
    if not seasons:
        return "Spring"
    season_weights = [weights[season] for season in seasons]
    return rng.choices(seasons, weights=season_weights, k=1)[0]


def get_turn_year(zero_based_turn: int) -> int:
    return max(0, zero_based_turn) // TURNS_PER_YEAR + 1


def get_turn_season_index(zero_based_turn: int) -> int:
    return max(0, zero_based_turn) % len(SEASON_NAMES)


def get_turn_season_name(zero_based_turn: int) -> str:
    return SEASON_NAMES[get_turn_season_index(zero_based_turn)]


def get_annual_dominant_season(
    region: Any | None = None,
    world: Any | None = None,
    *,
    turn: int | None = None,
) -> str:
    climate = getattr(region, "climate", None)
    weights = CLIMATE_ANNUAL_SEASON_WEIGHTS.get(
        _climate_band(climate),
        DEFAULT_ANNUAL_SEASON_WEIGHTS,
    )
    resolved_turn = world.turn if turn is None and world is not None else (turn or 0)
    seed_parts = [
        str(getattr(world, "random_seed", None) or getattr(world, "map_name", "") or "world"),
        str(resolved_turn),
        str(getattr(region, "name", None) or "world"),
        str(climate or ""),
    ]
    return _weighted_season_choice(weights, seed="|".join(seed_parts))


def get_annual_campaign_modifier(dominant_season: str) -> float:
    """Military campaign effectiveness for this year."""
    return ANNUAL_CAMPAIGN_MODIFIERS.get(dominant_season, 0.0)


def get_annual_food_variance(dominant_season: str) -> float:
    """Fractional adjustment to annual food production."""
    return ANNUAL_FOOD_VARIANCE.get(dominant_season, 0.0)


def is_year_end(zero_based_turn: int) -> bool:
    return True


def format_turn_date(zero_based_turn: int) -> str:
    return f"Year {get_turn_year(zero_based_turn)}"


def format_turn_label(zero_based_turn: int) -> str:
    return f"Turn {zero_based_turn + 1} ({format_turn_date(zero_based_turn)})"


def get_snapshot_year(one_based_turn: int) -> int:
    return get_turn_year(max(0, one_based_turn - 1))


def get_snapshot_season_name(one_based_turn: int) -> str:
    return get_turn_season_name(max(0, one_based_turn - 1))


def format_snapshot_date(one_based_turn: int) -> str:
    return format_turn_date(max(0, one_based_turn - 1))


def format_snapshot_label(one_based_turn: int) -> str:
    return format_turn_label(max(0, one_based_turn - 1))


def format_turn_span(turn_count: int) -> str:
    years = max(0, turn_count)
    return f"{years} year" + ("" if years == 1 else "s")
