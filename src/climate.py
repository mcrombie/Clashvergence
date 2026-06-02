from __future__ import annotations


SEASONS = ("Spring", "Summer", "Autumn", "Winter")


def _seasonal(
    spring: float,
    summer: float,
    autumn: float,
    winter: float,
) -> dict[str, float]:
    return {
        "Spring": spring,
        "Summer": summer,
        "Autumn": autumn,
        "Winter": winter,
    }


def _profile(
    *,
    label: str,
    group: str,
    heat: float,
    cold: float,
    aridity: float,
    humidity: float,
    seasonality: str,
    seasonal_food_production: dict[str, float],
    food_spoilage_modifier: float,
    migration_pressure: dict[str, float] | None = None,
    migration_attraction: dict[str, float] | None = None,
    migration_capacity: dict[str, float] | None = None,
    unrest_pressure: dict[str, float] | None = None,
    anomaly_vulnerability: float = 0.0,
    anomaly_food_loss_factor: float = 0.34,
) -> dict:
    return {
        "label": label,
        "group": group,
        "heat": heat,
        "cold": cold,
        "aridity": aridity,
        "humidity": humidity,
        "seasonality": seasonality,
        "seasonal_food_production": seasonal_food_production,
        "food_spoilage_modifier": food_spoilage_modifier,
        "migration_pressure": migration_pressure or {},
        "migration_attraction": migration_attraction or {},
        "migration_capacity": migration_capacity or {},
        "unrest_pressure": unrest_pressure or {},
        "anomaly_vulnerability": anomaly_vulnerability,
        "anomaly_food_loss_factor": anomaly_food_loss_factor,
    }


