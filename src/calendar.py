SEASON_NAMES = ("Spring", "Summer", "Autumn", "Winter")
TURNS_PER_YEAR = 4
SEASONAL_ECONOMY_SHARE = 1.0 / TURNS_PER_YEAR
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
