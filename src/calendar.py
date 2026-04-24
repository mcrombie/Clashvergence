SEASON_NAMES = ("Spring", "Summer", "Autumn", "Winter")
TURNS_PER_YEAR = 4
SEASONAL_ECONOMY_SHARE = 1.0 / TURNS_PER_YEAR
SEASONAL_ECONOMY_SHARES = {
    "Spring": 0.22,
    "Summer": 0.24,
    "Autumn": 0.31,
    "Winter": 0.23,
}
SEASONAL_FOOD_PRODUCTION_SHARES = {
    "Spring": 0.22,
    "Summer": 0.31,
    "Autumn": 0.35,
    "Winter": 0.12,
}
SEASONAL_FOOD_CONSUMPTION_SHARES = {
    "Spring": 0.24,
    "Summer": 0.24,
    "Autumn": 0.25,
    "Winter": 0.27,
}
SEASONAL_TIME_STEP_YEARS = 1.0 / TURNS_PER_YEAR
SEASONAL_ACTION_UTILITY_MODIFIERS = {
    "attack": {
        "Spring": 0.06,
        "Summer": 0.10,
        "Autumn": -0.02,
        "Winter": -0.18,
    },
    "expand": {
        "Spring": 0.04,
        "Summer": 0.06,
        "Autumn": -0.01,
        "Winter": -0.10,
    },
    "develop": {
        "Spring": -0.01,
        "Summer": -0.03,
        "Autumn": 0.08,
        "Winter": 0.11,
    },
}
SEASONAL_ATTACK_STRENGTH_BONUSES = {
    "Spring": 1.0,
    "Summer": 2.0,
    "Autumn": -1.0,
    "Winter": -4.0,
}
SEASONAL_ATTACK_SCORE_BONUSES = {
    "Spring": 3,
    "Summer": 5,
    "Autumn": -2,
    "Winter": -10,
}
SEASONAL_UNREST_PRESSURE_MODIFIERS = {
    "Spring": 1.08,
    "Summer": 0.98,
    "Autumn": 0.88,
    "Winter": 1.10,
}
SEASONAL_MIGRATION_PRESSURE_MODIFIERS = {
    "Spring": 1.12,
    "Summer": 1.02,
    "Autumn": 0.92,
    "Winter": 0.78,
}
SEASONAL_MIGRATION_ATTRACTION_MODIFIERS = {
    "Spring": 1.03,
    "Summer": 1.01,
    "Autumn": 1.06,
    "Winter": 0.90,
}
SEASONAL_MIGRATION_CAPACITY_MODIFIERS = {
    "Spring": 1.08,
    "Summer": 1.03,
    "Autumn": 1.00,
    "Winter": 0.82,
}
SEASONAL_MIGRATION_FLOW_MODIFIERS = {
    "Spring": 1.10,
    "Summer": 1.03,
    "Autumn": 0.94,
    "Winter": 0.72,
}
SEASONAL_REFUGEE_FLOW_MODIFIERS = {
    "Spring": 1.02,
    "Summer": 1.00,
    "Autumn": 0.97,
    "Winter": 0.88,
}


def get_turn_year(zero_based_turn: int) -> int:
    return max(0, zero_based_turn) // TURNS_PER_YEAR + 1


def get_turn_season_index(zero_based_turn: int) -> int:
    return max(0, zero_based_turn) % TURNS_PER_YEAR


def get_turn_season_name(zero_based_turn: int) -> str:
    return SEASON_NAMES[get_turn_season_index(zero_based_turn)]


def is_year_end(zero_based_turn: int) -> bool:
    return get_turn_season_index(zero_based_turn) == (TURNS_PER_YEAR - 1)


def format_turn_date(zero_based_turn: int) -> str:
    return f"Year {get_turn_year(zero_based_turn)}, {get_turn_season_name(zero_based_turn)}"


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
    if turn_count <= 0:
        return "0 seasons"
    years, seasons = divmod(turn_count, TURNS_PER_YEAR)
    parts: list[str] = []
    if years:
        parts.append(f"{years} year" + ("" if years == 1 else "s"))
    if seasons:
        parts.append(f"{seasons} season" + ("" if seasons == 1 else "s"))
    return " and ".join(parts) if parts else "0 seasons"


def get_seasonal_economy_share(season_name: str) -> float:
    return SEASONAL_ECONOMY_SHARES.get(season_name, SEASONAL_ECONOMY_SHARE)


def get_seasonal_action_modifier(action_name: str, season_name: str) -> float:
    return SEASONAL_ACTION_UTILITY_MODIFIERS.get(action_name, {}).get(season_name, 0.0)


def get_seasonal_attack_strength_bonus(season_name: str) -> float:
    return SEASONAL_ATTACK_STRENGTH_BONUSES.get(season_name, 0.0)


def get_seasonal_attack_score_bonus(season_name: str) -> int:
    return SEASONAL_ATTACK_SCORE_BONUSES.get(season_name, 0)


def get_seasonal_unrest_pressure_modifier(season_name: str) -> float:
    return SEASONAL_UNREST_PRESSURE_MODIFIERS.get(season_name, 1.0)


def get_seasonal_migration_pressure_modifier(season_name: str) -> float:
    return SEASONAL_MIGRATION_PRESSURE_MODIFIERS.get(season_name, 1.0)


def get_seasonal_migration_attraction_modifier(season_name: str) -> float:
    return SEASONAL_MIGRATION_ATTRACTION_MODIFIERS.get(season_name, 1.0)


def get_seasonal_migration_capacity_modifier(season_name: str) -> float:
    return SEASONAL_MIGRATION_CAPACITY_MODIFIERS.get(season_name, 1.0)


def get_seasonal_migration_flow_modifier(season_name: str) -> float:
    return SEASONAL_MIGRATION_FLOW_MODIFIERS.get(season_name, 1.0)


def get_seasonal_refugee_flow_modifier(season_name: str) -> float:
    return SEASONAL_REFUGEE_FLOW_MODIFIERS.get(season_name, 1.0)