KOPPEN_CLIMATE_PROFILES = {
    "Af": _profile(
        label="Tropical Rainforest",
        group="A",
        heat=0.92,
        cold=0.02,
        aridity=0.04,
        humidity=0.96,
        seasonality="wet",
        seasonal_food_production=_seasonal(1.06, 1.04, 1.05, 1.04),
        food_spoilage_modifier=0.014,
        migration_pressure={"Summer": 1.03},
        migration_attraction={"Spring": 1.03, "Winter": 1.02},
        migration_capacity={"Summer": 0.97},
        unrest_pressure={"Summer": 1.04},
        anomaly_vulnerability=0.05,
        anomaly_food_loss_factor=0.38,
    ),
    "Am": _profile(
        label="Tropical Monsoon",
        group="A",
        heat=0.9,
        cold=0.03,
        aridity=0.22,
        humidity=0.82,
        seasonality="monsoon",
        seasonal_food_production=_seasonal(1.07, 1.04, 0.98, 0.96),
        food_spoilage_modifier=0.013,
        migration_pressure={"Autumn": 1.04},
        migration_attraction={"Spring": 1.04, "Summer": 1.02},
        migration_capacity={"Autumn": 0.96},
        unrest_pressure={"Autumn": 1.05},
        anomaly_vulnerability=0.065,
        anomaly_food_loss_factor=0.4,
    ),
    "Aw": _profile(
        label="Tropical Savanna",
        group="A",
        heat=0.86,
        cold=0.04,
        aridity=0.36,
        humidity=0.64,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(1.04, 1.02, 0.97, 0.99),
        food_spoilage_modifier=0.01,
        migration_pressure={"Summer": 1.05},
        migration_attraction={"Spring": 1.03, "Winter": 1.02},
        migration_capacity={"Summer": 0.96},
        unrest_pressure={"Summer": 1.05},
        anomaly_vulnerability=0.055,
        anomaly_food_loss_factor=0.39,
    ),
    "BWh": _profile(
        label="Hot Desert",
        group="B",
        heat=0.96,
        cold=0.08,
        aridity=0.96,
        humidity=0.05,
        seasonality="desert",
        seasonal_food_production=_seasonal(1.08, 0.68, 1.0, 0.95),
        food_spoilage_modifier=-0.008,
        migration_pressure={"Summer": 1.18},
        migration_attraction={"Spring": 1.03, "Summer": 0.78},
        migration_capacity={"Summer": 0.76},
        unrest_pressure={"Summer": 1.14},
        anomaly_vulnerability=0.1,
        anomaly_food_loss_factor=0.44,
    ),
    "BWk": _profile(
        label="Cold Desert",
        group="B",
        heat=0.42,
        cold=0.66,
        aridity=0.92,
        humidity=0.08,
        seasonality="desert",
        seasonal_food_production=_seasonal(0.98, 0.82, 0.96, 0.72),
        food_spoilage_modifier=-0.01,
        migration_pressure={"Summer": 1.08, "Winter": 1.08},
        migration_attraction={"Summer": 0.88, "Winter": 0.82},
        migration_capacity={"Summer": 0.84, "Winter": 0.78},
        unrest_pressure={"Summer": 1.08, "Winter": 1.07},
        anomaly_vulnerability=0.085,
        anomaly_food_loss_factor=0.42,
    ),
    "BSh": _profile(
        label="Hot Steppe",
        group="B",
        heat=0.74,
        cold=0.18,
        aridity=0.7,
        humidity=0.26,
        seasonality="semi_arid",
        seasonal_food_production=_seasonal(1.08, 0.86, 1.02, 0.95),
        food_spoilage_modifier=-0.004,
        migration_pressure={"Summer": 1.1},
        migration_attraction={"Spring": 1.05, "Autumn": 1.04, "Summer": 0.92},
        migration_capacity={"Spring": 1.04, "Summer": 0.9},
        unrest_pressure={"Summer": 1.08, "Autumn": 0.97},
        anomaly_vulnerability=0.065,
        anomaly_food_loss_factor=0.4,
    ),
    "BSk": _profile(
        label="Cold Steppe",
        group="B",
        heat=0.42,
        cold=0.46,
        aridity=0.62,
        humidity=0.32,
        seasonality="semi_arid",
        seasonal_food_production=_seasonal(1.05, 0.9, 1.04, 0.88),
        food_spoilage_modifier=-0.003,
        migration_pressure={"Winter": 1.05},
        migration_attraction={"Spring": 1.05, "Autumn": 1.06, "Winter": 0.9},
        migration_capacity={"Spring": 1.04, "Winter": 0.86},
        unrest_pressure={"Winter": 1.05, "Autumn": 0.96},
        anomaly_vulnerability=0.045,
        anomaly_food_loss_factor=0.38,
    ),
    "Csa": _profile(
        label="Hot-Summer Mediterranean",
        group="C",
        heat=0.68,
        cold=0.16,
        aridity=0.46,
        humidity=0.48,
        seasonality="dry_summer",
        seasonal_food_production=_seasonal(1.1, 0.78, 1.04, 0.98),
        food_spoilage_modifier=0.001,
        migration_pressure={"Summer": 1.08},
        migration_attraction={"Spring": 1.05, "Autumn": 1.04, "Summer": 0.9},
        migration_capacity={"Summer": 0.9},
        unrest_pressure={"Summer": 1.08, "Autumn": 0.96},
        anomaly_vulnerability=0.055,
        anomaly_food_loss_factor=0.39,
    ),
    "Csb": _profile(
        label="Warm-Summer Mediterranean",
        group="C",
        heat=0.48,
        cold=0.22,
        aridity=0.38,
        humidity=0.56,
        seasonality="dry_summer",
        seasonal_food_production=_seasonal(1.08, 0.86, 1.05, 0.96),
        food_spoilage_modifier=0.0,
        migration_pressure={"Summer": 1.05},
        migration_attraction={"Spring": 1.05, "Autumn": 1.05},
        migration_capacity={"Summer": 0.94},
        unrest_pressure={"Summer": 1.05, "Autumn": 0.96},
        anomaly_vulnerability=0.04,
        anomaly_food_loss_factor=0.36,
    ),
    "Csc": _profile(
        label="Cold-Summer Mediterranean",
        group="C",
        heat=0.28,
        cold=0.46,
        aridity=0.34,
        humidity=0.56,
        seasonality="dry_summer",
        seasonal_food_production=_seasonal(0.94, 1.02, 0.92, 0.76),
        food_spoilage_modifier=-0.002,
        migration_pressure={"Winter": 1.06},
        migration_attraction={"Summer": 1.03, "Winter": 0.84},
        migration_capacity={"Winter": 0.82},
        unrest_pressure={"Winter": 1.06},
        anomaly_vulnerability=0.035,
        anomaly_food_loss_factor=0.35,
    ),
    "Cwa": _profile(
        label="Dry-Winter Humid Subtropical",
        group="C",
        heat=0.7,
        cold=0.18,
        aridity=0.28,
        humidity=0.68,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(1.12, 1.06, 0.95, 0.82),
        food_spoilage_modifier=0.006,
        migration_pressure={"Winter": 1.04},
        migration_attraction={"Spring": 1.05, "Summer": 1.02, "Winter": 0.94},
        migration_capacity={"Winter": 0.92},
        unrest_pressure={"Winter": 1.04},
        anomaly_vulnerability=0.05,
        anomaly_food_loss_factor=0.38,
    ),
    "Cwb": _profile(
        label="Dry-Winter Subtropical Highland",
        group="C",
        heat=0.42,
        cold=0.32,
        aridity=0.26,
        humidity=0.62,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(1.06, 1.02, 0.94, 0.78),
        food_spoilage_modifier=0.002,
        migration_pressure={"Winter": 1.05},
        migration_attraction={"Spring": 1.04, "Summer": 1.03, "Winter": 0.9},
        migration_capacity={"Winter": 0.9},
        unrest_pressure={"Winter": 1.04},
        anomaly_vulnerability=0.035,
        anomaly_food_loss_factor=0.35,
    ),
    "Cwc": _profile(
        label="Dry-Winter Subpolar Oceanic",
        group="C",
        heat=0.24,
        cold=0.56,
        aridity=0.24,
        humidity=0.6,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(0.9, 1.04, 0.88, 0.66),
        food_spoilage_modifier=-0.002,
        migration_pressure={"Winter": 1.08},
        migration_attraction={"Summer": 1.03, "Winter": 0.8},
        migration_capacity={"Winter": 0.78},
        unrest_pressure={"Winter": 1.08},
        anomaly_vulnerability=0.035,
        anomaly_food_loss_factor=0.35,
    ),
    "Cfa": _profile(
        label="Humid Subtropical",
        group="C",
        heat=0.68,
        cold=0.2,
        aridity=0.18,
        humidity=0.76,
        seasonality="no_dry_season",
        seasonal_food_production=_seasonal(1.08, 1.04, 1.0, 0.88),
        food_spoilage_modifier=0.008,
        migration_pressure={"Summer": 1.03},
        migration_attraction={"Spring": 1.04, "Autumn": 1.03},
        migration_capacity={"Winter": 0.95},
        unrest_pressure={"Summer": 1.05},
        anomaly_vulnerability=0.035,
        anomaly_food_loss_factor=0.36,
    ),
    "Cfb": _profile(
        label="Oceanic",
        group="C",
        heat=0.38,
        cold=0.26,
        aridity=0.14,
        humidity=0.74,
        seasonality="no_dry_season",
        seasonal_food_production=_seasonal(1.04, 0.98, 1.02, 0.98),
        food_spoilage_modifier=0.004,
        migration_pressure={"Winter": 1.04},
        migration_attraction={"Summer": 1.04, "Autumn": 1.04, "Winter": 0.96},
        migration_capacity={"Winter": 0.96},
        unrest_pressure={"Winter": 1.03},
        anomaly_vulnerability=-0.02,
        anomaly_food_loss_factor=0.3,
    ),
    "Cfc": _profile(
        label="Subpolar Oceanic",
        group="C",
        heat=0.22,
        cold=0.58,
        aridity=0.12,
        humidity=0.72,
        seasonality="no_dry_season",
        seasonal_food_production=_seasonal(0.9, 1.08, 0.92, 0.74),
        food_spoilage_modifier=0.0,
        migration_pressure={"Winter": 1.08},
        migration_attraction={"Summer": 1.05, "Winter": 0.84},
        migration_capacity={"Winter": 0.82},
        unrest_pressure={"Winter": 1.06, "Summer": 0.98},
        anomaly_vulnerability=0.02,
        anomaly_food_loss_factor=0.34,
    ),
    "Dsa": _profile(
        label="Hot-Summer Dry-Summer Continental",
        group="D",
        heat=0.66,
        cold=0.52,
        aridity=0.48,
        humidity=0.42,
        seasonality="dry_summer",
        seasonal_food_production=_seasonal(1.05, 0.86, 1.0, 0.58),
        food_spoilage_modifier=-0.003,
        migration_pressure={"Summer": 1.06, "Winter": 1.09},
        migration_attraction={"Spring": 1.03, "Winter": 0.78},
        migration_capacity={"Winter": 0.72},
        unrest_pressure={"Summer": 1.04, "Winter": 1.09},
        anomaly_vulnerability=0.06,
        anomaly_food_loss_factor=0.4,
    ),
    "Dsb": _profile(
        label="Warm-Summer Dry-Summer Continental",
        group="D",
        heat=0.46,
        cold=0.58,
        aridity=0.42,
        humidity=0.46,
        seasonality="dry_summer",
        seasonal_food_production=_seasonal(0.98, 1.0, 0.95, 0.54),
        food_spoilage_modifier=-0.004,
        migration_pressure={"Winter": 1.1},
        migration_attraction={"Summer": 1.03, "Winter": 0.76},
        migration_capacity={"Winter": 0.72},
        unrest_pressure={"Winter": 1.09},
        anomaly_vulnerability=0.055,
        anomaly_food_loss_factor=0.39,
    ),
    "Dsc": _profile(
        label="Cold-Summer Dry-Summer Subarctic",
        group="D",
        heat=0.28,
        cold=0.78,
        aridity=0.4,
        humidity=0.42,
        seasonality="dry_summer",
        seasonal_food_production=_seasonal(0.74, 1.08, 0.76, 0.38),
        food_spoilage_modifier=-0.007,
        migration_pressure={"Winter": 1.16},
        migration_attraction={"Summer": 1.03, "Winter": 0.68},
        migration_capacity={"Winter": 0.62},
        unrest_pressure={"Winter": 1.14},
        anomaly_vulnerability=0.06,
        anomaly_food_loss_factor=0.39,
    ),
    "Dsd": _profile(
        label="Severe-Winter Dry-Summer Subarctic",
        group="D",
        heat=0.18,
        cold=0.94,
        aridity=0.38,
        humidity=0.38,
        seasonality="dry_summer",
        seasonal_food_production=_seasonal(0.62, 1.02, 0.64, 0.3),
        food_spoilage_modifier=-0.01,
        migration_pressure={"Winter": 1.22},
        migration_attraction={"Summer": 1.0, "Winter": 0.58},
        migration_capacity={"Winter": 0.52},
        unrest_pressure={"Winter": 1.18},
        anomaly_vulnerability=0.07,
        anomaly_food_loss_factor=0.4,
    ),
    "Dwa": _profile(
        label="Hot-Summer Dry-Winter Continental",
        group="D",
        heat=0.66,
        cold=0.54,
        aridity=0.28,
        humidity=0.58,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(1.1, 1.08, 0.94, 0.52),
        food_spoilage_modifier=-0.002,
        migration_pressure={"Winter": 1.1},
        migration_attraction={"Spring": 1.04, "Summer": 1.03, "Winter": 0.76},
        migration_capacity={"Winter": 0.72},
        unrest_pressure={"Winter": 1.1},
        anomaly_vulnerability=0.055,
        anomaly_food_loss_factor=0.39,
    ),
    "Dwb": _profile(
        label="Warm-Summer Dry-Winter Continental",
        group="D",
        heat=0.44,
        cold=0.64,
        aridity=0.24,
        humidity=0.56,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(1.0, 1.1, 0.88, 0.46),
        food_spoilage_modifier=-0.004,
        migration_pressure={"Winter": 1.12},
        migration_attraction={"Summer": 1.04, "Winter": 0.72},
        migration_capacity={"Winter": 0.68},
        unrest_pressure={"Winter": 1.11},
        anomaly_vulnerability=0.05,
        anomaly_food_loss_factor=0.38,
    ),
    "Dwc": _profile(
        label="Cold-Summer Dry-Winter Subarctic",
        group="D",
        heat=0.24,
        cold=0.82,
        aridity=0.22,
        humidity=0.52,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(0.72, 1.14, 0.72, 0.34),
        food_spoilage_modifier=-0.007,
        migration_pressure={"Winter": 1.18},
        migration_attraction={"Summer": 1.04, "Winter": 0.64},
        migration_capacity={"Winter": 0.58},
        unrest_pressure={"Winter": 1.16},
        anomaly_vulnerability=0.06,
        anomaly_food_loss_factor=0.39,
    ),
    "Dwd": _profile(
        label="Severe-Winter Dry-Winter Subarctic",
        group="D",
        heat=0.14,
        cold=0.96,
        aridity=0.2,
        humidity=0.48,
        seasonality="dry_winter",
        seasonal_food_production=_seasonal(0.58, 1.08, 0.58, 0.26),
        food_spoilage_modifier=-0.01,
        migration_pressure={"Winter": 1.24},
        migration_attraction={"Summer": 1.0, "Winter": 0.56},
        migration_capacity={"Winter": 0.5},
        unrest_pressure={"Winter": 1.2},
        anomaly_vulnerability=0.07,
        anomaly_food_loss_factor=0.4,
    ),
    "Dfa": _profile(
        label="Hot-Summer Humid Continental",
        group="D",
        heat=0.64,
        cold=0.5,
        aridity=0.14,
        humidity=0.68,
        seasonality="no_dry_season",
        seasonal_food_production=_seasonal(1.08, 1.12, 0.98, 0.58),
        food_spoilage_modifier=-0.001,
        migration_pressure={"Winter": 1.08},
        migration_attraction={"Summer": 1.03, "Winter": 0.8},
        migration_capacity={"Winter": 0.74},
        unrest_pressure={"Winter": 1.09, "Summer": 0.98},
        anomaly_vulnerability=0.04,
        anomaly_food_loss_factor=0.36,
    ),
    "Dfb": _profile(
        label="Warm-Summer Humid Continental",
        group="D",
        heat=0.42,
        cold=0.62,
        aridity=0.12,
        humidity=0.66,
        seasonality="no_dry_season",
        seasonal_food_production=_seasonal(0.88, 1.14, 0.96, 0.7),
        food_spoilage_modifier=-0.004,
        migration_pressure={"Winter": 1.1},
        migration_attraction={"Summer": 1.04, "Winter": 0.82},
        migration_capacity={"Winter": 0.78},
        unrest_pressure={"Winter": 1.08, "Summer": 0.97},
        anomaly_vulnerability=0.03,
        anomaly_food_loss_factor=0.36,
    ),
    "Dfc": _profile(
        label="Subarctic",
        group="D",
        heat=0.22,
        cold=0.82,
        aridity=0.1,
        humidity=0.62,
        seasonality="no_dry_season",
        seasonal_food_production=_seasonal(0.72, 1.18, 0.8, 0.46),
        food_spoilage_modifier=-0.006,
        migration_pressure={"Winter": 1.16},
        migration_attraction={"Summer": 1.06, "Winter": 0.68},
        migration_capacity={"Winter": 0.62},
        unrest_pressure={"Winter": 1.14, "Summer": 0.96},
        anomaly_vulnerability=0.045,
        anomaly_food_loss_factor=0.37,
    ),
    "Dfd": _profile(
        label="Severe-Winter Subarctic",
        group="D",
        heat=0.12,
        cold=0.96,
        aridity=0.1,
        humidity=0.56,
        seasonality="no_dry_season",
        seasonal_food_production=_seasonal(0.6, 1.12, 0.66, 0.34),
        food_spoilage_modifier=-0.01,
        migration_pressure={"Winter": 1.24},
        migration_attraction={"Summer": 1.02, "Winter": 0.56},
        migration_capacity={"Winter": 0.5},
        unrest_pressure={"Winter": 1.2},
        anomaly_vulnerability=0.06,
        anomaly_food_loss_factor=0.39,
    ),
    "ET": _profile(
        label="Tundra",
        group="E",
        heat=0.06,
        cold=0.9,
        aridity=0.36,
        humidity=0.32,
        seasonality="polar",
        seasonal_food_production=_seasonal(0.35, 0.78, 0.42, 0.15),
        food_spoilage_modifier=-0.012,
        migration_pressure={"Winter": 1.25, "Autumn": 1.08},
        migration_attraction={"Summer": 0.86, "Winter": 0.4},
        migration_capacity={"Summer": 0.72, "Winter": 0.34},
        unrest_pressure={"Winter": 1.18},
        anomaly_vulnerability=0.07,
        anomaly_food_loss_factor=0.34,
    ),
    "EF": _profile(
        label="Ice Cap",
        group="E",
        heat=0.01,
        cold=1.0,
        aridity=0.5,
        humidity=0.18,
        seasonality="polar",
        seasonal_food_production=_seasonal(0.05, 0.12, 0.05, 0.02),
        food_spoilage_modifier=-0.015,
        migration_pressure={"Winter": 1.35, "Autumn": 1.14},
        migration_attraction={"Summer": 0.42, "Winter": 0.18},
        migration_capacity={"Summer": 0.28, "Winter": 0.12},
        unrest_pressure={"Winter": 1.25},
        anomaly_vulnerability=0.05,
        anomaly_food_loss_factor=0.3,
    ),
}


CLIMATE_ALIASES = {
    "temperate": "Cfb",
    "oceanic": "Cfb",
    "cold": "Dfb",
    "continental": "Dfb",
    "arid": "BWh",
    "desert": "BWh",
    "steppe": "BSk",
    "tropical": "Aw",
    "savanna": "Aw",
    "rainforest": "Af",
    "monsoon": "Am",
    "mediterranean": "Csa",
    "subtropical": "Cfa",
    "subarctic": "Dfc",
    "tundra": "ET",
    "polar": "ET",
    "ice": "EF",
}

CLIMATE_RULES = KOPPEN_CLIMATE_PROFILES
NORMALIZED_KOPPEN_CODES = {
    code.lower(): code
    for code in KOPPEN_CLIMATE_PROFILES
}


def normalize_climate(climate: str | None) -> str:
    if climate is None:
        return "Cfb"
    raw = str(climate).strip()
    if not raw:
        return "Cfb"
    lowered = raw.lower()
    if lowered in CLIMATE_ALIASES:
        return CLIMATE_ALIASES[lowered]
    if lowered in NORMALIZED_KOPPEN_CODES:
        return NORMALIZED_KOPPEN_CODES[lowered]
    raise ValueError(f"Unsupported climate: {climate}")


def is_supported_climate(climate: str | None) -> bool:
    try:
        normalize_climate(climate)
    except ValueError:
        return False
    return True


def format_climate_label(climate: str | None) -> str:
    normalized = normalize_climate(climate)
    return KOPPEN_CLIMATE_PROFILES[normalized]["label"]


def format_climate_code_label(climate: str | None) -> str:
    normalized = normalize_climate(climate)
    return f"{normalized} {format_climate_label(normalized)}"


def get_climate_profile(climate: str | None) -> dict:
    return KOPPEN_CLIMATE_PROFILES[normalize_climate(climate)]


def get_climate_group(climate: str | None) -> str:
    return str(get_climate_profile(climate)["group"])


def get_climate_group_label(climate: str | None) -> str:
    group = get_climate_group(climate)
    return {
        "A": "Tropical",
        "B": "Dry",
        "C": "Temperate",
        "D": "Continental",
        "E": "Polar",
    }.get(group, group)


def _get_seasonal_multiplier(
    climate: str | None,
    profile_key: str,
    season_name: str,
) -> float:
    profile = get_climate_profile(climate)
    seasonal_values = profile.get(profile_key, {})
    return float(seasonal_values.get(season_name, 1.0))


def get_seasonal_climate_food_production_multiplier(
    climate: str | None,
    season_name: str,
) -> float:
    return _get_seasonal_multiplier(climate, "seasonal_food_production", season_name)


def get_climate_food_spoilage_modifier(climate: str | None) -> float:
    return float(get_climate_profile(climate).get("food_spoilage_modifier", 0.0))


def get_seasonal_climate_migration_pressure_multiplier(
    climate: str | None,
    season_name: str,
) -> float:
    return _get_seasonal_multiplier(climate, "migration_pressure", season_name)


def get_seasonal_climate_migration_attraction_multiplier(
    climate: str | None,
    season_name: str,
) -> float:
    return _get_seasonal_multiplier(climate, "migration_attraction", season_name)


def get_seasonal_climate_migration_capacity_multiplier(
    climate: str | None,
    season_name: str,
) -> float:
    return _get_seasonal_multiplier(climate, "migration_capacity", season_name)


def get_seasonal_climate_unrest_multiplier(
    climate: str | None,
    season_name: str,
) -> float:
    return _get_seasonal_multiplier(climate, "unrest_pressure", season_name)


def get_climate_anomaly_vulnerability(climate: str | None) -> float:
    return float(get_climate_profile(climate).get("anomaly_vulnerability", 0.0))


def get_climate_anomaly_food_loss_factor(climate: str | None) -> float:
    return float(get_climate_profile(climate).get("anomaly_food_loss_factor", 0.34))


def get_climate_similarity(first: str | None, second: str | None) -> float:
    first_code = normalize_climate(first)
    second_code = normalize_climate(second)
    if first_code == second_code:
        return 1.0

    first_profile = get_climate_profile(first_code)
    second_profile = get_climate_profile(second_code)
    trait_distance = (
        abs(first_profile["heat"] - second_profile["heat"]) * 0.25
        + abs(first_profile["cold"] - second_profile["cold"]) * 0.25
        + abs(first_profile["aridity"] - second_profile["aridity"]) * 0.28
        + abs(first_profile["humidity"] - second_profile["humidity"]) * 0.22
    )
    first_group = str(first_profile["group"])
    second_group = str(second_profile["group"])
    if first_group == second_group:
        group_penalty = 0.0
    elif {first_group, second_group} == {"C", "D"}:
        group_penalty = 0.06
    elif {first_group, second_group} == {"B", "D"}:
        group_penalty = 0.12
    elif {first_group, second_group} == {"A", "C"}:
        group_penalty = 0.14
    else:
        group_penalty = 0.2

    seasonality_penalty = (
        0.0
        if first_profile["seasonality"] == second_profile["seasonality"]
        else 0.04
    )
    return round(max(0.05, min(1.0, 1.0 - trait_distance - group_penalty - seasonality_penalty)), 3)


def get_climate_expansion_modifier(climate: str | None) -> float:
    profile = get_climate_profile(climate)
    return round(
        (0.08 * (1.0 - profile["cold"]))
        + (0.06 * (1.0 - profile["aridity"]))
        - (0.08 * profile["cold"])
        - (0.05 * profile["aridity"])
        + (0.02 * profile["humidity"]),
        3,
    )


def classify_koppen_climate(
    monthly_temperature_c: list[float],
    monthly_precipitation_mm: list[float],
) -> str:
    if len(monthly_temperature_c) != 12 or len(monthly_precipitation_mm) != 12:
        raise ValueError("Koppen classification requires 12 monthly temperature and precipitation values.")

    temperatures = [float(value) for value in monthly_temperature_c]
    precipitation = [max(0.0, float(value)) for value in monthly_precipitation_mm]
    coldest = min(temperatures)
    hottest = max(temperatures)
    mean_temp = sum(temperatures) / 12.0
    annual_precip = sum(precipitation)
    months_above_10 = sum(1 for temperature in temperatures if temperature >= 10.0)
    warm_months = range(3, 9)
    cool_months = [0, 1, 2, 9, 10, 11]
    warm_precip = sum(precipitation[index] for index in warm_months)
    cool_precip = sum(precipitation[index] for index in cool_months)
    warm_fraction = warm_precip / annual_precip if annual_precip > 0 else 0.5
    aridity_threshold = 20.0 * mean_temp
    if warm_fraction >= 0.7:
        aridity_threshold += 280.0
    elif warm_fraction >= 0.3:
        aridity_threshold += 140.0

    if annual_precip < aridity_threshold:
        dryness = "W" if annual_precip < (aridity_threshold * 0.5) else "S"
        heat = "h" if mean_temp >= 18.0 else "k"
        return normalize_climate(f"B{dryness}{heat}")

    driest_month = min(precipitation)
    if coldest >= 18.0:
        if driest_month >= 60.0:
            return "Af"
        if driest_month >= 100.0 - (annual_precip / 25.0):
            return "Am"
        return "Aw"

    if hottest < 10.0:
        return "ET" if hottest >= 0.0 else "EF"

    group = "C" if coldest > 0.0 else "D"
    summer_precip = [precipitation[index] for index in warm_months]
    winter_precip = [precipitation[index] for index in cool_months]
    dry_summer = min(summer_precip) < 40.0 and min(summer_precip) < max(winter_precip) / 3.0
    dry_winter = min(winter_precip) < max(summer_precip) / 10.0
    if dry_summer and not dry_winter:
        seasonal_letter = "s"
    elif dry_winter and not dry_summer:
        seasonal_letter = "w"
    else:
        seasonal_letter = "f"

    if hottest >= 22.0 and months_above_10 >= 4:
        heat_letter = "a"
    elif months_above_10 >= 4:
        heat_letter = "b"
    elif group == "D" and coldest <= -38.0:
        heat_letter = "d"
    else:
        heat_letter = "c"
    return normalize_climate(f"{group}{seasonal_letter}{heat_letter}")
