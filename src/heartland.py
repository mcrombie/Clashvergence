from __future__ import annotations

from copy import deepcopy
import random
import re

from src.calendar import (
    get_seasonal_migration_attraction_modifier,
    get_seasonal_migration_capacity_modifier,
    get_seasonal_migration_flow_modifier,
    get_seasonal_migration_pressure_modifier,
    get_seasonal_refugee_flow_modifier,
    get_seasonal_unrest_pressure_modifier,
    get_turn_season_name,
)
from src.config import (
    ADMIN_BASE_CAPACITY_PER_REGION,
    ADMIN_BURDEN_CORE,
    ADMIN_BURDEN_FRONTIER,
    ADMIN_BURDEN_HOMELAND,
    ADMIN_DISTANCE_PER_ROUTE_DEPTH,
    ADMIN_FOREIGN_BORDER_DISTANCE,
    ADMIN_HOSTILE_BORDER_DISTANCE,
    ADMIN_INTEGRATION_AUTONOMY_FACTOR,
    ADMIN_INTEGRATION_EFFICIENCY_FACTOR,
    ADMIN_INTEGRATION_SUPPORT_FACTOR,
    ADMIN_LEGITIMACY_WEIGHT,
    ADMIN_MOBILITY_CAPACITY_FACTOR,
    ADMIN_OVEREXTENSION_PENALTY_FACTOR,
    ADMIN_POPULATION_BURDEN_FACTOR,
    ADMIN_POPULATION_BURDEN_MAX,
    ADMIN_RELIGIOUS_LEGITIMACY_WEIGHT,
    ADMIN_SUPPORT_CAPACITY_FACTOR,
    ADMIN_SUPPORT_INFRASTRUCTURE_FACTOR,
    ADMIN_SUPPORT_INTEGRATION_FACTOR,
    ADMIN_SUPPORT_MARKET_FACTOR,
    ADMIN_SUPPORT_ROAD_FACTOR,
    ADMIN_SUPPORT_SETTLEMENT_BONUSES,
    ADMIN_SUPPORT_STOREHOUSE_FACTOR,
    ADMIN_TAXABLE_CAPACITY_FACTOR,
    ADMIN_UNREST_AUTONOMY_FACTOR,
    ADMIN_UNREST_BURDEN_FACTOR,
    MIGRATION_ATTRACTION_CITY_BONUS,
    MIGRATION_ATTRACTION_CORE_BONUS,
    MIGRATION_ATTRACTION_DEVELOPMENT_FACTOR,
    MIGRATION_ATTRACTION_FOOD_FACTOR,
    MIGRATION_ATTRACTION_FRONTIER_BONUS,
    MIGRATION_ATTRACTION_LOW_UNREST_FACTOR,
    MIGRATION_ATTRACTION_SURPLUS_FACTOR,
    MIGRATION_ATTRACTION_TRADE_FACTOR,
    MIGRATION_EVENT_MINIMUM,
    MIGRATION_FRIENDLY_BORDER_FACTOR,
    MIGRATION_FRONTIER_INTEGRATION_PER_100,
    MIGRATION_FRONTIER_UNREST_REDUCTION,
    MIGRATION_MAX_SHARE_PER_TURN,
    MIGRATION_MIN_SOURCE_POPULATION,
    MIGRATION_NEIGHBOR_FACTOR,
    MIGRATION_PARENT_CHILD_FACTOR,
    MIGRATION_PRESSURE_FOOD_FACTOR,
    MIGRATION_PRESSURE_FRONTIER_FACTOR,
    MIGRATION_PRESSURE_SURPLUS_FACTOR,
    MIGRATION_PRESSURE_UNREST_FACTOR,
    MIGRATION_REFUGEE_CRISIS_BONUS,
    MIGRATION_REFUGEE_SEVERE_UNREST,
    MIGRATION_ROUTE_ANCHOR_FACTOR,
    DIPLOMACY_RIVAL_THRESHOLD,
    ETHNIC_CLAIM_INTEGRATION_BONUS,
    ETHNIC_CLAIM_UNREST_REDUCTION,
    ETHNIC_INTEGRATION_MIN_MULTIPLIER,
    ETHNIC_UNREST_CALMING_EFFECT,
    ETHNIC_UNREST_CALMING_THRESHOLD,
    ETHNIC_UNREST_LOW_AFFINITY_PRESSURE,
    ETHNIC_UNREST_NEUTRAL_THRESHOLD,
    ETHNIC_UNREST_SEVERE_AFFINITY_PRESSURE,
    ETHNIC_UNREST_SEVERE_THRESHOLD,
    REGIME_CONTESTATION_CORE_UNREST_BONUS,
    REGIME_CONTESTATION_HOMELAND_UNREST_BONUS,
    REGIME_CONTESTATION_UNREST_BASE,
    REGIME_AGITATION_CLAIMANT_BONUS,
    REGIME_AGITATION_HEAVY_BACKLASH_MULTIPLIER,
    REGIME_AGITATION_HEAVY_COST_MULTIPLIER,
    REGIME_AGITATION_HEAVY_MODE_THRESHOLD,
    REGIME_AGITATION_HEAVY_PRESSURE_MULTIPLIER,
    REGIME_AGITATION_HOMEFRONT_UNREST_FACTOR,
    REGIME_AGITATION_INSULARITY_FACTOR,
    REGIME_AGITATION_LOW_BACKLASH_MULTIPLIER,
    REGIME_AGITATION_LOW_COST_MULTIPLIER,
    REGIME_AGITATION_LOW_MODE_THRESHOLD,
    REGIME_AGITATION_LOW_PRESSURE_MULTIPLIER,
    REGIME_AGITATION_MAX,
    REGIME_AGITATION_MAX_SPONSOR_FACTOR,
    REGIME_AGITATION_MIN_SPONSOR_FACTOR,
    REGIME_AGITATION_TREASURY_COST_FACTOR,
    REGIME_AGITATION_TREASURY_FACTOR,
    REGIME_AGITATION_TREASURY_MAX_BONUS,
    REGIME_AGITATION_UNREST_PER_SPONSOR,
    REGIME_AGITATION_WAR_POSTURE_FACTOR,
    SUCCESSION_CLAIMANT_PRESSURE_DECAY,
    SUCCESSION_CLAIMANT_REGION_MIN_POPULATION,
    SUCCESSION_CLAIMANT_TRIGGER_THRESHOLD,
    SUCCESSION_CRISIS_TREASURY_HIT,
    SUCCESSION_CRISIS_TURNS,
    SUCCESSION_CRISIS_UNREST_PRESSURE,
    SUCCESSION_FOOD_DEFICIT_LEGITIMACY_PENALTY,
    SUCCESSION_FORCED_AGE,
    SUCCESSION_INITIAL_HEIR_PREPAREDNESS_MAX,
    SUCCESSION_INITIAL_HEIR_PREPAREDNESS_MIN,
    SUCCESSION_INITIAL_LEGITIMACY_MAX,
    SUCCESSION_INITIAL_LEGITIMACY_MIN,
    SUCCESSION_INITIAL_PRESTIGE_MAX,
    SUCCESSION_INITIAL_PRESTIGE_MIN,
    SUCCESSION_MAX_TRIGGER_CHANCE,
    SUCCESSION_MINOR_HEIR_AGE,
    SUCCESSION_PRESTIGE_GAIN_FACTOR,
    SUCCESSION_PROSPERITY_LEGITIMACY_GAIN,
    SUCCESSION_REALM_LEGITIMACY_PENALTY,
    SUCCESSION_REGENCY_TURNS,
    SUCCESSION_REGENCY_UNREST_PRESSURE,
    SUCCESSION_STABLE_TREASURY_HIT,
    SUCCESSION_TRADE_LEGITIMACY_GAIN,
    SUCCESSION_TRIGGER_AGE,
    SUCCESSION_UNREST_LEGITIMACY_PENALTY,
    POPULATION_BASE,
    POPULATION_FOOD_DEFICIT_MAX_PENALTY,
    POPULATION_FOOD_DEFICIT_PENALTY_FACTOR,
    POPULATION_FOOD_SURPLUS_BONUS_FACTOR,
    POPULATION_FOOD_SURPLUS_MAX_BONUS,
    POPULATION_GROWTH_PER_TURN,
    POPULATION_MINIMUM,
    POPULATION_PER_CONNECTION,
    POPULATION_PER_RESOURCE,
    POPULATION_SECESSION_LOSS,
    POPULATION_STARTING_OWNER_BONUS,
    POPULATION_UNOWNED_GROWTH_FACTOR,
    POPULATION_UNREST_CRISIS_LOSS,
    POPULATION_UNREST_GROWTH_PENALTY,
    POLITY_ADVANCEMENT_UNREST_REDUCTION,
    RELIGION_CLERGY_LEGITIMACY_FACTOR,
    RELIGION_CONVERSION_BASE,
    RELIGION_CONVERSION_INTEGRATION_FACTOR,
    RELIGION_CONVERSION_SHRINE_FACTOR,
    RELIGION_DISSENT_UNREST_FACTOR,
    RELIGION_INITIAL_CLERGY_SUPPORT_MAX,
    RELIGION_INITIAL_CLERGY_SUPPORT_MIN,
    RELIGION_INITIAL_LEGITIMACY_MAX,
    RELIGION_INITIAL_LEGITIMACY_MIN,
    RELIGION_INITIAL_STATE_CULT_MAX,
    RELIGION_INITIAL_STATE_CULT_MIN,
    RELIGION_INITIAL_TOLERANCE_MAX,
    RELIGION_INITIAL_TOLERANCE_MIN,
    RELIGION_INITIAL_ZEAL_MAX,
    RELIGION_INITIAL_ZEAL_MIN,
    RELIGION_PILGRIMAGE_PER_SHRINE,
    RELIGION_REFORM_MIN_INTERVAL,
    RELIGION_REFORM_PRESSURE_FACTOR,
    RELIGION_REFORM_STATE_MIN_TIER,
    RELIGION_REFORM_THRESHOLD,
    RELIGION_SACRED_SITE_BONUS,
    RELIGION_SACRED_SITE_HOME_SHRINE,
    RELIGION_TOLERANCE_UNREST_REDUCTION,
    RELIGION_UNITY_LEGITIMACY_FACTOR,
    UNREST_CLIMATE_PRESSURE_FACTOR,
    UNREST_CONQUEST_START,
    UNREST_CRISIS_DURATION,
    UNREST_CRISIS_TREASURY_HIT,
    UNREST_CRITICAL_THRESHOLD,
    UNREST_DECAY_PER_TURN,
    UNREST_DISTURBANCE_DURATION,
    UNREST_DISTURBANCE_TREASURY_HIT,
    UNREST_EXPANSION_START,
    UNREST_FRONTIER_BURDEN_FACTOR,
    UNREST_FRONTIER_PRESSURE,
    UNREST_INTEGRATION_PRESSURE_FACTOR,
    UNREST_MAX,
    UNREST_MODERATE_THRESHOLD,
    REBEL_FULL_INDEPENDENCE_THRESHOLD,
    REBEL_INDEPENDENCE_PER_EXTRA_REGION,
    REBEL_INDEPENDENCE_PER_TURN,
    REBEL_INDEPENDENCE_TREASURY_BONUS,
    REBEL_MATURE_GOVERNMENT_TYPE,
    REBEL_PARENT_RECLAIM_MAX_BONUS,
    REBEL_RECURSIVE_UNREST_REDUCTION,
    REBEL_SECESSION_COOLDOWN_TURNS,
    REBEL_STARTING_TREASURY,
    REBEL_STARTING_UNREST,
    UNREST_SECESSION_CRISIS_TURNS,
    UNREST_SECESSION_RESOURCE_LOSS,
    UNREST_SECESSION_THRESHOLD,
)
from src.diplomacy import get_relationship_status, seed_rebel_origin_relationship
from src.governance import (
    REGIME_AGITATION_DIPLOMATIC_FORMS,
    REGIME_AGITATION_GOVERNMENT_FORM_BIAS,
    get_faction_administrative_capacity_modifier,
    get_faction_administrative_reach_modifier,
    get_faction_income_modifier,
    get_faction_integration_modifier,
    get_faction_maintenance_modifier,
    get_faction_realm_size_unrest_factor,
    get_faction_stability_modifier,
)
from src.models import (
    Ethnicity,
    Event,
    Faction,
    FactionIdentity,
    FactionReligionState,
    FactionSuccessionState,
    GOVERNMENT_FORMS_BY_TIER,
    LanguageProfile,
    Religion,
    Region,
    WorldState,
    get_default_government_form,
)
from src.region_state import (
    CORE_INTEGRATION_SCORE,
    HOMELAND_INTEGRATION_SCORE,
    get_faction_frontier_burden,
    get_region_attack_projection_modifier,
    get_region_climate_affinity,
    get_region_climate_integration_modifier,
    get_region_core_defense_bonus,
    get_region_core_status,
)
from src.resource_economy import (
    advance_region_domesticable_resources,
    apply_region_resource_damage,
    ensure_region_resource_state,
    get_region_effective_income,
    get_region_maintenance_cost,
    get_region_taxable_value,
    initialize_region_resources,
    refresh_region_resource_state,
    update_faction_resource_economy,
)
from src.resources import (
    CAPACITY_FOOD_SECURITY,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_LIVESTOCK,
    RESOURCE_SALT,
    RESOURCE_VALUE_WEIGHTS,
    RESOURCE_STONE,
    RESOURCE_TIMBER,
    RESOURCE_TEXTILES,
    RESOURCE_WILD_FOOD,
    format_resource_map,
    get_legacy_region_resource_value,
    get_region_resource_summary,
    normalize_resource_map,
)
from src.terrain import (
    get_seasonal_terrain_migration_attraction_multiplier,
    get_seasonal_terrain_migration_capacity_multiplier,
    get_seasonal_terrain_unrest_multiplier,
    get_terrain_profile,
)


CONQUEST_INTEGRATION_SCORE = 1.0
PER_TURN_FRONTIER_GAIN = 1.0
PER_TURN_CORE_GAIN = 0.35
SURPLUS_RESOURCE_YIELD = 2.5
SURPLUS_CONNECTION_YIELD = 0.15
SURPLUS_POPULATION_PRESSURE = 90.0
SURPLUS_GROWTH_FACTOR = 0.003
SURPLUS_MAX_GROWTH_BONUS = 0.018
SURPLUS_MIN_GROWTH_PENALTY = -0.012
SETTLEMENT_LEVELS = ("wild", "rural", "town", "city")
POLITY_TIER_ORDER = ("band", "tribe", "chiefdom", "state")
SURPLUS_TERRAIN_PRODUCTIVITY = {
    "plains": 1.6,
    "riverland": 1.8,
    "coast": 0.8,
    "forest": 0.4,
    "hills": 0.2,
    "highland": -0.6,
    "marsh": -0.8,
    "steppe": 1.0,
}
REBEL_CONFLICT_SECESSION = "secession"
REBEL_CONFLICT_CIVIL_WAR = "civil_war"
CIVIL_WAR_AFFINITY_THRESHOLD = 0.65
CIVIL_WAR_CLAIMANT_PRESSURE_THRESHOLD = 0.45
CIVIL_WAR_SUCCESSOR_FORMS = {
    ("band", "leader"): "council",
    ("band", "council"): "leader",
    ("tribe", "leader"): "council",
    ("tribe", "council"): "assembly",
    ("tribe", "assembly"): "leader",
    ("chiefdom", "leader"): "council",
    ("chiefdom", "council"): "monarchy",
    ("chiefdom", "monarchy"): "council",
    ("state", "council"): "monarchy",
    ("state", "assembly"): "monarchy",
    ("state", "monarchy"): "republic",
    ("state", "republic"): "monarchy",
    ("state", "oligarchy"): "republic",
}
CIVIL_WAR_REGIME_LABELS = {
    ("band", "leader"): "Warband",
    ("band", "council"): "Council",
    ("tribe", "leader"): "Chieftaincy",
    ("tribe", "council"): "Council",
    ("tribe", "assembly"): "Assembly",
    ("chiefdom", "leader"): "Chieftaincy",
    ("chiefdom", "council"): "Council",
    ("chiefdom", "monarchy"): "Monarchy",
    ("state", "council"): "Council Realm",
    ("state", "assembly"): "Commonwealth",
    ("state", "monarchy"): "Kingdom",
    ("state", "republic"): "Republic",
    ("state", "oligarchy"): "Oligarchy",
}
DYNASTIC_FORMS = {"leader", "monarchy"}
SUCCESSION_COLLEGIAL_FORMS = {"council", "assembly", "republic", "oligarchy"}
SUCCESSION_POLITY_PROFILE = {
    "band": {
        "legitimacy": -0.12,
        "prestige": -0.16,
        "preparedness": -0.18,
        "claimant": -0.06,
        "ruler_age": (22, 40),
        "heir_age": (10, 20),
        "adult_successor_age": (18, 28),
    },
    "tribe": {
        "legitimacy": -0.06,
        "prestige": -0.08,
        "preparedness": -0.08,
        "claimant": -0.02,
        "ruler_age": (24, 48),
        "heir_age": (8, 22),
        "adult_successor_age": (20, 34),
    },
    "chiefdom": {
        "legitimacy": 0.0,
        "prestige": 0.04,
        "preparedness": 0.03,
        "claimant": 0.03,
        "ruler_age": (26, 58),
        "heir_age": (7, 25),
        "adult_successor_age": (24, 42),
    },
    "state": {
        "legitimacy": 0.08,
        "prestige": 0.1,
        "preparedness": 0.1,
        "claimant": 0.06,
        "ruler_age": (30, 64),
        "heir_age": (6, 28),
        "adult_successor_age": (28, 50),
    },
}
SUCCESSION_FORM_PROFILE = {
    "leader": {
        "legitimacy": -0.04,
        "prestige": 0.03,
        "preparedness": -0.06,
        "claimant": -0.03,
        "adult_successor": False,
        "regency": True,
        "dynasty_rotation": 0.12,
    },
    "council": {
        "legitimacy": 0.02,
        "prestige": -0.03,
        "preparedness": 0.02,
        "claimant": 0.02,
        "adult_successor": True,
        "regency": False,
        "dynasty_rotation": 0.2,
    },
    "assembly": {
        "legitimacy": 0.04,
        "prestige": -0.05,
        "preparedness": 0.05,
        "claimant": 0.04,
        "adult_successor": True,
        "regency": False,
        "dynasty_rotation": 0.28,
    },
    "monarchy": {
        "legitimacy": 0.08,
        "prestige": 0.12,
        "preparedness": 0.08,
        "claimant": 0.06,
        "adult_successor": False,
        "regency": True,
        "dynasty_rotation": 0.04,
    },
    "republic": {
        "legitimacy": 0.06,
        "prestige": -0.02,
        "preparedness": 0.12,
        "claimant": 0.09,
        "adult_successor": True,
        "regency": False,
        "dynasty_rotation": 0.5,
    },
    "oligarchy": {
        "legitimacy": 0.02,
        "prestige": 0.04,
        "preparedness": 0.08,
        "claimant": 0.11,
        "adult_successor": True,
        "regency": False,
        "dynasty_rotation": 0.36,
    },
}
RELIGION_POLITY_PROFILE = {
    "band": {"tolerance": -0.08, "zeal": 0.06, "state_cult": 0.05, "legitimacy": -0.04},
    "tribe": {"tolerance": -0.03, "zeal": 0.03, "state_cult": 0.03, "legitimacy": 0.0},
    "chiefdom": {"tolerance": 0.0, "zeal": 0.02, "state_cult": 0.08, "legitimacy": 0.03},
    "state": {"tolerance": 0.04, "zeal": 0.0, "state_cult": 0.1, "legitimacy": 0.06},
}
RELIGION_FORM_PROFILE = {
    "leader": {"tolerance": -0.08, "zeal": 0.08, "state_cult": 0.08, "legitimacy": 0.02},
    "council": {"tolerance": 0.04, "zeal": -0.02, "state_cult": -0.02, "legitimacy": 0.03},
    "assembly": {"tolerance": 0.08, "zeal": -0.04, "state_cult": -0.04, "legitimacy": 0.04},
    "monarchy": {"tolerance": -0.04, "zeal": 0.05, "state_cult": 0.12, "legitimacy": 0.08},
    "republic": {"tolerance": 0.12, "zeal": -0.05, "state_cult": -0.08, "legitimacy": 0.04},
    "oligarchy": {"tolerance": 0.02, "zeal": 0.0, "state_cult": 0.02, "legitimacy": 0.03},
}
RELIGION_DOCTRINE_BY_TERRAIN = {
    "riverland": "River Rite",
    "coast": "Sea Cult",
    "forest": "Grove Worship",
    "highland": "Sky Rite",
    "hills": "Ancestor Stones",
    "marsh": "Fen Mysteries",
    "steppe": "Horse Heaven",
    "plains": "Sun Rite",
}
POLITY_TIER_RANK = {tier: index for index, tier in enumerate(POLITY_TIER_ORDER)}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _pick_name_fragment(options: list[str], fallback: str) -> str:
    filtered = [option for option in options if option]
    if filtered:
        return random.choice(filtered)
    return fallback


def _pick_lexical_root(
    profile: LanguageProfile,
    concepts: list[str],
    fallback: str,
) -> str:
    lexical_roots = profile.lexical_roots or {}
    options: list[str] = []
    for concept in concepts:
        options.extend(lexical_roots.get(concept, []))
    filtered = [re.sub(r"[^a-z]", "", option.lower()) for option in options if option]
    filtered = [option for option in filtered if option]
    if filtered:
        return random.choice(filtered)
    return fallback


def _merge_language_lexical_roots(
    base_roots: dict[str, list[str]],
    extra_roots: dict[str, list[str]],
    *,
    limit: int = 3,
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for concept in sorted(set(base_roots) | set(extra_roots)):
        seen: set[str] = set()
        ordered: list[str] = []
        for value in list(base_roots.get(concept, [])) + list(extra_roots.get(concept, [])):
            normalized = re.sub(r"[^a-z]", "", (value or "").lower())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
            if len(ordered) >= limit:
                break
        if ordered:
            merged[concept] = ordered
    return merged


def _get_religion_root_concepts(region: Region | None, doctrine: str | None) -> list[str]:
    concepts = ["sacred"]
    doctrine_text = (doctrine or "").lower()
    if "ancestor" in doctrine_text:
        concepts.append("ancestor")
    if "sun" in doctrine_text:
        concepts.append("sun")
    if region is not None:
        if "riverland" in region.terrain_tags:
            concepts.append("river")
        if "forest" in region.terrain_tags:
            concepts.append("forest")
        if "coast" in region.terrain_tags:
            concepts.append("sea")
        if "hills" in region.terrain_tags or "mountains" in region.terrain_tags:
            concepts.append("hill")
    return concepts


def _generate_personal_name(faction: Faction, *, seed: str | None = None) -> str:
    culture_name = (faction.culture_name or faction.name or "Ruler").strip()
    profile = faction.identity.language_profile if faction.identity is not None else LanguageProfile()
    fallback_core = (seed or culture_name or "rul").strip().lower()
    fallback_core = re.sub(r"[^a-z]", "", fallback_core) or "rul"
    lexical_root = _pick_lexical_root(profile, ["ruler", "ancestor"], fallback_core[:3] or "ru")
    onset = _pick_name_fragment(profile.onsets, lexical_root[:2] or fallback_core[:2] or "ru")
    middle = _pick_name_fragment(profile.middles, fallback_core[1:3] or "la")
    suffix = _pick_name_fragment(
        profile.suffixes,
        lexical_root[-2:] or fallback_core[-2:] or "an",
    )
    token = f"{onset}{middle}{suffix}"
    token = re.sub(r"[^a-z]", "", token.lower()) or fallback_core
    return token[:1].upper() + token[1:]


def _generate_dynasty_name(faction: Faction, *, cadet: bool = False) -> str:
    profile = faction.identity.language_profile if faction.identity is not None else LanguageProfile()
    dynasty_seed = _pick_lexical_root(
        profile,
        ["dynasty", "ancestor", "ruler"],
        (faction.culture_name or faction.name or "line").strip().lower(),
    )
    dynasty_root = _generate_personal_name(faction, seed=dynasty_seed)
    prefix = "House" if faction.government_form in DYNASTIC_FORMS else "Line"
    if cadet:
        return f"{prefix} {dynasty_root}cad"
    return f"{prefix} {dynasty_root}"


def _normalize_region_religious_composition(region: Region) -> None:
    if region.population <= 0:
        region.religious_composition = {}
        return
    composition = {
        religion_name: count
        for religion_name, count in region.religious_composition.items()
        if count > 0
    }
    if not composition:
        region.religious_composition = {}
        return
    total = sum(composition.values())
    scaled: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    assigned = 0
    for religion_name, count in composition.items():
        scaled_value = (count / total) * region.population
        whole = int(scaled_value)
        scaled[religion_name] = whole
        assigned += whole
        remainders.append((scaled_value - whole, religion_name))
    for _fraction, religion_name in sorted(remainders, reverse=True)[: max(0, region.population - assigned)]:
        scaled[religion_name] += 1
    region.religious_composition = {
        religion_name: count
        for religion_name, count in scaled.items()
        if count > 0
    }


def seed_region_religion(region: Region, religion_name: str) -> None:
    if region.population <= 0:
        region.religious_composition = {}
        return
    region.religious_composition = {religion_name: region.population}


def get_region_dominant_religion(region: Region) -> str | None:
    if not region.religious_composition:
        return None
    return max(
        region.religious_composition.items(),
        key=lambda item: (item[1], item[0]),
    )[0]


def _pick_religion_doctrine(region: Region) -> str:
    terrain_tags = list(region.terrain_tags or ["plains"])
    for terrain_tag in terrain_tags:
        if terrain_tag in RELIGION_DOCTRINE_BY_TERRAIN:
            return RELIGION_DOCTRINE_BY_TERRAIN[terrain_tag]
    return "Ancestor Rite"


def _generate_religion_name(
    faction: Faction,
    *,
    suffix: str = "rite",
    doctrine: str | None = None,
    region: Region | None = None,
) -> str:
    profile = faction.identity.language_profile if faction.identity is not None else LanguageProfile()
    culture_name = (faction.culture_name or faction.name or "Faith").strip()
    root_seed = _pick_lexical_root(
        profile,
        _get_religion_root_concepts(region, doctrine),
        culture_name.lower(),
    )
    root = _generate_personal_name(faction, seed=root_seed)
    label = f"{root}{suffix}"
    label = re.sub(r"[^A-Za-z]", "", label) or root or "Faith"
    return _to_title_case_root(label)


def register_religion(
    world: WorldState,
    religion_name: str,
    *,
    founding_faction: str | None = None,
    parent_religion: str | None = None,
    doctrine: str = "",
    sacred_terrain_tags: list[str] | None = None,
    sacred_climate: str = "temperate",
    reform_origin_turn: int | None = None,
) -> None:
    world.religions.setdefault(
        religion_name,
        Religion(
            name=religion_name,
            founding_faction=founding_faction,
            parent_religion=parent_religion,
            doctrine=doctrine,
            sacred_terrain_tags=list(sacred_terrain_tags or []),
            sacred_climate=sacred_climate,
            reform_origin_turn=reform_origin_turn,
        ),
    )


def _build_initial_religion_state(faction: Faction) -> FactionReligionState:
    polity_profile = RELIGION_POLITY_PROFILE.get(faction.polity_tier, RELIGION_POLITY_PROFILE["tribe"])
    form_profile = RELIGION_FORM_PROFILE.get(faction.government_form, RELIGION_FORM_PROFILE["council"])
    return FactionReligionState(
        official_religion="",
        religious_legitimacy=round(
            _clamp(
                random.uniform(RELIGION_INITIAL_LEGITIMACY_MIN, RELIGION_INITIAL_LEGITIMACY_MAX)
                + polity_profile["legitimacy"]
                + form_profile["legitimacy"],
                0.2,
                0.95,
            ),
            3,
        ),
        clergy_support=round(
            _clamp(
                random.uniform(RELIGION_INITIAL_CLERGY_SUPPORT_MIN, RELIGION_INITIAL_CLERGY_SUPPORT_MAX)
                + (form_profile["state_cult"] * 0.35),
                0.2,
                0.95,
            ),
            3,
        ),
        religious_tolerance=round(
            _clamp(
                random.uniform(RELIGION_INITIAL_TOLERANCE_MIN, RELIGION_INITIAL_TOLERANCE_MAX)
                + polity_profile["tolerance"]
                + form_profile["tolerance"],
                0.05,
                0.95,
            ),
            3,
        ),
        religious_zeal=round(
            _clamp(
                random.uniform(RELIGION_INITIAL_ZEAL_MIN, RELIGION_INITIAL_ZEAL_MAX)
                + polity_profile["zeal"]
                + form_profile["zeal"],
                0.05,
                0.95,
            ),
            3,
        ),
        state_cult_strength=round(
            _clamp(
                random.uniform(RELIGION_INITIAL_STATE_CULT_MIN, RELIGION_INITIAL_STATE_CULT_MAX)
                + polity_profile["state_cult"]
                + form_profile["state_cult"],
                0.05,
                0.95,
            ),
            3,
        ),
        reform_pressure=0.0,
        sacred_sites_controlled=0,
        total_sacred_sites=0,
        last_reform_turn=None,
    )


def initialize_faction_religion_state(
    world: WorldState,
    faction: Faction,
    *,
    parent_faction: Faction | None = None,
    region: Region | None = None,
    claimant: bool = False,
) -> None:
    existing_official = faction.religion.official_religion
    faction.religion = _build_initial_religion_state(faction)
    if existing_official and existing_official in world.religions:
        official_religion = existing_official
    elif parent_faction is not None and parent_faction.religion.official_religion:
        official_religion = parent_faction.religion.official_religion
    else:
        doctrine = _pick_religion_doctrine(region) if region is not None else "Ancestor Rite"
        official_religion = _generate_religion_name(
            faction,
            doctrine=doctrine,
            region=region,
        )
        while official_religion in world.religions:
            official_religion = f"{official_religion}a"
        register_religion(
            world,
            official_religion,
            founding_faction=faction.name,
            doctrine=doctrine,
            sacred_terrain_tags=list(region.terrain_tags or []) if region is not None else [],
            sacred_climate=region.climate if region is not None else "temperate",
        )
    faction.religion.official_religion = official_religion
    if claimant:
        faction.religion.religious_legitimacy = round(
            _clamp(faction.religion.religious_legitimacy - 0.06, 0.2, 0.95),
            3,
        )
        faction.religion.reform_pressure = 0.08


def initialize_religious_legitimacy(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        homeland_region_name = faction.doctrine_state.homeland_region
        homeland_region = world.regions.get(homeland_region_name) if homeland_region_name else None
        initialize_faction_religion_state(world, faction, region=homeland_region)
        if homeland_region is not None:
            seed_region_religion(homeland_region, faction.religion.official_religion)
            homeland_region.sacred_religion = faction.religion.official_religion
            homeland_region.shrine_level = max(homeland_region.shrine_level, RELIGION_SACRED_SITE_HOME_SHRINE)
        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            if not region.religious_composition:
                seed_region_religion(region, faction.religion.official_religion)


def evolve_faction_religion_politics(
    faction: Faction,
    *,
    previous_tier: str | None = None,
    previous_form: str | None = None,
) -> None:
    previous_tier = previous_tier or faction.polity_tier
    previous_form = previous_form or faction.government_form
    tier_rank = POLITY_TIER_RANK.get(faction.polity_tier, POLITY_TIER_RANK["tribe"])
    previous_rank = POLITY_TIER_RANK.get(previous_tier, POLITY_TIER_RANK["tribe"])
    tier_gain = max(0, tier_rank - previous_rank)
    polity_profile = RELIGION_POLITY_PROFILE.get(faction.polity_tier, RELIGION_POLITY_PROFILE["tribe"])
    form_profile = RELIGION_FORM_PROFILE.get(faction.government_form, RELIGION_FORM_PROFILE["council"])
    religion_state = faction.religion
    religion_state.religious_tolerance = round(
        _clamp(
            max(religion_state.religious_tolerance, 0.18 + (tier_rank * 0.09))
            + (polity_profile["tolerance"] * 0.25)
            + (form_profile["tolerance"] * 0.35),
            0.05,
            0.95,
        ),
        3,
    )
    religion_state.state_cult_strength = round(
        _clamp(
            religion_state.state_cult_strength
            + (0.03 * tier_gain)
            + (polity_profile["state_cult"] * 0.22)
            + (form_profile["state_cult"] * 0.26),
            0.05,
            0.95,
        ),
        3,
    )
    religion_state.religious_zeal = round(
        _clamp(
            religion_state.religious_zeal
            + (polity_profile["zeal"] * 0.2)
            + (form_profile["zeal"] * 0.25),
            0.05,
            0.95,
        ),
        3,
    )
    religion_state.clergy_support = round(
        _clamp(
            religion_state.clergy_support
            + (0.02 * tier_gain)
            + (religion_state.state_cult_strength * 0.05),
            0.05,
            0.95,
        ),
        3,
    )
    if previous_form != faction.government_form and faction.government_form == "republic":
        religion_state.religious_tolerance = round(_clamp(religion_state.religious_tolerance + 0.08, 0.05, 0.95), 3)
        religion_state.state_cult_strength = round(_clamp(religion_state.state_cult_strength - 0.08, 0.05, 0.95), 3)


def _get_region_religious_alignment(region: Region, official_religion: str) -> float:
    if region.population <= 0 or not official_religion:
        return 0.0
    return _clamp(
        region.religious_composition.get(official_religion, 0) / max(1, region.population),
        0.0,
        1.0,
    )


def _iter_regions_sacred_to_religion(world: WorldState, religion_name: str) -> list[Region]:
    return [
        region
        for region in world.regions.values()
        if region.sacred_religion == religion_name
    ]


def _maybe_reform_state_religion(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    religion_state = faction.religion
    if POLITY_TIER_RANK.get(faction.polity_tier, 0) < POLITY_TIER_RANK.get(RELIGION_REFORM_STATE_MIN_TIER, 3):
        return
    if religion_state.reform_pressure < RELIGION_REFORM_THRESHOLD:
        return
    if religion_state.last_reform_turn is not None and (world.turn - religion_state.last_reform_turn) < RELIGION_REFORM_MIN_INTERVAL:
        return
    old_religion = religion_state.official_religion
    if not old_religion:
        return
    homeland_region_name = faction.doctrine_state.homeland_region
    homeland_region = world.regions.get(homeland_region_name) if homeland_region_name else None
    reform_doctrine = f"Reformed {_pick_religion_doctrine(homeland_region) if homeland_region is not None else 'Rite'}"
    new_religion = _generate_religion_name(
        faction,
        suffix="an",
        doctrine=reform_doctrine,
        region=homeland_region,
    )
    while new_religion in world.religions:
        new_religion = f"{new_religion}a"
    register_religion(
        world,
        new_religion,
        founding_faction=faction_name,
        parent_religion=old_religion,
        doctrine=reform_doctrine,
        sacred_terrain_tags=list(homeland_region.terrain_tags or []) if homeland_region is not None else [],
        sacred_climate=homeland_region.climate if homeland_region is not None else "temperate",
        reform_origin_turn=world.turn,
    )
    religion_state.official_religion = new_religion
    religion_state.last_reform_turn = world.turn
    religion_state.reform_pressure = round(_clamp(religion_state.reform_pressure * 0.45, 0.0, 1.0), 3)
    religion_state.religious_legitimacy = round(_clamp(religion_state.religious_legitimacy - 0.08, 0.15, 0.95), 3)
    religion_state.clergy_support = round(_clamp(religion_state.clergy_support - 0.05, 0.1, 0.95), 3)
    owned_regions = _get_faction_owned_regions(world, faction_name)
    for region in owned_regions:
        old_count = region.religious_composition.get(old_religion, 0)
        if old_count <= 0:
            continue
        convert_count = max(1, int(round(old_count * (0.24 + (region.shrine_level * 0.08)))))
        convert_count = min(convert_count, old_count)
        region.religious_composition[old_religion] = max(0, old_count - convert_count)
        if region.religious_composition[old_religion] <= 0:
            region.religious_composition.pop(old_religion, None)
        region.religious_composition[new_religion] = region.religious_composition.get(new_religion, 0) + convert_count
        if region.name == homeland_region_name:
            region.sacred_religion = new_religion
        _normalize_region_religious_composition(region)
    world.events.append(Event(
        turn=world.turn,
        type="religious_reform",
        faction=faction_name,
        region=homeland_region_name,
        details={
            "old_religion": old_religion,
            "new_religion": new_religion,
            "parent_religion": old_religion,
        },
        tags=["religion", "reform", "legitimacy"],
        significance=float(religion_state.religious_legitimacy or 0.0),
    ))


def update_religious_legitimacy(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        official_religion = faction.religion.official_religion
        if not official_religion:
            homeland_region_name = faction.doctrine_state.homeland_region
            homeland_region = world.regions.get(homeland_region_name) if homeland_region_name else None
            initialize_faction_religion_state(world, faction, region=homeland_region)
            official_religion = faction.religion.official_religion
        owned_regions = _get_faction_owned_regions(world, faction_name)
        if not owned_regions:
            continue
        controlled_population = sum(region.population for region in owned_regions)
        aligned_population = sum(
            region.religious_composition.get(official_religion, 0)
            for region in owned_regions
        )
        unity = aligned_population / max(1, controlled_population)
        sacred_sites = _iter_regions_sacred_to_religion(world, official_religion)
        sacred_controlled = sum(1 for region in sacred_sites if region.owner == faction_name)
        faction.religion.sacred_sites_controlled = sacred_controlled
        faction.religion.total_sacred_sites = len(sacred_sites)
        sacred_ratio = sacred_controlled / max(1, len(sacred_sites))
        pilgrimage_income = 0.0
        for region in owned_regions:
            alignment = _get_region_religious_alignment(region, official_religion)
            mismatch = max(0.0, 1.0 - alignment - faction.religion.religious_tolerance)
            region.religious_unrest = round(mismatch * RELIGION_DISSENT_UNREST_FACTOR, 3)
            region.pilgrimage_value = 0.0
            if region.population > 0 and alignment < 0.96 and official_religion:
                convert_ratio = (
                    RELIGION_CONVERSION_BASE
                    + (region.shrine_level * RELIGION_CONVERSION_SHRINE_FACTOR)
                    + (max(0.0, region.integration_score) * RELIGION_CONVERSION_INTEGRATION_FACTOR / 10.0)
                    + (faction.religion.state_cult_strength * 0.03)
                )
                if faction.government_form == "republic":
                    convert_ratio *= 0.7
                convert_count = min(
                    max(0, region.population - region.religious_composition.get(official_religion, 0)),
                    int(round(region.population * max(0.0, convert_ratio))),
                )
                if convert_count > 0:
                    dominant_religion = get_region_dominant_religion(region)
                    if dominant_religion is not None and dominant_religion != official_religion:
                        region.religious_composition[dominant_religion] = max(
                            0,
                            region.religious_composition.get(dominant_religion, 0) - convert_count,
                        )
                        if region.religious_composition.get(dominant_religion, 0) <= 0:
                            region.religious_composition.pop(dominant_religion, None)
                    region.religious_composition[official_religion] = (
                        region.religious_composition.get(official_religion, 0) + convert_count
                    )
                    _normalize_region_religious_composition(region)
            if region.sacred_religion == official_religion:
                region.pilgrimage_value = round(region.shrine_level * RELIGION_PILGRIMAGE_PER_SHRINE, 3)
                pilgrimage_income += region.pilgrimage_value
        faction.religion.religious_legitimacy = round(
            _clamp(
                (unity * RELIGION_UNITY_LEGITIMACY_FACTOR)
                + (faction.religion.clergy_support * RELIGION_CLERGY_LEGITIMACY_FACTOR)
                + (sacred_ratio * RELIGION_SACRED_SITE_BONUS)
                + (faction.religion.state_cult_strength * 0.06)
                + (faction.religion.religious_zeal * 0.04)
                + 0.34,
                0.15,
                0.95,
            ),
            3,
        )
        faction.religion.clergy_support = round(
            _clamp(
                faction.religion.clergy_support
                + ((sacred_ratio - 0.5) * 0.05)
                - (max(0.0, 0.6 - unity) * 0.04),
                0.1,
                0.95,
            ),
            3,
        )
        faction.religion.reform_pressure = round(
            _clamp(
                faction.religion.reform_pressure
                + (max(0.0, 0.72 - unity) * RELIGION_REFORM_PRESSURE_FACTOR)
                + (max(0.0, 0.52 - faction.succession.legitimacy) * 0.12)
                - (faction.religion.religious_tolerance * 0.04),
                0.0,
                1.0,
            ),
            3,
        )
        faction.trade_income = round(faction.trade_income + pilgrimage_income, 3)
        _maybe_reform_state_religion(world, faction_name)
def _get_faction_regions(world: WorldState, faction_name: str) -> list[Region]:
    return [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]


def _get_succession_polity_profile(faction: Faction) -> dict[str, object]:
    return SUCCESSION_POLITY_PROFILE.get(
        faction.polity_tier,
        SUCCESSION_POLITY_PROFILE["tribe"],
    )


def _get_succession_form_profile(faction: Faction) -> dict[str, object]:
    return SUCCESSION_FORM_PROFILE.get(
        faction.government_form,
        SUCCESSION_FORM_PROFILE["council"],
    )


def _get_successor_age_range(faction: Faction, *, adult: bool = False) -> tuple[int, int]:
    polity_profile = _get_succession_polity_profile(faction)
    if adult or bool(_get_succession_form_profile(faction).get("adult_successor")):
        return polity_profile["adult_successor_age"]  # type: ignore[return-value]
    return polity_profile["heir_age"]  # type: ignore[return-value]


def _can_have_regency(faction: Faction) -> bool:
    return bool(_get_succession_form_profile(faction).get("regency"))


def _get_dynasty_rotation_chance(faction: Faction, claimant_pressure: float = 0.0) -> float:
    base = float(_get_succession_form_profile(faction).get("dynasty_rotation", 0.2))
    if faction.government_form == "republic":
        base += claimant_pressure * 0.18
    elif faction.government_form in {"assembly", "council", "oligarchy"}:
        base += claimant_pressure * 0.08
    return _clamp(base, 0.0, 0.9)


def evolve_faction_succession_politics(
    faction: Faction,
    *,
    previous_tier: str | None = None,
    previous_form: str | None = None,
) -> None:
    succession = faction.succession
    polity_profile = _get_succession_polity_profile(faction)
    form_profile = _get_succession_form_profile(faction)
    previous_tier = previous_tier or faction.polity_tier
    previous_form = previous_form or faction.government_form
    tier_gain = max(
        0,
        POLITY_TIER_ORDER.index(faction.polity_tier) - POLITY_TIER_ORDER.index(previous_tier),
    )
    tier_rank = max(0, POLITY_TIER_ORDER.index(faction.polity_tier))
    legitimacy_floor = 0.3 + (tier_rank * 0.07)
    preparedness_floor = 0.24 + (tier_rank * 0.08)
    prestige_floor = 0.18 + (tier_rank * 0.06)
    succession.legitimacy = round(
        _clamp(
            max(
                float(succession.legitimacy or 0.0),
                legitimacy_floor + float(polity_profile["legitimacy"]) * 0.35 + float(form_profile["legitimacy"]) * 0.25,
            )
            + (0.03 * tier_gain),
            0.15,
            0.95,
        ),
        3,
    )
    succession.heir_preparedness = round(
        _clamp(
            max(
                float(succession.heir_preparedness or 0.0),
                preparedness_floor + float(polity_profile["preparedness"]) * 0.4 + float(form_profile["preparedness"]) * 0.35,
            )
            + (0.04 * tier_gain),
            0.18,
            0.95,
        ),
        3,
    )
    succession.dynasty_prestige = round(
        _clamp(
            max(
                float(succession.dynasty_prestige or 0.0),
                prestige_floor + float(polity_profile["prestige"]) * 0.35 + float(form_profile["prestige"]) * 0.35,
            )
            + (0.03 * tier_gain),
            0.18,
            0.95,
        ),
        3,
    )
    claimant_adjustment = -0.03 * tier_gain
    if faction.government_form == "republic":
        claimant_adjustment += 0.03
    elif faction.government_form == "monarchy":
        claimant_adjustment += 0.01
    succession.claimant_pressure = round(
        _clamp(
            float(succession.claimant_pressure or 0.0)
            + claimant_adjustment
            + float(polity_profile["claimant"]) * 0.15
            + float(form_profile["claimant"]) * 0.1,
            0.0,
            1.0,
        ),
        3,
    )
    if bool(form_profile.get("adult_successor")) and succession.heir_age < 18:
        adult_min, adult_max = _get_successor_age_range(faction, adult=True)
        succession.heir_age = max(18, random.randint(adult_min, adult_max))
    if not succession.heir_name:
        succession.heir_name = _generate_personal_name(faction, seed=succession.ruler_name)
    if faction.government_form in DYNASTIC_FORMS and succession.dynasty_name.startswith("Line "):
        succession.dynasty_name = succession.dynasty_name.replace("Line ", "House ", 1)
    elif faction.government_form not in DYNASTIC_FORMS and succession.dynasty_name.startswith("House "):
        succession.dynasty_name = succession.dynasty_name.replace("House ", "Line ", 1)
    if previous_form != faction.government_form and faction.government_form == "republic":
        succession.heir_age = max(succession.heir_age, random.randint(24, 42))
        succession.heir_preparedness = round(_clamp(succession.heir_preparedness + 0.08, 0.18, 0.95), 3)


def _build_initial_succession_state(
    faction: Faction,
    *,
    dynasty_name: str | None = None,
    heir_name: str | None = None,
    claimant: bool = False,
) -> FactionSuccessionState:
    polity_profile = _get_succession_polity_profile(faction)
    form_profile = _get_succession_form_profile(faction)
    ruler_name = _generate_personal_name(faction)
    heir_label = heir_name if heir_name is not None else _generate_personal_name(faction, seed=ruler_name)
    heir_min, heir_max = _get_successor_age_range(
        faction,
        adult=bool(form_profile.get("adult_successor")),
    )
    heir_age = random.randint(heir_min, heir_max)
    legitimacy = random.uniform(
        SUCCESSION_INITIAL_LEGITIMACY_MIN,
        SUCCESSION_INITIAL_LEGITIMACY_MAX,
    ) + float(polity_profile["legitimacy"]) + float(form_profile["legitimacy"])
    prestige = random.uniform(
        SUCCESSION_INITIAL_PRESTIGE_MIN,
        SUCCESSION_INITIAL_PRESTIGE_MAX,
    ) + float(polity_profile["prestige"]) + float(form_profile["prestige"])
    preparedness = random.uniform(
        SUCCESSION_INITIAL_HEIR_PREPAREDNESS_MIN,
        SUCCESSION_INITIAL_HEIR_PREPAREDNESS_MAX,
    ) + float(polity_profile["preparedness"]) + float(form_profile["preparedness"])
    if claimant:
        legitimacy -= 0.08
        preparedness += 0.06
        prestige -= 0.03
    ruler_age_min, ruler_age_max = polity_profile["ruler_age"]  # type: ignore[misc]
    return FactionSuccessionState(
        dynasty_name=dynasty_name or _generate_dynasty_name(faction),
        ruler_name=ruler_name,
        ruler_age=random.randint(ruler_age_min, ruler_age_max),
        ruler_reign_turns=0,
        heir_name=heir_label,
        heir_age=heir_age,
        heir_preparedness=round(_clamp(preparedness, 0.2, 0.95), 3),
        legitimacy=round(_clamp(legitimacy, 0.25, 0.95), 3),
        dynasty_prestige=round(_clamp(prestige, 0.2, 0.95), 3),
        regency_turns=0,
        succession_crisis_turns=0,
        claimant_pressure=round(
            _clamp(
                (0.16 if claimant else 0.0)
                + float(polity_profile["claimant"])
                + float(form_profile["claimant"]),
                0.0,
                1.0,
            ),
            3,
        ),
        last_succession_turn=None,
        last_succession_type="founding",
    )


def initialize_faction_succession_state(
    faction: Faction,
    *,
    parent_faction: Faction | None = None,
    claimant: bool = False,
) -> None:
    dynasty_name = None
    if claimant and parent_faction is not None and parent_faction.succession.dynasty_name:
        dynasty_name = parent_faction.succession.dynasty_name
    elif parent_faction is not None and parent_faction.succession.dynasty_name:
        dynasty_name = _generate_dynasty_name(faction, cadet=True)
    faction.succession = _build_initial_succession_state(
        faction,
        dynasty_name=dynasty_name,
        claimant=claimant,
    )
    evolve_faction_succession_politics(faction)


def initialize_dynastic_politics(world: WorldState) -> None:
    for faction in world.factions.values():
        initialize_faction_succession_state(faction)


def _get_faction_owned_regions(world: WorldState, faction_name: str) -> list[Region]:
    return [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]


def _choose_succession_claimant_region(world: WorldState, faction_name: str) -> Region | None:
    faction = world.factions[faction_name]
    candidates = [
        region
        for region in _get_faction_owned_regions(world, faction_name)
        if (
            region.population >= SUCCESSION_CLAIMANT_REGION_MIN_POPULATION
            and get_region_dominant_ethnicity(region) == faction.primary_ethnicity
            and region.core_status in {"core", "homeland"}
        )
    ]
    if not candidates:
        return None
    ordered = sorted(
        candidates,
        key=lambda region: (
            0 if region.core_status == "core" else 1,
            -region.unrest,
            -region.population,
            region.name,
        ),
    )
    return ordered[0]


def _inherit_successor_heir(faction: Faction) -> tuple[str, int, float]:
    succession = faction.succession
    if succession.heir_name:
        if bool(_get_succession_form_profile(faction).get("adult_successor")) and succession.heir_age < 18:
            adult_min, adult_max = _get_successor_age_range(faction, adult=True)
            return (
                succession.heir_name,
                random.randint(adult_min, adult_max),
                max(0.32, float(succession.heir_preparedness or 0.0)),
            )
        return (
            succession.heir_name,
            max(0, succession.heir_age),
            max(0.18, float(succession.heir_preparedness or 0.0)),
        )
    heir_min, heir_max = _get_successor_age_range(faction)
    return (
        _generate_personal_name(faction, seed=faction.succession.ruler_name),
        random.randint(heir_min, heir_max),
        random.uniform(0.32, 0.78),
    )


def _normalize_region_ethnic_composition(region: Region) -> None:
    if region.population <= 0:
        region.ethnic_composition = {}
        return
    composition = {
        ethnicity: count
        for ethnicity, count in region.ethnic_composition.items()
        if count > 0
    }
    if not composition:
        region.ethnic_composition = {}
        return
    total = sum(composition.values())
    scaled: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    assigned = 0
    for ethnicity, count in composition.items():
        scaled_value = (count / total) * region.population
        whole = int(scaled_value)
        scaled[ethnicity] = whole
        assigned += whole
        remainders.append((scaled_value - whole, ethnicity))
    for _fraction, ethnicity in sorted(remainders, reverse=True)[: max(0, region.population - assigned)]:
        scaled[ethnicity] += 1
    region.ethnic_composition = {
        ethnicity: count
        for ethnicity, count in scaled.items()
        if count > 0
    }


def register_ethnicity(
    world: WorldState,
    ethnicity_name: str,
    *,
    language_family: str = "",
    parent_ethnicity: str | None = None,
    origin_faction: str | None = None,
    language_profile: LanguageProfile | None = None,
) -> None:
    world.ethnicities.setdefault(
        ethnicity_name,
        Ethnicity(
            name=ethnicity_name,
            language_family=language_family or ethnicity_name,
            parent_ethnicity=parent_ethnicity,
            origin_faction=origin_faction,
            language_profile=deepcopy(language_profile) if language_profile is not None else LanguageProfile(family_name=language_family or ethnicity_name),
        ),
    )


def seed_region_ethnicity(region: Region, ethnicity_name: str) -> None:
    if region.population <= 0:
        region.ethnic_composition = {}
        return
    region.ethnic_composition = {ethnicity_name: region.population}


def get_region_dominant_ethnicity(region: Region) -> str | None:
    if not region.ethnic_composition:
        return None
    return max(
        region.ethnic_composition.items(),
        key=lambda item: (item[1], item[0]),
    )[0]


def get_region_owner_primary_ethnicity(region: Region, world: WorldState) -> str | None:
    if region.owner is None or region.owner not in world.factions:
        return None
    return world.factions[region.owner].primary_ethnicity


def get_region_ruling_ethnic_affinity(
    region: Region,
    world: WorldState,
    faction_name: str | None = None,
) -> float:
    if region.population <= 0:
        return 0.0

    faction_name = faction_name or region.owner
    if faction_name is None or faction_name not in world.factions:
        return 0.0

    primary_ethnicity = world.factions[faction_name].primary_ethnicity
    if not primary_ethnicity:
        return 0.0

    return _clamp(
        region.ethnic_composition.get(primary_ethnicity, 0) / max(1, region.population),
        0.0,
        1.0,
    )


def faction_has_ethnic_claim(
    world: WorldState,
    region: Region,
    faction_name: str | None,
) -> bool:
    if faction_name is None or faction_name not in world.factions:
        return False
    dominant_ethnicity = get_region_dominant_ethnicity(region)
    if dominant_ethnicity is None:
        return False
    return world.factions[faction_name].primary_ethnicity == dominant_ethnicity


def get_region_ethnic_claimants(region: Region, world: WorldState) -> list[str]:
    dominant_ethnicity = get_region_dominant_ethnicity(region)
    if dominant_ethnicity is None:
        return []
    return sorted(
        [
            faction_name
            for faction_name, faction in world.factions.items()
            if faction.primary_ethnicity == dominant_ethnicity
        ],
    )


def get_faction_ethnic_claims(world: WorldState, faction_name: str) -> list[str]:
    if faction_name not in world.factions:
        return []
    return sorted(
        [
            region.name
            for region in world.regions.values()
            if faction_has_ethnic_claim(world, region, faction_name)
        ],
    )


def factions_have_same_ethnicity_regime_tension(
    world: WorldState,
    faction_a_name: str | None,
    faction_b_name: str | None,
) -> bool:
    if (
        faction_a_name is None
        or faction_b_name is None
        or faction_a_name == faction_b_name
        or faction_a_name not in world.factions
        or faction_b_name not in world.factions
    ):
        return False

    faction_a = world.factions[faction_a_name]
    faction_b = world.factions[faction_b_name]
    if (
        faction_a.primary_ethnicity is None
        or faction_b.primary_ethnicity is None
        or faction_a.primary_ethnicity != faction_b.primary_ethnicity
    ):
        return False

    return (
        faction_a.government_form != faction_b.government_form
        or (faction_a.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR and faction_a.origin_faction == faction_b_name)
        or (faction_b.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR and faction_b.origin_faction == faction_a_name)
    )


def get_same_ethnicity_regime_rivals(world: WorldState, faction_name: str | None) -> list[str]:
    if faction_name is None or faction_name not in world.factions:
        return []

    owned_region_counts = get_owned_region_counts(world)
    return sorted(
        [
            other_name
            for other_name in world.factions
            if other_name != faction_name
            and owned_region_counts.get(other_name, 0) > 0
            and factions_have_same_ethnicity_regime_tension(world, faction_name, other_name)
        ]
    )


def get_region_regime_contestation_unrest_modifier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions or region.population <= 0:
        return 0.0

    owner = world.factions[region.owner]
    if owner.primary_ethnicity is None:
        return 0.0
    if get_region_dominant_ethnicity(region) != owner.primary_ethnicity:
        return 0.0
    if get_region_ruling_ethnic_affinity(region, world) < 0.6:
        return 0.0

    rivals = get_same_ethnicity_regime_rivals(world, region.owner)
    if not rivals:
        return 0.0

    modifier = REGIME_CONTESTATION_UNREST_BASE
    status = get_region_core_status(region)
    if status == "homeland":
        modifier += REGIME_CONTESTATION_HOMELAND_UNREST_BONUS
    elif status == "core":
        modifier += REGIME_CONTESTATION_CORE_UNREST_BONUS
    return modifier


def get_region_external_regime_agitators(region: Region, world: WorldState) -> list[str]:
    if region.owner is None or region.owner not in world.factions or region.population <= 0:
        return []

    owner = world.factions[region.owner]
    if owner.primary_ethnicity is None:
        return []
    if get_region_dominant_ethnicity(region) != owner.primary_ethnicity:
        return []
    if get_region_ruling_ethnic_affinity(region, world) < 0.5:
        return []

    agitators: set[str] = set()
    for neighbor_name in region.neighbors:
        neighbor_owner = world.regions[neighbor_name].owner
        if neighbor_owner is None or neighbor_owner == region.owner:
            continue
        if factions_have_same_ethnicity_regime_tension(world, region.owner, neighbor_owner):
            agitators.add(neighbor_owner)
    return sorted(agitators)


def get_regime_agitation_sponsor_factor(
    world: WorldState,
    sponsor_name: str,
) -> float:
    sponsor = world.factions.get(sponsor_name)
    if sponsor is None:
        return 1.0

    treasury_bonus = min(
        REGIME_AGITATION_TREASURY_MAX_BONUS,
        sponsor.treasury * REGIME_AGITATION_TREASURY_FACTOR,
    )
    war_bias = (sponsor.doctrine_profile.war_posture - 0.5) * REGIME_AGITATION_WAR_POSTURE_FACTOR
    insularity_bias = (0.5 - sponsor.doctrine_profile.insularity) * REGIME_AGITATION_INSULARITY_FACTOR
    return _clamp(
        1.0 + treasury_bonus + war_bias + insularity_bias,
        REGIME_AGITATION_MIN_SPONSOR_FACTOR,
        REGIME_AGITATION_MAX_SPONSOR_FACTOR,
    )


def get_regime_agitation_government_bias(
    world: WorldState,
    sponsor_name: str,
) -> float:
    sponsor = world.factions.get(sponsor_name)
    if sponsor is None:
        return 0.0
    return REGIME_AGITATION_GOVERNMENT_FORM_BIAS.get(sponsor.government_form, 0.0)


def get_regime_agitation_sponsor_mode(
    world: WorldState,
    sponsor_name: str,
    *,
    owner_name: str | None = None,
) -> str:
    from src.diplomacy import get_relationship_state

    sponsor_factor = get_regime_agitation_sponsor_factor(world, sponsor_name)
    sponsor = world.factions.get(sponsor_name)
    effective_factor = sponsor_factor + get_regime_agitation_government_bias(
        world,
        sponsor_name,
    )
    is_claimant = (
        sponsor is not None
        and owner_name is not None
        and sponsor.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR
        and not sponsor.proto_state
        and sponsor.origin_faction == owner_name
    )
    if sponsor is not None and owner_name is not None:
        relationship = get_relationship_state(world, sponsor_name, owner_name)
        if (
            sponsor.government_form in REGIME_AGITATION_DIPLOMATIC_FORMS
            and relationship.status != "rival"
            and relationship.score > DIPLOMACY_RIVAL_THRESHOLD
        ):
            return "none"
    if (
        is_claimant
        and effective_factor >= 1.05
    ):
        return "heavy"
    if effective_factor >= REGIME_AGITATION_HEAVY_MODE_THRESHOLD:
        return "heavy"
    if is_claimant and effective_factor >= REGIME_AGITATION_LOW_MODE_THRESHOLD:
        return "standard"
    if effective_factor <= REGIME_AGITATION_LOW_MODE_THRESHOLD:
        return "low"
    return "standard"


def get_regime_agitation_mode_multipliers(mode: str) -> dict[str, float]:
    if mode == "none":
        return {
            "pressure": 0.0,
            "cost": 0.0,
            "backlash": 0.0,
        }
    if mode == "heavy":
        return {
            "pressure": REGIME_AGITATION_HEAVY_PRESSURE_MULTIPLIER,
            "cost": REGIME_AGITATION_HEAVY_COST_MULTIPLIER,
            "backlash": REGIME_AGITATION_HEAVY_BACKLASH_MULTIPLIER,
        }
    if mode == "low":
        return {
            "pressure": REGIME_AGITATION_LOW_PRESSURE_MULTIPLIER,
            "cost": REGIME_AGITATION_LOW_COST_MULTIPLIER,
            "backlash": REGIME_AGITATION_LOW_BACKLASH_MULTIPLIER,
        }
    return {
        "pressure": 1.0,
        "cost": 1.0,
        "backlash": 1.0,
    }


def get_region_external_regime_agitation_breakdown(
    region: Region,
    world: WorldState,
) -> dict[str, dict[str, float | str]]:
    agitators = get_region_external_regime_agitators(region, world)
    if not agitators:
        return {}

    owner_name = region.owner
    contributions: dict[str, dict[str, float | str]] = {}
    for agitator_name in agitators:
        mode = get_regime_agitation_sponsor_mode(
            world,
            agitator_name,
            owner_name=owner_name,
        )
        agitator = world.factions.get(agitator_name)
        is_claimant = (
            agitator is not None
            and owner_name is not None
            and agitator.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR
            and not agitator.proto_state
            and agitator.origin_faction == owner_name
        )
        if mode == "none" and is_claimant:
            mode = "standard"
        if mode == "none":
            continue
        mode_multipliers = get_regime_agitation_mode_multipliers(mode)
        sponsor_factor = get_regime_agitation_sponsor_factor(world, agitator_name)
        base_contribution = REGIME_AGITATION_UNREST_PER_SPONSOR * sponsor_factor
        claimant_bonus = 0.0
        if is_claimant:
            claimant_bonus = REGIME_AGITATION_CLAIMANT_BONUS
        contribution = (base_contribution + claimant_bonus) * mode_multipliers["pressure"]
        contributions[agitator_name] = {
            "pressure": round(contribution, 4),
            "mode": mode,
            "sponsor_factor": round(sponsor_factor, 3),
            "cost_multiplier": mode_multipliers["cost"],
            "backlash_multiplier": mode_multipliers["backlash"],
        }
    return contributions


def get_region_external_regime_agitation_modifier(region: Region, world: WorldState) -> float:
    contributions = get_region_external_regime_agitation_breakdown(region, world)
    if not contributions:
        return 0.0
    return min(
        REGIME_AGITATION_MAX,
        sum(float(details["pressure"]) for details in contributions.values()),
    )


def _choose_regime_agitation_backlash_region(
    world: WorldState,
    sponsor_name: str,
) -> Region | None:
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == sponsor_name
    ]
    if not owned_regions:
        return None

    homeland_regions = [
        region
        for region in owned_regions
        if get_region_core_status(region) == "homeland"
    ]
    if homeland_regions:
        return max(
            homeland_regions,
            key=lambda region: (
                region.integration_score,
                get_region_taxable_value(region, world),
                region.name,
            ),
        )

    core_regions = [
        region
        for region in owned_regions
        if get_region_core_status(region) == "core"
    ]
    if core_regions:
        return max(
            core_regions,
            key=lambda region: (
                region.integration_score,
                get_region_taxable_value(region, world),
                region.name,
            ),
        )

    return max(
        owned_regions,
        key=lambda region: (
            region.integration_score,
            get_region_taxable_value(region, world),
            region.name,
        ),
    )


def _dedupe_language_values(values: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = (value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
        if len(ordered) >= limit:
            break
    return ordered


def _profile_contact_markers(profile: LanguageProfile) -> set[str]:
    markers: set[str] = set()
    for note in profile.style_notes or []:
        if note.startswith("borrowed from "):
            markers.add(note.removeprefix("borrowed from ").strip())
    return markers


def _add_contact_borrowing(
    receiver_profile: LanguageProfile,
    donor_profile: LanguageProfile,
    *,
    donor_label: str,
    seed_text: str,
    intensity: float,
) -> bool:
    if donor_profile.family_name and donor_profile.family_name == receiver_profile.family_name:
        return False
    if donor_label in _profile_contact_markers(receiver_profile):
        return False

    donor_fragments = donor_profile.seed_fragments or _extract_name_fragments(donor_profile.family_name)
    donor_onsets = donor_profile.onsets or donor_fragments
    donor_middles = donor_profile.middles or ["a", "e", "i"]
    donor_suffixes = donor_profile.suffixes or donor_fragments
    if not donor_onsets and not donor_suffixes and not donor_fragments:
        return False

    rng = random.Random(seed_text)
    borrowed_onsets = []
    borrowed_middles = []
    borrowed_suffixes = []
    borrowed_fragments = []
    borrowed_lexical_roots: dict[str, list[str]] = {}
    borrow_count = 2 if intensity >= 2.0 else 1

    for _ in range(borrow_count):
        if donor_onsets:
            borrowed_onsets.append(rng.choice(donor_onsets))
        if donor_middles:
            borrowed_middles.append(rng.choice(donor_middles))
        if donor_suffixes:
            borrowed_suffixes.append(rng.choice(donor_suffixes))
        if donor_fragments:
            borrowed_fragments.append(rng.choice(donor_fragments))
    donor_lexical_roots = donor_profile.lexical_roots or {}
    lexical_concepts = sorted(donor_lexical_roots)
    for _ in range(borrow_count):
        if not lexical_concepts:
            break
        concept = rng.choice(lexical_concepts)
        concept_roots = donor_lexical_roots.get(concept, [])
        if not concept_roots:
            continue
        borrowed_lexical_roots.setdefault(concept, []).append(rng.choice(concept_roots))

    next_onsets = _dedupe_language_values(receiver_profile.onsets + borrowed_onsets + receiver_profile.onsets, limit=12)
    next_middles = _dedupe_language_values(receiver_profile.middles + borrowed_middles + receiver_profile.middles, limit=12)
    next_suffixes = _dedupe_language_values(receiver_profile.suffixes + borrowed_suffixes + receiver_profile.suffixes, limit=12)
    next_fragments = _dedupe_language_values(receiver_profile.seed_fragments + borrowed_fragments + receiver_profile.seed_fragments, limit=16)
    next_lexical_roots = _merge_language_lexical_roots(
        receiver_profile.lexical_roots or {},
        borrowed_lexical_roots,
        limit=3,
    )

    changed = (
        next_onsets != list(receiver_profile.onsets)
        or next_middles != list(receiver_profile.middles)
        or next_suffixes != list(receiver_profile.suffixes)
        or next_fragments != list(receiver_profile.seed_fragments)
        or next_lexical_roots != dict(receiver_profile.lexical_roots or {})
    )
    if not changed:
        return False

    receiver_profile.onsets = next_onsets
    receiver_profile.middles = next_middles
    receiver_profile.suffixes = next_suffixes
    receiver_profile.seed_fragments = next_fragments
    receiver_profile.lexical_roots = next_lexical_roots
    receiver_profile.style_notes = (
        list(receiver_profile.style_notes[:3]) + [f"borrowed from {donor_label}"]
    )[-4:]
    return True


def _get_faction_language_profile(world: WorldState, faction_name: str) -> LanguageProfile | None:
    faction = world.factions.get(faction_name)
    if faction is None:
        return None
    if faction.primary_ethnicity and faction.primary_ethnicity in world.ethnicities:
        return world.ethnicities[faction.primary_ethnicity].language_profile
    if faction.identity is not None:
        return faction.identity.language_profile
    return None


def _get_contact_language_sources(world: WorldState, faction_name: str) -> list[tuple[str, float]]:
    contact_scores: dict[str, float] = {}
    owned_regions = [region for region in world.regions.values() if region.owner == faction_name]
    if not owned_regions:
        return []

    for region in owned_regions:
        for neighbor_name in region.neighbors:
            neighbor_owner = world.regions[neighbor_name].owner
            if neighbor_owner is None or neighbor_owner == faction_name:
                continue
            contact_scores[neighbor_owner] = contact_scores.get(neighbor_owner, 0.0) + 1.0
        if region.trade_foreign_partner and region.trade_foreign_partner != faction_name:
            contact_scores[region.trade_foreign_partner] = contact_scores.get(region.trade_foreign_partner, 0.0) + 1.5

    owned_region_names = {region.name for region in owned_regions}
    for first, second in world.river_links:
        if first in owned_region_names:
            other_owner = world.regions.get(second).owner if second in world.regions else None
            if other_owner is not None and other_owner != faction_name:
                contact_scores[other_owner] = contact_scores.get(other_owner, 0.0) + 0.6
        if second in owned_region_names:
            other_owner = world.regions.get(first).owner if first in world.regions else None
            if other_owner is not None and other_owner != faction_name:
                contact_scores[other_owner] = contact_scores.get(other_owner, 0.0) + 0.6

    for first, second in world.sea_links:
        if first in owned_region_names:
            other_owner = world.regions.get(second).owner if second in world.regions else None
            if other_owner is not None and other_owner != faction_name:
                contact_scores[other_owner] = contact_scores.get(other_owner, 0.0) + 0.5
        if second in owned_region_names:
            other_owner = world.regions.get(first).owner if first in world.regions else None
            if other_owner is not None and other_owner != faction_name:
                contact_scores[other_owner] = contact_scores.get(other_owner, 0.0) + 0.5

    for (faction_a, faction_b), state in world.relationships.items():
        if faction_name not in {faction_a, faction_b}:
            continue
        other_name = faction_b if faction_a == faction_name else faction_a
        if other_name not in world.factions:
            continue
        if state.status == "alliance":
            contact_scores[other_name] = contact_scores.get(other_name, 0.0) + 2.0
        elif state.status == "tributary":
            contact_scores[other_name] = contact_scores.get(other_name, 0.0) + 2.4
        elif state.status == "non_aggression_pact":
            contact_scores[other_name] = contact_scores.get(other_name, 0.0) + 0.8

    return sorted(
        contact_scores.items(),
        key=lambda item: (-item[1], item[0]),
    )


def apply_language_contact_borrowing(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        if faction.primary_ethnicity is None:
            continue
        if faction.primary_ethnicity not in world.ethnicities:
            continue
        receiver_ethnicity = world.ethnicities[faction.primary_ethnicity]
        receiver_profile = receiver_ethnicity.language_profile
        receiver_identity_profile = faction.identity.language_profile if faction.identity is not None else None

        for donor_name, intensity in _get_contact_language_sources(world, faction_name)[:2]:
            donor_profile = _get_faction_language_profile(world, donor_name)
            donor_faction = world.factions.get(donor_name)
            if donor_profile is None or donor_faction is None:
                continue
            donor_label = donor_profile.family_name or donor_faction.primary_ethnicity or donor_faction.culture_name
            changed = _add_contact_borrowing(
                receiver_profile,
                donor_profile,
                donor_label=donor_label,
                seed_text=f"{world.turn}|{faction_name}|{donor_name}|{donor_label}",
                intensity=intensity,
            )
            if changed and receiver_identity_profile is not None:
                receiver_identity_profile.onsets = list(receiver_profile.onsets)
                receiver_identity_profile.middles = list(receiver_profile.middles)
                receiver_identity_profile.suffixes = list(receiver_profile.suffixes)
                receiver_identity_profile.seed_fragments = list(receiver_profile.seed_fragments)
                receiver_identity_profile.lexical_roots = {
                    concept: list(values)
                    for concept, values in receiver_profile.lexical_roots.items()
                }
                receiver_identity_profile.style_notes = list(receiver_profile.style_notes)


def _apply_regime_agitation_sponsor_costs(
    world: WorldState,
    sponsor_pressures: dict[str, dict[str, float | str]],
) -> dict[str, dict[str, float | int | str | None]]:
    sponsor_costs: dict[str, dict[str, float | int | str | None]] = {}
    for sponsor_name, details in sponsor_pressures.items():
        sponsor = world.factions.get(sponsor_name)
        if sponsor is None:
            continue
        pressure = float(details.get("pressure", 0.0))
        mode = str(details.get("mode", "standard"))
        cost_multiplier = float(details.get("cost_multiplier", 1.0))
        backlash_multiplier = float(details.get("backlash_multiplier", 1.0))

        treasury_cost = min(
            sponsor.treasury,
            max(1, int(round(pressure * REGIME_AGITATION_TREASURY_COST_FACTOR * cost_multiplier))),
        ) if pressure > 0 else 0
        sponsor.treasury -= treasury_cost

        backlash_region = _choose_regime_agitation_backlash_region(world, sponsor_name)
        backlash_unrest = round(
            pressure * REGIME_AGITATION_HOMEFRONT_UNREST_FACTOR * backlash_multiplier,
            2,
        )
        if backlash_region is not None and backlash_unrest > 0:
            set_region_unrest(backlash_region, backlash_region.unrest + backlash_unrest)

        sponsor_costs[sponsor_name] = {
            "mode": mode,
            "treasury_cost": treasury_cost,
            "treasury_after": sponsor.treasury,
            "backlash_region": backlash_region.name if backlash_region is not None else None,
            "backlash_unrest": backlash_unrest if backlash_region is not None else 0.0,
        }
    return sponsor_costs


def _emit_regime_agitation_event(world: WorldState, region: Region) -> None:
    sponsor_pressures = get_region_external_regime_agitation_breakdown(region, world)
    agitators = sorted(sponsor_pressures)
    agitation = get_region_external_regime_agitation_modifier(region, world)
    if not agitators or agitation <= 0:
        return

    sponsor_costs = _apply_regime_agitation_sponsor_costs(world, sponsor_pressures)
    claimant_sponsors = [
        faction_name
        for faction_name in agitators
        if (
            faction_name in world.factions
            and world.factions[faction_name].rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR
            and not world.factions[faction_name].proto_state
            and world.factions[faction_name].origin_faction == region.owner
        )
    ]
    lead_sponsor = max(
        sponsor_pressures.items(),
        key=lambda item: (float(item[1]["pressure"]), item[0]),
    )[0]
    world.events.append(Event(
        turn=world.turn,
        type="regime_agitation",
        faction=region.owner,
        region=region.name,
        details={
            "sponsors": agitators,
            "lead_sponsor": lead_sponsor,
            "sponsor_pressures": sponsor_pressures,
            "lead_sponsor_mode": sponsor_pressures[lead_sponsor]["mode"],
            "sponsor_costs": sponsor_costs,
            "claimant_sponsors": claimant_sponsors,
            "agitation_pressure": round(agitation, 3),
            "event_level": region.unrest_event_level,
            "unrest": round(region.unrest, 2),
        },
        tags=[
            "unrest",
            "agitation",
            "regime",
            *(["civil_war"] if claimant_sponsors else []),
        ],
        significance=agitation,
    ))


def get_region_ethnic_integration_multiplier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 1.0
    if region.homeland_faction_id == region.owner:
        return 1.0
    multiplier = ETHNIC_INTEGRATION_MIN_MULTIPLIER + get_region_ruling_ethnic_affinity(region, world)
    if faction_has_ethnic_claim(world, region, region.owner):
        multiplier += ETHNIC_CLAIM_INTEGRATION_BONUS
    return multiplier


def get_region_ethnic_unrest_modifier(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.0
    if region.homeland_faction_id == region.owner:
        return 0.0

    affinity = get_region_ruling_ethnic_affinity(region, world)
    if affinity >= ETHNIC_UNREST_CALMING_THRESHOLD:
        modifier = ETHNIC_UNREST_CALMING_EFFECT
    elif affinity >= ETHNIC_UNREST_NEUTRAL_THRESHOLD:
        modifier = 0.0
    elif affinity >= ETHNIC_UNREST_SEVERE_THRESHOLD:
        modifier = ETHNIC_UNREST_LOW_AFFINITY_PRESSURE
    else:
        modifier = ETHNIC_UNREST_SEVERE_AFFINITY_PRESSURE
    if faction_has_ethnic_claim(world, region, region.owner):
        modifier -= ETHNIC_CLAIM_UNREST_REDUCTION
    return modifier


def change_region_population(region: Region, amount: int) -> int:
    previous_population = region.population
    if previous_population <= 0 and amount <= 0:
        return 0
    region.population = max(0, region.population + amount)
    _normalize_region_ethnic_composition(region)
    _normalize_region_religious_composition(region)
    return region.population - previous_population


def apply_region_population_loss(region: Region, ratio: float, *, minimum_loss: int = 1) -> int:
    if region.population <= 0:
        return 0
    loss = max(minimum_loss, int(round(region.population * max(0.0, ratio))))
    return -change_region_population(region, -loss)


def transfer_region_population(source: Region, target: Region, amount: int) -> int:
    if amount <= 0 or source.population <= 0:
        return 0
    amount = min(amount, source.population)
    source_total = source.population
    source_composition = {
        ethnicity: count
        for ethnicity, count in source.ethnic_composition.items()
        if count > 0
    }
    if not source_composition:
        return 0

    moved_counts: dict[str, int] = {}
    assigned = 0
    remainders: list[tuple[float, str]] = []
    for ethnicity, count in source_composition.items():
        moved_value = (count / source_total) * amount
        whole = min(count, int(moved_value))
        moved_counts[ethnicity] = whole
        assigned += whole
        remainders.append((moved_value - whole, ethnicity))
    for _fraction, ethnicity in sorted(remainders, reverse=True):
        if assigned >= amount:
            break
        available = source_composition[ethnicity] - moved_counts[ethnicity]
        if available <= 0:
            continue
        moved_counts[ethnicity] += 1
        assigned += 1

    moved_total = sum(moved_counts.values())
    if moved_total <= 0:
        return 0

    source.population -= moved_total
    target.population += moved_total
    for ethnicity, count in moved_counts.items():
        remaining = source.ethnic_composition.get(ethnicity, 0) - count
        if remaining > 0:
            source.ethnic_composition[ethnicity] = remaining
        elif ethnicity in source.ethnic_composition:
            del source.ethnic_composition[ethnicity]
        target.ethnic_composition[ethnicity] = target.ethnic_composition.get(ethnicity, 0) + count

    _normalize_region_ethnic_composition(source)
    _normalize_region_ethnic_composition(target)
    source_religious_total = max(1, source_total)
    source_religious_composition = {
        religion_name: count
        for religion_name, count in source.religious_composition.items()
        if count > 0
    }
    moved_religions: dict[str, int] = {}
    if source_religious_composition:
        assigned_religions = 0
        religion_remainders: list[tuple[float, str]] = []
        for religion_name, count in source_religious_composition.items():
            moved_value = (count / source_religious_total) * moved_total
            whole = min(count, int(moved_value))
            moved_religions[religion_name] = whole
            assigned_religions += whole
            religion_remainders.append((moved_value - whole, religion_name))
        for _fraction, religion_name in sorted(religion_remainders, reverse=True):
            if assigned_religions >= moved_total:
                break
            available = source_religious_composition[religion_name] - moved_religions[religion_name]
            if available <= 0:
                continue
            moved_religions[religion_name] += 1
            assigned_religions += 1
        for religion_name, count in moved_religions.items():
            remaining = source.religious_composition.get(religion_name, 0) - count
            if remaining > 0:
                source.religious_composition[religion_name] = remaining
            elif religion_name in source.religious_composition:
                del source.religious_composition[religion_name]
            target.religious_composition[religion_name] = target.religious_composition.get(religion_name, 0) + count
        _normalize_region_religious_composition(source)
        _normalize_region_religious_composition(target)
    return moved_total


def estimate_region_population(
    resources: float,
    neighbor_count: int,
    owner: str | None = None,
) -> int:
    if owner is None:
        return 0
    estimate = (
        POPULATION_BASE
        + (resources * POPULATION_PER_RESOURCE)
        + (neighbor_count * POPULATION_PER_CONNECTION)
    )
    estimate += POPULATION_STARTING_OWNER_BONUS
    return max(POPULATION_MINIMUM, int(round(estimate)))


def _get_region_starting_resource_potential(region: Region) -> float:
    total_value = 0.0
    for resource_name, amount in region.resource_fixed_endowments.items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.55
    for resource_name, amount in region.resource_wild_endowments.items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.3
    for resource_name, amount in region.resource_suitability.items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.45
    for resource_name, amount in region.resource_established.items():
        total_value += amount * RESOURCE_VALUE_WEIGHTS.get(resource_name, 1.0) * 0.5
    return total_value / 1.8


def estimate_region_population_from_resource_profile(
    region: Region,
    *,
    owner: str | None = None,
) -> int:
    ensure_region_resource_state(region)
    owner_name = owner if owner is not None else region.owner
    if any(region.resource_output.values()) or any(region.resource_effective_output.values()):
        resource_potential = float(region.resources)
    else:
        resource_potential = max(
            _get_region_starting_resource_potential(region),
            float(get_legacy_region_resource_value(
                None,
                fixed_endowments=region.resource_fixed_endowments,
                wild_endowments=region.resource_wild_endowments,
                suitability=region.resource_suitability,
                established=region.resource_established,
            )),
        )
    return estimate_region_population(
        resource_potential,
        len(region.neighbors),
        owner=owner_name,
    )


def get_region_productive_capacity(region: Region, world: WorldState | None = None) -> float:
    ensure_region_resource_state(region)
    terrain_profile = get_terrain_profile(region)
    terrain_productivity = sum(
        SURPLUS_TERRAIN_PRODUCTIVITY.get(tag, 0.0)
        for tag in terrain_profile["terrain_tags"]
    )
    productive_capacity = (
        get_region_taxable_value(region, world)
        + min(1.5, len(region.neighbors) * SURPLUS_CONNECTION_YIELD)
        + max(-0.8, terrain_productivity * 0.35)
    )
    return round(max(0.0, productive_capacity), 2)


def get_region_population_pressure(region: Region) -> float:
    if region.population <= 0:
        return 0.0
    return round(region.population / SURPLUS_POPULATION_PRESSURE, 2)


def get_region_surplus(region: Region, world: WorldState | None = None) -> float:
    surplus = get_region_productive_capacity(region, world) - get_region_population_pressure(region)
    return round(surplus, 2)


def get_region_surplus_label(region: Region, world: WorldState | None = None) -> str:
    surplus = get_region_surplus(region, world)
    if surplus >= 4.0:
        return "abundant"
    if surplus >= 1.0:
        return "stable"
    if surplus > -1.0:
        return "strained"
    return "deficit"


def get_region_settlement_level(region: Region, world: WorldState | None = None) -> str:
    if region.owner is None or region.population <= 0:
        return "wild"

    surplus = get_region_surplus(region, world)
    core_status = get_region_core_status(region)
    unrest = region.unrest
    ownership_turns = region.ownership_turns

    if (
        region.population >= 320
        and surplus >= 2.5
        and unrest < 3.5
        and core_status in {"homeland", "core"}
        and (core_status == "homeland" or ownership_turns >= 6)
    ):
        return "city"

    if (
        region.population >= 160
        and surplus >= 1.5
        and unrest < 5.0
        and (core_status in {"homeland", "core"} or ownership_turns >= 3)
    ):
        return "town"

    if region.population >= 35 and surplus >= -0.5 and unrest < 8.0:
        return "rural"

    return "wild"


def update_region_settlement_levels(world: WorldState) -> None:
    for region in world.regions.values():
        region.settlement_level = get_region_settlement_level(region, world)


def get_faction_settlement_profile(world: WorldState, faction_name: str) -> dict[str, float | int]:
    profile = {
        "owned_regions": 0,
        "population": 0,
        "total_surplus": 0.0,
        "wild_regions": 0,
        "rural_regions": 0,
        "town_regions": 0,
        "city_regions": 0,
        "settled_regions": 0,
        "core_regions": 0,
        "mature_regions": 0,
        "total_infrastructure": 0.0,
        "total_road": 0.0,
        "total_market": 0.0,
        "total_administrative_support": 0.0,
    }

    for region in world.regions.values():
        if region.owner != faction_name:
            continue
        profile["owned_regions"] += 1
        profile["population"] += region.population
        profile["total_surplus"] += get_region_surplus(region, world)
        profile["total_infrastructure"] += region.infrastructure_level
        profile["total_road"] += region.road_level
        profile["total_market"] += region.market_level
        profile["total_administrative_support"] += region.administrative_support
        if get_region_core_status(region) in {"homeland", "core"}:
            profile["core_regions"] += 1
        settlement_level = region.settlement_level
        if settlement_level == "city":
            profile["city_regions"] += 1
        elif settlement_level == "town":
            profile["town_regions"] += 1
        elif settlement_level == "rural":
            profile["rural_regions"] += 1
        else:
            profile["wild_regions"] += 1
        if settlement_level in {"rural", "town", "city"}:
            profile["settled_regions"] += 1
        if (
            settlement_level in {"town", "city"}
            and get_region_core_status(region) in {"homeland", "core"}
        ):
            profile["mature_regions"] += 1

    profile["total_surplus"] = round(profile["total_surplus"], 2)
    owned_regions = max(1, int(profile["owned_regions"]))
    profile["average_infrastructure"] = round(profile["total_infrastructure"] / owned_regions, 3)
    profile["average_road"] = round(profile["total_road"] / owned_regions, 3)
    profile["average_market"] = round(profile["total_market"] / owned_regions, 3)
    profile["average_administrative_support"] = round(
        profile["total_administrative_support"] / owned_regions,
        3,
    )
    return profile


def _qualifies_for_tribe(profile: dict[str, float | int]) -> bool:
    return profile["owned_regions"] >= 1 and (
        profile["rural_regions"] >= 1
        or profile["town_regions"] >= 1
        or profile["city_regions"] >= 1
    )


def _qualifies_for_chiefdom(profile: dict[str, float | int]) -> bool:
    return (
        profile["owned_regions"] >= 3
        and profile["population"] >= 360
        and profile["total_surplus"] >= 3.5
        and profile["core_regions"] >= 1
        and (profile["town_regions"] + profile["city_regions"]) >= 1
    )


def _qualifies_for_state(profile: dict[str, float | int]) -> bool:
    return (
        profile["owned_regions"] >= 5
        and profile["population"] >= 900
        and profile["total_surplus"] >= 10.0
        and profile["city_regions"] >= 1
        and (profile["town_regions"] + profile["city_regions"]) >= 3
        and profile["core_regions"] >= 2
        and profile["mature_regions"] >= 2
        and profile["average_infrastructure"] >= 0.25
        and profile["average_road"] >= 0.15
        and profile["average_administrative_support"] >= 0.18
    )


def get_next_polity_tier(
    current_tier: str,
    profile: dict[str, float | int],
) -> str:
    if current_tier == "band" and _qualifies_for_tribe(profile):
        return "tribe"
    if current_tier == "tribe" and _qualifies_for_chiefdom(profile):
        return "chiefdom"
    if current_tier == "chiefdom" and _qualifies_for_state(profile):
        return "state"
    return current_tier


def update_faction_polity_tiers(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        if faction.identity is None:
            continue

        current_tier = faction.polity_tier
        previous_form = faction.government_form
        profile = get_faction_settlement_profile(world, faction_name)
        next_tier = get_next_polity_tier(current_tier, profile)
        if next_tier == current_tier:
            continue

        next_form = previous_form
        if next_form not in GOVERNMENT_FORMS_BY_TIER[next_tier]:
            next_form = get_default_government_form(next_tier)

        prior_display_name = faction.identity.display_name
        refresh_display_name = prior_display_name == faction.identity.default_display_name()
        old_government_type = faction.government_type
        faction.identity.set_government_structure(
            next_tier,
            next_form,
            update_display_name=refresh_display_name,
        )
        evolve_faction_succession_politics(
            faction,
            previous_tier=current_tier,
            previous_form=previous_form,
        )
        evolve_faction_religion_politics(
            faction,
            previous_tier=current_tier,
            previous_form=previous_form,
        )
        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            set_region_unrest(
                region,
                max(0.0, region.unrest - POLITY_ADVANCEMENT_UNREST_REDUCTION),
            )

        world.events.append(Event(
            turn=world.turn,
            type="polity_advance",
            faction=faction_name,
            details={
                "old_polity_tier": current_tier,
                "new_polity_tier": next_tier,
                "old_government_type": old_government_type,
                "new_government_type": faction.government_type,
                "town_regions": profile["town_regions"],
                "city_regions": profile["city_regions"],
                "population": profile["population"],
                "total_surplus": profile["total_surplus"],
            },
            tags=["government", "polity", "advancement"],
            significance=float(POLITY_TIER_ORDER.index(next_tier)),
        ))


def update_region_populations(world: WorldState) -> None:
    for region in world.regions.values():
        if region.population <= 0:
            continue
        growth_factor = POPULATION_GROWTH_PER_TURN
        if region.owner is None:
            growth_factor *= POPULATION_UNOWNED_GROWTH_FACTOR
        unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
        growth_factor -= unrest_ratio * POPULATION_UNREST_GROWTH_PENALTY * POPULATION_GROWTH_PER_TURN
        surplus_growth_modifier = _clamp(
            get_region_surplus(region, world) * SURPLUS_GROWTH_FACTOR,
            SURPLUS_MIN_GROWTH_PENALTY,
            SURPLUS_MAX_GROWTH_BONUS,
        )
        if surplus_growth_modifier > 0:
            surplus_growth_modifier *= (1.0 - unrest_ratio)
        growth_factor += surplus_growth_modifier

        if region.owner in world.factions:
            food_consumption = max(0.2, region.food_consumption)
            food_deficit_ratio = min(
                1.0,
                region.food_deficit / food_consumption,
            )
            if food_deficit_ratio > 0:
                growth_factor -= min(
                    POPULATION_FOOD_DEFICIT_MAX_PENALTY,
                    food_deficit_ratio * POPULATION_FOOD_DEFICIT_PENALTY_FACTOR,
                )
            else:
                food_surplus_ratio = min(
                    1.0,
                    max(0.0, region.food_balance) / food_consumption,
                )
                growth_factor += min(
                    POPULATION_FOOD_SURPLUS_MAX_BONUS,
                    food_surplus_ratio * POPULATION_FOOD_SURPLUS_BONUS_FACTOR,
                )

        change = int(round(region.population * growth_factor))
        if change == 0 and growth_factor > 0:
            change = 1
        if change != 0:
            change_region_population(region, change)


def _reset_migration_state(world: WorldState) -> None:
    for region in world.regions.values():
        region.migration_inflow = 0
        region.migration_outflow = 0
        region.refugee_inflow = 0
        region.refugee_outflow = 0
        region.frontier_settler_inflow = 0
        region.migration_pressure = 0.0
        region.migration_attraction = 0.0
    for faction in world.factions.values():
        faction.migration_inflow = 0
        faction.migration_outflow = 0
        faction.refugee_inflow = 0
        faction.refugee_outflow = 0
        faction.frontier_settlers = 0


def _get_food_deficit_ratio(region: Region) -> float:
    food_consumption = max(0.2, float(region.food_consumption or 0.0))
    return _clamp(float(region.food_deficit or 0.0) / food_consumption, 0.0, 1.0)


def _get_food_surplus_ratio(region: Region) -> float:
    food_consumption = max(0.2, float(region.food_consumption or 0.0))
    return _clamp(max(0.0, float(region.food_balance or 0.0)) / food_consumption, 0.0, 1.0)


def _get_region_migration_pressure(region: Region, world: WorldState) -> float:
    if region.owner is None or region.population < MIGRATION_MIN_SOURCE_POPULATION:
        return 0.0
    season_name = get_turn_season_name(world.turn)
    unrest_ratio = _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
    surplus_pressure = _clamp(max(0.0, -get_region_surplus(region, world)) / 3.0, 0.0, 1.0)
    frontier_pressure = 1.0 if get_region_core_status(region) == "frontier" else 0.0
    base_pressure = (
        _get_food_deficit_ratio(region) * MIGRATION_PRESSURE_FOOD_FACTOR
        + unrest_ratio * MIGRATION_PRESSURE_UNREST_FACTOR
        + surplus_pressure * MIGRATION_PRESSURE_SURPLUS_FACTOR
        + frontier_pressure * MIGRATION_PRESSURE_FRONTIER_FACTOR
    )
    pressure = base_pressure * get_seasonal_migration_pressure_modifier(season_name)
    if region.unrest_event_level == "crisis":
        pressure += MIGRATION_REFUGEE_CRISIS_BONUS
    elif region.unrest_event_level == "disturbance":
        pressure += MIGRATION_REFUGEE_CRISIS_BONUS * 0.45
    return round(_clamp(pressure, 0.0, 1.0), 3)


def _get_region_migration_attraction(region: Region, world: WorldState) -> float:
    if region.owner is None or region.population <= 0:
        return 0.0
    season_name = get_turn_season_name(world.turn)
    low_unrest = 1.0 - _clamp(region.unrest / UNREST_MAX, 0.0, 1.0)
    surplus_bonus = _clamp(max(0.0, get_region_surplus(region, world)) / 3.5, 0.0, 1.0)
    food_bonus = _get_food_surplus_ratio(region)
    trade_bonus = _clamp(
        (
            float(region.trade_throughput or 0.0)
            + float(region.trade_foreign_flow or 0.0)
            + float(region.trade_import_value or 0.0)
        ) / 10.0,
        0.0,
        1.0,
    )
    development_bonus = _clamp(
        (
            float(region.infrastructure_level or 0.0)
            + float(region.road_level or 0.0)
            + float(region.market_level or 0.0)
            + float(region.storehouse_level or 0.0)
        ) / 3.5,
        0.0,
        1.0,
    )
    attraction = (
        surplus_bonus * MIGRATION_ATTRACTION_SURPLUS_FACTOR
        + food_bonus * MIGRATION_ATTRACTION_FOOD_FACTOR
        + trade_bonus * MIGRATION_ATTRACTION_TRADE_FACTOR
        + development_bonus * MIGRATION_ATTRACTION_DEVELOPMENT_FACTOR
        + low_unrest * MIGRATION_ATTRACTION_LOW_UNREST_FACTOR
    )
    core_status = get_region_core_status(region)
    if core_status == "frontier":
        attraction += MIGRATION_ATTRACTION_FRONTIER_BONUS
    elif core_status == "core":
        attraction += MIGRATION_ATTRACTION_CORE_BONUS
    if region.settlement_level == "city":
        attraction += MIGRATION_ATTRACTION_CITY_BONUS
    elif region.settlement_level == "town":
        attraction += MIGRATION_ATTRACTION_CITY_BONUS * 0.6
    attraction *= get_seasonal_migration_attraction_modifier(season_name)
    attraction *= get_seasonal_terrain_migration_attraction_multiplier(region, season_name)
    return round(_clamp(attraction, 0.0, 1.5), 3)


def _get_region_migration_capacity(region: Region, world: WorldState) -> int:
    if region.owner is None or region.population <= 0:
        return 0
    season_name = get_turn_season_name(world.turn)
    food_headroom = max(0.0, float(region.food_storage_capacity or 0.0) - float(region.food_stored or 0.0))
    capacity = (
        max(14, int(round(region.population * 0.11)))
        + int(round(max(0.0, get_region_surplus(region, world)) * 14))
        + int(round(food_headroom * 10))
    )
    if get_region_core_status(region) == "frontier":
        capacity = int(round(capacity * 1.2))
    capacity = int(round(capacity * get_seasonal_migration_capacity_modifier(season_name)))
    capacity = int(round(capacity * get_seasonal_terrain_migration_capacity_multiplier(region, season_name)))
    return max(8, capacity)


def _get_internal_connection_score(source: Region, target: Region) -> float:
    score = 0.2
    if target.name in source.neighbors:
        score += MIGRATION_NEIGHBOR_FACTOR
    if source.trade_route_parent == target.name or target.trade_route_parent == source.name:
        score += MIGRATION_PARENT_CHILD_FACTOR
    if (
        source.resource_route_anchor
        and source.resource_route_anchor == target.resource_route_anchor
    ):
        score += MIGRATION_ROUTE_ANCHOR_FACTOR
    if source.resource_route_anchor == target.name or target.resource_route_anchor == source.name:
        score += MIGRATION_PARENT_CHILD_FACTOR * 0.45
    return score


def _iter_internal_migration_destinations(source: Region, world: WorldState) -> list[tuple[Region, float]]:
    candidates: list[tuple[Region, float]] = []
    if source.owner is None:
        return candidates
    for target in world.regions.values():
        if target.name == source.name or target.owner != source.owner:
            continue
        if target.migration_attraction <= 0.12:
            continue
        connection_score = _get_internal_connection_score(source, target)
        if connection_score <= 0.2 and get_region_core_status(target) != "frontier":
            continue
        score = target.migration_attraction * (1.0 + connection_score)
        if get_region_core_status(target) == "frontier":
            score *= 1.15
        candidates.append((target, round(score, 3)))
    return sorted(candidates, key=lambda item: (item[1], item[0].name), reverse=True)


def _iter_foreign_refugee_destinations(source: Region, world: WorldState) -> list[tuple[Region, float]]:
    if source.owner is None:
        return []
    candidates: dict[str, tuple[Region, float]] = {}

    def maybe_add_target(target_name: str, *, route_bonus: float = 0.0) -> None:
        target = world.regions.get(target_name)
        if target is None or target.owner is None or target.owner == source.owner:
            return
        status = get_relationship_status(world, source.owner, target.owner)
        if status not in {"alliance", "non_aggression_pact"}:
            return
        if target.migration_attraction <= 0.18:
            return
        score = target.migration_attraction * MIGRATION_FRIENDLY_BORDER_FACTOR * (1.0 + route_bonus)
        existing = candidates.get(target.name)
        if existing is None or score > existing[1]:
            candidates[target.name] = (target, round(score, 3))

    for neighbor_name in source.neighbors:
        maybe_add_target(neighbor_name, route_bonus=MIGRATION_NEIGHBOR_FACTOR)

    for first, second in world.sea_links:
        if first == source.name:
            maybe_add_target(second, route_bonus=MIGRATION_ROUTE_ANCHOR_FACTOR + 0.18)
        elif second == source.name:
            maybe_add_target(first, route_bonus=MIGRATION_ROUTE_ANCHOR_FACTOR + 0.18)

    if source.trade_foreign_partner_region:
        maybe_add_target(source.trade_foreign_partner_region, route_bonus=MIGRATION_PARENT_CHILD_FACTOR * 0.7)

    return sorted(candidates.values(), key=lambda item: (item[1], item[0].name), reverse=True)


def _record_migration_move(
    world: WorldState,
    source: Region,
    target: Region,
    moved: int,
    *,
    refugee: bool,
) -> None:
    if moved <= 0 or source.owner is None or target.owner is None:
        return
    source.migration_outflow += moved
    target.migration_inflow += moved
    world.factions[source.owner].migration_outflow += moved
    world.factions[target.owner].migration_inflow += moved

    if refugee:
        source.refugee_outflow += moved
        target.refugee_inflow += moved
        world.factions[source.owner].refugee_outflow += moved
        world.factions[target.owner].refugee_inflow += moved

    if source.owner == target.owner and get_region_core_status(target) == "frontier":
        target.frontier_settler_inflow += moved
        world.factions[target.owner].frontier_settlers += moved
        target.integration_score = round(
            target.integration_score + ((moved / 100.0) * MIGRATION_FRONTIER_INTEGRATION_PER_100),
            2,
        )
        set_region_unrest(
            target,
            max(0.0, target.unrest - (MIGRATION_FRONTIER_UNREST_REDUCTION * (moved / 40.0))),
        )


def _emit_migration_event(
    world: WorldState,
    source: Region,
    *,
    total_moved: int,
    refugee_moved: int,
    destination_breakdown: dict[str, int],
) -> None:
    if total_moved < MIGRATION_EVENT_MINIMUM or source.owner is None:
        return
    top_destinations = sorted(
        destination_breakdown.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )[:3]
    top_destination_name = top_destinations[0][0] if top_destinations else None
    event_type = "refugee_wave" if refugee_moved >= max(10, int(round(total_moved * 0.45))) else "migration_wave"
    world.events.append(Event(
        turn=world.turn,
        type=event_type,
        faction=source.owner,
        region=source.name,
        details={
            "population_moved": total_moved,
            "refugees": refugee_moved,
            "top_destination": top_destination_name,
            "destinations": [
                {"region": region_name, "population": amount}
                for region_name, amount in top_destinations
            ],
            "source_unrest": round(source.unrest, 2),
            "source_food_deficit": round(source.food_deficit, 3),
            "source_trade_role": source.trade_route_role,
        },
        tags=["population", "migration", *(["refugees"] if refugee_moved > 0 else ["settlement"])],
        significance=round(total_moved / max(1, source.population + total_moved), 3),
    ))


def resolve_population_migration(world: WorldState) -> None:
    _reset_migration_state(world)
    if not world.regions:
        return
    season_name = get_turn_season_name(world.turn)
    migration_flow_modifier = get_seasonal_migration_flow_modifier(season_name)
    refugee_flow_modifier = get_seasonal_refugee_flow_modifier(season_name)

    source_regions: list[tuple[Region, int, int]] = []
    for region in world.regions.values():
        region.migration_pressure = _get_region_migration_pressure(region, world)
        region.migration_attraction = _get_region_migration_attraction(region, world)
    for region in world.regions.values():
        if region.owner is None or region.population < MIGRATION_MIN_SOURCE_POPULATION:
            continue
        migration_share = min(
            MIGRATION_MAX_SHARE_PER_TURN,
            float(region.migration_pressure or 0.0) * MIGRATION_MAX_SHARE_PER_TURN,
        )
        severe_displacement = (
            region.unrest_event_level == "crisis"
            or region.unrest >= MIGRATION_REFUGEE_SEVERE_UNREST
            or _get_food_deficit_ratio(region) >= 0.75
        )
        movement_volume_modifier = refugee_flow_modifier if severe_displacement else migration_flow_modifier
        movable_population = int(round(region.population * migration_share * movement_volume_modifier))
        if movable_population <= 0:
            continue
        refugee_ratio = 0.0
        if severe_displacement:
            refugee_ratio = _clamp(0.25 + (float(region.migration_pressure or 0.0) * 0.45), 0.25, 0.85)
        refugee_population = int(round(movable_population * refugee_ratio))
        source_regions.append((region, movable_population, refugee_population))

    source_regions.sort(
        key=lambda item: (float(item[0].migration_pressure or 0.0), item[0].population),
        reverse=True,
    )

    destination_capacity_used: dict[str, int] = {region_name: 0 for region_name in world.regions}

    for source, movable_population, refugee_population in source_regions:
        remaining = min(movable_population, source.population)
        if remaining <= 0:
            continue
        refugee_remaining = min(refugee_population, remaining)
        destination_breakdown: dict[str, int] = {}
        total_moved = 0
        total_refugees = 0

        for target, score in _iter_internal_migration_destinations(source, world):
            if remaining <= refugee_remaining and refugee_remaining > 0:
                break
            target_capacity = _get_region_migration_capacity(target, world) - destination_capacity_used[target.name]
            if target_capacity <= 0:
                continue
            move_cap = max(4, int(round(score * 10 * migration_flow_modifier)))
            move_amount = min(remaining - refugee_remaining, target_capacity, move_cap, source.population)
            if move_amount <= 0:
                continue
            moved = transfer_region_population(source, target, move_amount)
            if moved <= 0:
                continue
            remaining -= moved
            total_moved += moved
            destination_capacity_used[target.name] += moved
            destination_breakdown[target.name] = destination_breakdown.get(target.name, 0) + moved
            _record_migration_move(world, source, target, moved, refugee=False)

        for target, score in _iter_foreign_refugee_destinations(source, world):
            if refugee_remaining <= 0:
                break
            target_capacity = _get_region_migration_capacity(target, world) - destination_capacity_used[target.name]
            if target_capacity <= 0:
                continue
            move_cap = max(4, int(round(score * 9 * refugee_flow_modifier)))
            move_amount = min(refugee_remaining, target_capacity, move_cap, source.population)
            if move_amount <= 0:
                continue
            moved = transfer_region_population(source, target, move_amount)
            if moved <= 0:
                continue
            refugee_remaining -= moved
            remaining -= moved
            total_moved += moved
            total_refugees += moved
            destination_capacity_used[target.name] += moved
            destination_breakdown[target.name] = destination_breakdown.get(target.name, 0) + moved
            _record_migration_move(world, source, target, moved, refugee=True)

        if remaining > 0 and get_region_core_status(source) == "frontier":
            for target, score in _iter_internal_migration_destinations(source, world):
                if remaining <= 0:
                    break
                if get_region_core_status(target) != "core":
                    continue
                target_capacity = _get_region_migration_capacity(target, world) - destination_capacity_used[target.name]
                if target_capacity <= 0:
                    continue
                move_cap = max(3, int(round(score * 7 * migration_flow_modifier)))
                move_amount = min(remaining, target_capacity, move_cap, source.population)
                if move_amount <= 0:
                    continue
                moved = transfer_region_population(source, target, move_amount)
                if moved <= 0:
                    continue
                remaining -= moved
                total_moved += moved
                destination_capacity_used[target.name] += moved
                destination_breakdown[target.name] = destination_breakdown.get(target.name, 0) + moved
                _record_migration_move(world, source, target, moved, refugee=False)

        _emit_migration_event(
            world,
            source,
            total_moved=total_moved,
            refugee_moved=total_refugees,
            destination_breakdown=destination_breakdown,
        )


def _get_region_administrative_support(region: Region) -> float:
    support = ADMIN_SUPPORT_SETTLEMENT_BONUSES.get(region.settlement_level, 0.0)
    support += region.infrastructure_level * ADMIN_SUPPORT_INFRASTRUCTURE_FACTOR
    support += region.road_level * ADMIN_SUPPORT_ROAD_FACTOR
    support += region.market_level * ADMIN_SUPPORT_MARKET_FACTOR
    support += region.storehouse_level * ADMIN_SUPPORT_STOREHOUSE_FACTOR
    support += region.integration_score * ADMIN_SUPPORT_INTEGRATION_FACTOR
    status = get_region_core_status(region)
    if status == "homeland":
        support += 0.18
    elif status == "core":
        support += 0.08
    return round(max(0.0, support), 3)


def _get_region_administrative_distance(region: Region, world: WorldState) -> float:
    if region.owner is None or get_region_core_status(region) == "homeland":
        return 0.0

    distance = float(region.resource_route_depth or 0) * ADMIN_DISTANCE_PER_ROUTE_DEPTH
    if not region.resource_route_depth:
        distance += 0.1 if get_region_core_status(region) == "frontier" else 0.04
    if region.resource_route_mode in {"sea", "river"}:
        distance = max(0.0, distance - 0.04)

    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None or neighbor.owner == region.owner:
            continue
        distance += ADMIN_FOREIGN_BORDER_DISTANCE
        relation = get_relationship_status(world, region.owner, neighbor.owner)
        if relation in {"rival", "war", "truce"}:
            distance += ADMIN_HOSTILE_BORDER_DISTANCE

    return round(min(1.8, distance), 3)


def _get_region_administrative_burden(region: Region, world: WorldState) -> float:
    status = get_region_core_status(region)
    burden = {
        "homeland": ADMIN_BURDEN_HOMELAND,
        "core": ADMIN_BURDEN_CORE,
        "frontier": ADMIN_BURDEN_FRONTIER,
    }.get(status, ADMIN_BURDEN_FRONTIER)
    burden += _get_region_administrative_distance(region, world)
    burden += min(
        ADMIN_POPULATION_BURDEN_MAX,
        max(0.0, region.population) * ADMIN_POPULATION_BURDEN_FACTOR,
    )
    burden += region.unrest * ADMIN_UNREST_BURDEN_FACTOR
    if region.unrest_event_level == "disturbance":
        burden += 0.12
    elif region.unrest_event_level == "crisis":
        burden += 0.24
    return round(max(0.35, burden), 3)


def refresh_administrative_state(world: WorldState) -> None:
    per_faction_support: dict[str, float] = {}
    per_faction_distance: dict[str, float] = {}
    per_faction_regions: dict[str, int] = {}

    for faction in world.factions.values():
        faction.administrative_capacity = 0.0
        faction.administrative_load = 0.0
        faction.administrative_efficiency = 1.0
        faction.administrative_reach = 1.0
        faction.administrative_overextension = 0.0
        faction.administrative_overextension_penalty = 0.0

    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            region.administrative_burden = 0.0
            region.administrative_support = 0.0
            region.administrative_distance = 0.0
            region.administrative_autonomy = 0.0
            region.administrative_tax_capture = 1.0
            continue

        owner_name = region.owner
        region.administrative_support = _get_region_administrative_support(region)
        region.administrative_distance = _get_region_administrative_distance(region, world)
        region.administrative_burden = _get_region_administrative_burden(region, world)
        region.administrative_autonomy = 0.0
        region.administrative_tax_capture = 1.0

        per_faction_support[owner_name] = per_faction_support.get(owner_name, 0.0) + region.administrative_support
        per_faction_distance[owner_name] = per_faction_distance.get(owner_name, 0.0) + region.administrative_distance
        per_faction_regions[owner_name] = per_faction_regions.get(owner_name, 0) + 1
        world.factions[owner_name].administrative_load = round(
            world.factions[owner_name].administrative_load + region.administrative_burden,
            3,
        )

    for faction_name, faction in world.factions.items():
        region_count = per_faction_regions.get(faction_name, 0)
        if region_count <= 0:
            continue
        average_support = per_faction_support.get(faction_name, 0.0) / region_count
        average_distance = per_faction_distance.get(faction_name, 0.0) / region_count
        legitimacy_support = (
            0.78
            + (float(faction.succession.legitimacy or 0.0) * ADMIN_LEGITIMACY_WEIGHT)
            + (float(faction.religion.religious_legitimacy or 0.0) * ADMIN_RELIGIOUS_LEGITIMACY_WEIGHT)
        )
        capacity = (
            region_count
            * ADMIN_BASE_CAPACITY_PER_REGION
            * get_faction_administrative_capacity_modifier(faction)
            * (1.0 + (average_support * ADMIN_SUPPORT_CAPACITY_FACTOR))
            * legitimacy_support
        )
        capacity += max(0.0, float(faction.derived_capacity.get("mobility_capacity", 0.0))) * ADMIN_MOBILITY_CAPACITY_FACTOR
        capacity += max(0.0, float(faction.derived_capacity.get("taxable_value", 0.0))) * ADMIN_TAXABLE_CAPACITY_FACTOR

        load = max(0.01, float(faction.administrative_load or 0.0))
        efficiency = max(0.45, min(1.15, capacity / load))
        reach = max(
            0.45,
            min(
                1.15,
                (1.02 - (average_distance * 0.28) + (average_support * 0.06))
                * get_faction_administrative_reach_modifier(faction),
            ),
        )
        overextension = max(0.0, load - capacity)

        faction.administrative_capacity = round(capacity, 3)
        faction.administrative_efficiency = round(efficiency, 3)
        faction.administrative_reach = round(reach, 3)
        faction.administrative_overextension = round(overextension, 3)
        faction.administrative_overextension_penalty = round(
            overextension * ADMIN_OVEREXTENSION_PENALTY_FACTOR,
            2,
        )

        for region in world.regions.values():
            if region.owner != faction_name:
                continue
            autonomy = max(
                0.0,
                region.administrative_burden
                - (0.62 + (region.administrative_support * 0.9) + (efficiency * 0.85) + (reach * 0.35)),
            )
            tax_capture = (
                (efficiency * 0.78)
                + (reach * 0.18)
                + (region.administrative_support * 0.14)
                - (autonomy * 0.16)
            )
            status = get_region_core_status(region)
            if status == "homeland":
                tax_capture += 0.05
            elif status == "core":
                tax_capture += 0.02
            elif status == "frontier":
                tax_capture -= 0.04
            region.administrative_autonomy = round(min(2.5, autonomy), 3)
            region.administrative_tax_capture = round(max(0.42, min(1.05, tax_capture)), 3)


def set_region_integration(
    region: Region,
    *,
    owner: str | None,
    score: float,
    ownership_turns: int,
    core_status: str | None = None,
) -> None:
    region.integrated_owner = owner
    region.integration_score = score
    region.ownership_turns = ownership_turns
    region.core_status = core_status or get_region_core_status(region)


def set_region_unrest(region: Region, unrest: float) -> None:
    region.unrest = round(_clamp(unrest, 0.0, UNREST_MAX), 2)


def clear_region_unrest_event(region: Region) -> None:
    region.unrest_event_level = "none"
    region.unrest_event_turns_remaining = 0


def set_region_unrest_event(region: Region, *, level: str, duration: int) -> None:
    region.unrest_event_level = level
    region.unrest_event_turns_remaining = duration


def get_region_unrest_event_cost(region: Region) -> int:
    if region.unrest_event_level == "crisis":
        return UNREST_CRISIS_TREASURY_HIT
    if region.unrest_event_level == "disturbance":
        return UNREST_DISTURBANCE_TREASURY_HIT
    return 0


def reset_region_crisis_streak(region: Region) -> None:
    region.unrest_crisis_streak = 0


def set_region_secession_cooldown(region: Region, turns: int) -> None:
    region.secession_cooldown_turns = max(0, turns)


def _normalize_rebel_name_seed(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _letters_only(value: str) -> str:
    return "".join(character for character in (value or "") if character.isalpha())


def _extract_name_fragments(value: str) -> list[str]:
    normalized = _letters_only(value).lower()
    if len(normalized) < 4:
        return [normalized] if normalized else []
    fragments = [
        normalized[:3],
        normalized[:4],
        normalized[-3:],
        normalized[-4:],
        normalized[1:4],
    ]
    unique_fragments: list[str] = []
    for fragment in fragments:
        if len(fragment) >= 2 and fragment not in unique_fragments:
            unique_fragments.append(fragment)
    return unique_fragments


def _to_title_case_root(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:].lower()


SUCCESSOR_SOUND_CHANGE_SETS = (
    ("a_to_e", (("a", "e"),)),
    ("o_to_u", (("o", "u"),)),
    ("k_to_h", (("k", "h"), ("kh", "h"))),
    ("t_to_s", (("ti", "si"), ("ta", "sa"), ("to", "so"), ("t", "s"))),
    ("r_to_l", (("r", "l"),)),
    ("an_to_en", (("an", "en"), ("ar", "er"))),
    ("or_to_ur", (("or", "ur"), ("on", "un"))),
    ("final_soften", (("ad", "ar"), ("and", "an"), ("os", "or"), ("um", "un"))),
)


def _apply_successor_sound_changes(value: str, sound_changes: tuple[tuple[str, str], ...]) -> str:
    normalized = _letters_only(value).lower()
    if not normalized:
        return normalized
    updated = normalized
    for source, target in sound_changes:
        updated = updated.replace(source, target)
    updated = re.sub(r"([aeiou])\1{2,}", r"\1\1", updated)
    updated = re.sub(r"(.)\1{2,}", r"\1\1", updated)
    updated = re.sub(r"([bcdfghjklmnpqrstvwxyz]{4,})", lambda match: match.group(0)[:3], updated)
    return updated


def _derive_successor_sound_changes(
    parent_profile: LanguageProfile,
    parent_ethnicity: str,
    faction_name: str,
    turn: int,
) -> tuple[list[str], tuple[tuple[str, str], ...]]:
    rng = random.Random(
        f"{parent_profile.family_name}|{parent_ethnicity}|{faction_name}|{turn}|successor_sound_change"
    )
    available = list(SUCCESSOR_SOUND_CHANGE_SETS)
    rng.shuffle(available)
    selected = available[: rng.randint(2, 3)]
    labels = [label for label, _changes in selected]
    changes = tuple(
        pair
        for _label, replacements in selected
        for pair in replacements
    )
    return labels, changes


def _mutate_successor_language_pool(
    values: list[str],
    sound_changes: tuple[tuple[str, str], ...],
    *,
    minimum_length: int,
    maximum_length: int,
    limit: int,
) -> list[str]:
    mutated: list[str] = []
    for value in values:
        changed = _apply_successor_sound_changes(value, sound_changes)
        if minimum_length <= len(changed) <= maximum_length:
            mutated.append(changed)
        normalized = _letters_only(value).lower()
        if minimum_length <= len(normalized) <= maximum_length:
            mutated.append(normalized)
    unique: list[str] = []
    seen: set[str] = set()
    for value in mutated:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique[:limit]


def _generate_successor_ethnicity_name(
    world: WorldState,
    parent_ethnicity: str,
    faction_name: str,
) -> str:
    parent_profile = world.ethnicities.get(parent_ethnicity).language_profile if parent_ethnicity in world.ethnicities else LanguageProfile()
    rng = random.Random(f"{parent_ethnicity}:{faction_name}:{world.turn}")
    _sound_change_labels, sound_changes = _derive_successor_sound_changes(
        parent_profile,
        parent_ethnicity,
        faction_name,
        world.turn,
    )

    onsets = parent_profile.onsets or ["ka", "sa", "va", "ta", "no"]
    middles = parent_profile.middles or ["a", "e", "i", "o", "u", "ae", "ia"]
    suffixes = parent_profile.suffixes or ["ar", "an", "en", "or", "ri", "var"]
    fragments = parent_profile.seed_fragments or [_letters_only(parent_ethnicity).lower() or "novan"]

    shifted_fragments = _mutate_successor_language_pool(
        fragments,
        sound_changes,
        minimum_length=2,
        maximum_length=8,
        limit=16,
    ) or fragments
    shifted_onsets = _mutate_successor_language_pool(
        onsets,
        sound_changes,
        minimum_length=2,
        maximum_length=5,
        limit=12,
    ) or onsets
    shifted_middles = _mutate_successor_language_pool(
        middles,
        sound_changes,
        minimum_length=1,
        maximum_length=4,
        limit=12,
    ) or middles
    shifted_suffixes = _mutate_successor_language_pool(
        suffixes,
        sound_changes,
        minimum_length=2,
        maximum_length=5,
        limit=12,
    ) or suffixes

    fragment = rng.choice(shifted_fragments)
    onset = rng.choice(shifted_onsets)
    middle = rng.choice(shifted_middles)
    suffix = rng.choice(shifted_suffixes)
    endings = ["ri", "vi", "ra", "ta", "ni", "len", "var", "sar"]
    shifted_parent_root = _apply_successor_sound_changes(parent_ethnicity, sound_changes) or _letters_only(parent_ethnicity).lower()

    pattern = rng.choice(("profile_blend", "fragment_soften", "compound", "shifted_root"))
    if pattern == "profile_blend":
        candidate = f"{onset[: max(1, min(3, len(onset)))]}{middle}{fragment[-max(2, min(4, len(fragment))):]}{rng.choice(endings)}"
    elif pattern == "fragment_soften":
        candidate = f"{fragment[: max(2, min(4, len(fragment)))]}{middle}{suffix}"
    elif pattern == "compound":
        candidate = f"{onset[:2]}{fragment[max(1, len(fragment) // 3): max(3, len(fragment) // 3 + 3)]}{suffix}"
    else:
        candidate = (
            f"{shifted_parent_root[: max(2, min(4, len(shifted_parent_root)))]}"
            f"{middle}"
            f"{suffix}"
        )

    candidate = _to_title_case_root(re.sub(r"[^A-Za-z]", "", candidate))
    if _letters_only(candidate).lower() == _letters_only(parent_ethnicity).lower():
        candidate = _to_title_case_root(f"{candidate}n")
    while candidate in world.ethnicities:
        candidate = f"{candidate}n"
    return candidate


def _build_successor_language_profile(
    parent_profile: LanguageProfile,
    successor_ethnicity: str,
    sound_change_labels: list[str],
    sound_changes: tuple[tuple[str, str], ...],
) -> LanguageProfile:
    successor_fragments = _extract_name_fragments(successor_ethnicity)
    shifted_onsets = _mutate_successor_language_pool(
        parent_profile.onsets,
        sound_changes,
        minimum_length=2,
        maximum_length=5,
        limit=12,
    )
    shifted_middles = _mutate_successor_language_pool(
        parent_profile.middles,
        sound_changes,
        minimum_length=1,
        maximum_length=4,
        limit=12,
    )
    shifted_suffixes = _mutate_successor_language_pool(
        parent_profile.suffixes,
        sound_changes,
        minimum_length=2,
        maximum_length=5,
        limit=12,
    )
    shifted_seed_fragments = _mutate_successor_language_pool(
        parent_profile.seed_fragments,
        sound_changes,
        minimum_length=2,
        maximum_length=8,
        limit=16,
    )
    shifted_lexical_roots = {
        concept: _mutate_successor_language_pool(
            values,
            sound_changes,
            minimum_length=2,
            maximum_length=8,
            limit=3,
        )
        for concept, values in (parent_profile.lexical_roots or {}).items()
    }
    return LanguageProfile(
        family_name=parent_profile.family_name or successor_ethnicity,
        onsets=(shifted_onsets + successor_fragments[:3])[:12],
        middles=(shifted_middles + successor_fragments[:2])[:12],
        suffixes=(shifted_suffixes + [fragment[-3:] for fragment in successor_fragments if len(fragment) >= 3])[:12],
        seed_fragments=(shifted_seed_fragments + successor_fragments)[:16],
        lexical_roots=_merge_language_lexical_roots(
            shifted_lexical_roots,
            {
                "ruler": successor_fragments[:1],
                "dynasty": successor_fragments[-1:],
                "ancestor": successor_fragments[:1],
                "settlement": successor_fragments[-1:],
            },
        ),
        style_notes=(parent_profile.style_notes[:3] + [f"successor shifts: {', '.join(sound_change_labels)}"])[:4],
    )


def _split_successor_ethnicity_in_regions(
    world: WorldState,
    faction_name: str,
    parent_ethnicity: str,
    successor_ethnicity: str,
) -> tuple[int, int]:
    successor_total = 0
    parent_total = 0

    for region in world.regions.values():
        if region.owner != faction_name or region.population <= 0:
            continue

        parent_count = region.ethnic_composition.get(parent_ethnicity, 0)
        if parent_count <= 0:
            parent_count = region.population
            region.ethnic_composition[parent_ethnicity] = parent_count

        successor_count = max(
            region.population // 2,
            int(round(region.population * 0.6)),
        )
        successor_count = min(successor_count, max(1, parent_count - 1) if parent_count > 1 else parent_count)
        if successor_count <= 0:
            continue

        region.ethnic_composition[parent_ethnicity] = max(
            0,
            region.ethnic_composition.get(parent_ethnicity, 0) - successor_count,
        )
        region.ethnic_composition[successor_ethnicity] = (
            region.ethnic_composition.get(successor_ethnicity, 0) + successor_count
        )
        _normalize_region_ethnic_composition(region)
        successor_total += region.ethnic_composition.get(successor_ethnicity, 0)
        parent_total += region.ethnic_composition.get(parent_ethnicity, 0)

    return successor_total, parent_total


def _build_rebel_faction_name(world: WorldState, region: Region) -> str:
    base_name = _normalize_rebel_name_seed(f"{region.ui_name} Rebels")
    candidate = base_name
    suffix = 2
    while candidate in world.factions:
        candidate = f"{base_name} {suffix}"
        suffix += 1
    return candidate


def _next_dynamic_internal_id(world: WorldState) -> str:
    existing_ids = {
        faction.internal_id
        for faction in world.factions.values()
    }
    next_index = 1
    while f"Faction{next_index}" in existing_ids:
        next_index += 1
    return f"Faction{next_index}"


def get_owned_region_counts(world: WorldState) -> dict[str, int]:
    counts = {faction_name: 0 for faction_name in world.factions}
    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1
    return counts


def _find_extinct_ethnic_restoration_faction(
    world: WorldState,
    region: Region,
    former_owner: str,
) -> str | None:
    if region.population <= 0 or not region.ethnic_composition:
        return None

    owned_region_counts = get_owned_region_counts(world)
    ranked_ethnicities = sorted(
        region.ethnic_composition.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    for ethnicity_name, population in ranked_ethnicities:
        if population <= 0:
            continue
        for faction_name, faction in world.factions.items():
            if faction_name == former_owner:
                continue
            if faction.primary_ethnicity != ethnicity_name:
                continue
            if owned_region_counts.get(faction_name, 0) > 0:
                continue
            if faction.is_rebel and faction.proto_state:
                continue
            return faction_name
    return None


def _restore_extinct_faction(
    world: WorldState,
    faction_name: str,
    *,
    former_owner: str,
    region_name: str,
) -> None:
    from src.visibility import inherit_parent_visibility

    faction = world.factions[faction_name]
    faction.treasury = REBEL_STARTING_TREASURY
    faction.starting_treasury = REBEL_STARTING_TREASURY
    faction.proto_state = False
    faction.rebel_age = 0
    faction.independence_score = (
        REBEL_FULL_INDEPENDENCE_THRESHOLD
        if faction.is_rebel
        else 0.0
    )
    if faction.doctrine_state.homeland_region is None:
        faction.doctrine_state.homeland_region = region_name
        faction.doctrine_state.homeland_climate = world.regions[region_name].climate
        faction.doctrine_state.homeland_terrain_tags = list(world.regions[region_name].terrain_tags)
    if faction.origin_faction is None and faction.is_rebel:
        faction.origin_faction = former_owner
    initialize_faction_succession_state(
        faction,
        parent_faction=world.factions.get(former_owner),
        claimant=faction.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR,
    )
    initialize_faction_religion_state(
        world,
        faction,
        parent_faction=world.factions.get(former_owner),
        region=world.regions.get(region_name),
        claimant=faction.rebel_conflict_type == REBEL_CONFLICT_CIVIL_WAR,
    )
    inherit_parent_visibility(
        world,
        faction_name,
        former_owner,
        extra_region_names=[region_name, *world.regions[region_name].neighbors],
    )


def _find_adjacent_rebel_destination(
    world: WorldState,
    region: Region,
    former_owner: str,
    conflict_type: str,
) -> str | None:
    for neighbor_name in region.neighbors:
        neighbor_owner = world.regions[neighbor_name].owner
        if neighbor_owner is None or neighbor_owner == former_owner:
            continue
        if neighbor_owner not in world.factions:
            continue
        neighbor_faction = world.factions[neighbor_owner]
        if (
            neighbor_faction.is_rebel
            and neighbor_faction.origin_faction == former_owner
            and neighbor_faction.rebel_conflict_type == conflict_type
        ):
            return neighbor_owner
    return None


def _determine_rebel_conflict_type(
    world: WorldState,
    region: Region,
    former_owner: str,
) -> str:
    former_faction = world.factions.get(former_owner)
    if former_faction is None or former_faction.primary_ethnicity is None:
        return REBEL_CONFLICT_SECESSION

    if get_region_dominant_ethnicity(region) != former_faction.primary_ethnicity:
        return REBEL_CONFLICT_SECESSION

    if region.homeland_faction_id == former_owner:
        return REBEL_CONFLICT_CIVIL_WAR

    succession = former_faction.succession
    has_open_succession_fight = (
        succession.succession_crisis_turns > 0
        or float(succession.claimant_pressure or 0.0) >= CIVIL_WAR_CLAIMANT_PRESSURE_THRESHOLD
    )
    if (
        has_open_succession_fight
        and region.core_status in {"core", "homeland"}
        and get_region_ruling_ethnic_affinity(region, world) >= CIVIL_WAR_AFFINITY_THRESHOLD
    ):
        return REBEL_CONFLICT_CIVIL_WAR

    return REBEL_CONFLICT_SECESSION


def _choose_civil_war_successor_structure(
    world: WorldState,
    former_owner: str,
) -> tuple[str, str]:
    former_faction = world.factions.get(former_owner)
    if former_faction is None:
        return "tribe", get_default_government_form("tribe")

    polity_tier = former_faction.polity_tier
    government_form = former_faction.government_form
    successor_form = CIVIL_WAR_SUCCESSOR_FORMS.get((polity_tier, government_form))
    if successor_form in GOVERNMENT_FORMS_BY_TIER.get(polity_tier, ()):
        return polity_tier, successor_form

    for candidate in GOVERNMENT_FORMS_BY_TIER.get(polity_tier, ()):
        if candidate != government_form:
            return polity_tier, candidate
    return polity_tier, get_default_government_form(polity_tier)


def _get_civil_war_display_name(
    culture_name: str,
    polity_tier: str,
    government_form: str,
    fallback_government_type: str,
) -> str:
    regime_label = CIVIL_WAR_REGIME_LABELS.get(
        (polity_tier, government_form),
        fallback_government_type,
    )
    return f"{culture_name} {regime_label}".strip()


def create_rebel_faction(world: WorldState, region: Region, former_owner: str) -> tuple[str, bool]:
    from src.doctrine import initialize_rebel_faction_doctrine
    from src.visibility import inherit_parent_visibility

    restored_faction_name = _find_extinct_ethnic_restoration_faction(
        world,
        region,
        former_owner,
    )
    if restored_faction_name is not None:
        _restore_extinct_faction(
            world,
            restored_faction_name,
            former_owner=former_owner,
            region_name=region.name,
        )
        return restored_faction_name, True

    rebel_name = _build_rebel_faction_name(world, region)
    former_faction = world.factions[former_owner]
    conflict_type = _determine_rebel_conflict_type(world, region, former_owner)
    inherited_ethnicity = former_faction.primary_ethnicity
    parent_language_profile = (
        deepcopy(former_faction.identity.language_profile)
        if former_faction.identity is not None
        else LanguageProfile(family_name=inherited_ethnicity or former_owner)
    )
    if conflict_type == REBEL_CONFLICT_CIVIL_WAR:
        polity_tier, government_form = _choose_civil_war_successor_structure(
            world,
            former_owner,
        )
        culture_name = former_faction.culture_name
        generation_method = "civil_war_claimant"
    else:
        polity_tier, government_form = "state", "council"
        culture_name = _normalize_rebel_name_seed(region.ui_name)
        generation_method = "rebel_secession"
    rebel_identity = FactionIdentity(
        internal_id=_next_dynamic_internal_id(world),
        culture_name=culture_name,
        polity_tier=polity_tier,
        government_form=government_form,
        government_type="Rebels",
        display_name=rebel_name,
        language_profile=parent_language_profile,
        generation_method=generation_method,
        inspirations=[former_owner],
    )
    world.factions[rebel_name] = Faction(
        name=rebel_name,
        treasury=REBEL_STARTING_TREASURY,
        identity=rebel_identity,
        starting_treasury=REBEL_STARTING_TREASURY,
        primary_ethnicity=inherited_ethnicity,
        is_rebel=True,
        origin_faction=former_owner,
        rebel_conflict_type=conflict_type,
        rebel_age=0,
        independence_score=0.0,
        proto_state=True,
    )
    initialize_faction_succession_state(
        world.factions[rebel_name],
        parent_faction=former_faction,
        claimant=conflict_type == REBEL_CONFLICT_CIVIL_WAR,
    )
    initialize_faction_religion_state(
        world,
        world.factions[rebel_name],
        parent_faction=former_faction,
        region=region,
        claimant=conflict_type == REBEL_CONFLICT_CIVIL_WAR,
    )
    initialize_rebel_faction_doctrine(
        world,
        rebel_name,
        former_owner,
        region.name,
    )
    inherit_parent_visibility(
        world,
        rebel_name,
        former_owner,
        extra_region_names=[region.name, *region.neighbors],
    )
    seed_rebel_origin_relationship(world, rebel_name, former_owner)
    return rebel_name, False


def _is_multi_region_rebellion_candidate(
    world: WorldState,
    region: Region,
    former_owner: str,
    conflict_type: str,
) -> bool:
    if region.owner != former_owner:
        return False
    if region.population <= 0:
        return False
    if region.homeland_faction_id == former_owner:
        return False
    if region.secession_cooldown_turns > 0:
        return False
    if _determine_rebel_conflict_type(world, region, former_owner) != conflict_type:
        return False
    return (
        region.unrest_event_level in {"disturbance", "crisis"}
        or region.unrest >= UNREST_MODERATE_THRESHOLD
    )


def _transfer_region_to_rebellion(
    world: WorldState,
    region: Region,
    rebel_faction_name: str,
) -> dict[str, int | str]:
    resources_before = region.resources
    taxable_before = get_region_taxable_value(region, world)
    population_before = region.population
    unrest_before = round(region.unrest, 2)
    apply_region_resource_damage(
        region,
        {
            RESOURCE_GRAIN: 0.08,
            RESOURCE_LIVESTOCK: 0.07,
            RESOURCE_HORSES: 0.06,
            RESOURCE_WILD_FOOD: 0.04,
            RESOURCE_TIMBER: 0.07,
            RESOURCE_COPPER: 0.05,
            RESOURCE_STONE: 0.05,
            RESOURCE_SALT: 0.05,
            RESOURCE_TEXTILES: 0.06,
        },
    )
    population_loss = apply_region_population_loss(region, POPULATION_SECESSION_LOSS)
    region.owner = rebel_faction_name
    set_region_integration(
        region,
        owner=rebel_faction_name,
        score=CORE_INTEGRATION_SCORE,
        ownership_turns=1,
        core_status="core",
    )
    set_region_unrest(region, REBEL_STARTING_UNREST)
    clear_region_unrest_event(region)
    reset_region_crisis_streak(region)
    set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
    refresh_region_resource_state(region, world)
    region.resources = max(region.resources, max(1, resources_before - 1))
    return {
        "region": region.name,
        "resource_change": region.resources - resources_before,
        "taxable_change": round(get_region_taxable_value(region, world) - taxable_before, 2),
        "population_before": population_before,
        "population_after": region.population,
        "population_loss": population_loss,
        "unrest_before": unrest_before,
    }


def _collect_multi_region_rebellion_joiners(
    world: WorldState,
    seed_region_name: str,
    former_owner: str,
    conflict_type: str,
) -> list[str]:
    queue = [seed_region_name]
    seen = {seed_region_name}
    joined_regions: list[str] = []

    while queue:
        region_name = queue.pop(0)
        region = world.regions[region_name]
        for neighbor_name in region.neighbors:
            if neighbor_name in seen:
                continue
            seen.add(neighbor_name)
            neighbor = world.regions[neighbor_name]
            if not _is_multi_region_rebellion_candidate(
                world,
                neighbor,
                former_owner,
                conflict_type,
            ):
                continue
            joined_regions.append(neighbor_name)
            queue.append(neighbor_name)

    return joined_regions


def mature_rebel_faction(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    if not faction.is_rebel or not faction.proto_state:
        return

    origin_faction = faction.origin_faction
    conflict_type = faction.rebel_conflict_type or REBEL_CONFLICT_SECESSION
    parent_ethnicity = (
        world.factions[origin_faction].primary_ethnicity
        if origin_faction in world.factions
        else faction.primary_ethnicity
    )
    successor_ethnicity = None
    successor_language_profile = None
    successor_population = 0
    parent_population = 0
    if parent_ethnicity is not None:
        parent_language_profile = (
            deepcopy(world.ethnicities[parent_ethnicity].language_profile)
            if parent_ethnicity in world.ethnicities
            else LanguageProfile(family_name=parent_ethnicity)
        )
        sound_change_labels, sound_changes = _derive_successor_sound_changes(
            parent_language_profile,
            parent_ethnicity,
            faction_name,
            world.turn,
        )
        successor_ethnicity = _generate_successor_ethnicity_name(
            world,
            parent_ethnicity,
            faction_name,
        )
        successor_language_profile = _build_successor_language_profile(
            parent_language_profile,
            successor_ethnicity,
            sound_change_labels,
            sound_changes,
        )
        register_ethnicity(
            world,
            successor_ethnicity,
            language_family=parent_language_profile.family_name or parent_ethnicity,
            parent_ethnicity=parent_ethnicity,
            origin_faction=faction_name,
            language_profile=successor_language_profile,
        )
        successor_population, parent_population = _split_successor_ethnicity_in_regions(
            world,
            faction_name,
            parent_ethnicity,
            successor_ethnicity,
        )
        faction.primary_ethnicity = successor_ethnicity

    faction.proto_state = False
    faction.treasury += REBEL_INDEPENDENCE_TREASURY_BONUS
    if faction.identity is not None:
        if conflict_type == REBEL_CONFLICT_CIVIL_WAR:
            if successor_ethnicity is not None:
                faction.identity.culture_name = successor_ethnicity
                faction.identity.language_profile = deepcopy(successor_language_profile)
            elif origin_faction in world.factions:
                faction.identity.culture_name = world.factions[origin_faction].culture_name
                if world.factions[origin_faction].identity is not None:
                    faction.identity.language_profile = deepcopy(
                        world.factions[origin_faction].identity.language_profile
                    )
            faction.identity.set_government_structure(
                faction.identity.polity_tier,
                faction.identity.government_form,
            )
            faction.identity.display_name = _get_civil_war_display_name(
                faction.identity.culture_name,
                faction.identity.polity_tier,
                faction.identity.government_form,
                faction.identity.government_type,
            )
        else:
            if successor_ethnicity is not None:
                faction.identity.culture_name = successor_ethnicity
                faction.identity.language_profile = deepcopy(successor_language_profile)
            faction.identity.set_government_structure(
                "state",
                "council",
                government_type=REBEL_MATURE_GOVERNMENT_TYPE,
            )
            faction.identity.display_name = faction.identity.culture_name

    world.events.append(Event(
        turn=world.turn,
        type="rebel_independence",
        faction=faction_name,
        details={
            "origin_faction": faction.origin_faction,
            "conflict_type": conflict_type,
            "civil_war": conflict_type == REBEL_CONFLICT_CIVIL_WAR,
            "rebel_age": faction.rebel_age,
            "independence_score": round(faction.independence_score, 2),
            "government_type": faction.government_type,
            "parent_ethnicity": parent_ethnicity,
            "successor_ethnicity": successor_ethnicity,
            "successor_population": successor_population,
            "parent_population": parent_population,
        },
        impact={
            "treasury_after": faction.treasury,
            "treasury_change": REBEL_INDEPENDENCE_TREASURY_BONUS,
            "proto_state": False,
            "primary_ethnicity": faction.primary_ethnicity,
        },
        tags=["rebel", "independence", "statehood", conflict_type],
        significance=faction.independence_score,
    ))


def _update_faction_legitimacy(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    succession = faction.succession
    polity_profile = _get_succession_polity_profile(faction)
    owned_regions = _get_faction_owned_regions(world, faction_name)
    if not owned_regions:
        succession.legitimacy = round(_clamp(float(succession.legitimacy or 0.0), 0.15, 0.95), 3)
        return

    average_unrest = sum(region.unrest for region in owned_regions) / max(1, len(owned_regions))
    prosperity = max(0.0, faction.treasury / max(1.0, len(owned_regions) * 6.0))
    trade_stability = max(0.0, float(faction.trade_income or 0.0) / max(1.0, len(owned_regions) * 2.5))
    legitimacy = float(succession.legitimacy or 0.0)
    legitimacy += min(0.04, prosperity * SUCCESSION_PROSPERITY_LEGITIMACY_GAIN)
    legitimacy += min(0.03, trade_stability * SUCCESSION_TRADE_LEGITIMACY_GAIN)
    prestige_factor = SUCCESSION_PRESTIGE_GAIN_FACTOR
    if faction.government_form == "monarchy":
        prestige_factor *= 1.4
    elif faction.government_form == "republic":
        prestige_factor *= 0.6
    legitimacy += float(succession.dynasty_prestige or 0.0) * prestige_factor
    legitimacy -= average_unrest * SUCCESSION_UNREST_LEGITIMACY_PENALTY
    legitimacy -= max(0.0, float(faction.food_deficit or 0.0)) * SUCCESSION_FOOD_DEFICIT_LEGITIMACY_PENALTY
    realm_penalty = SUCCESSION_REALM_LEGITIMACY_PENALTY
    if faction.polity_tier == "band":
        realm_penalty *= 1.25
    elif faction.polity_tier == "state":
        realm_penalty *= 0.75
    if faction.government_form == "republic":
        legitimacy += 0.015
    legitimacy += float(faction.religion.religious_legitimacy or 0.0) * 0.12
    legitimacy += float(faction.religion.clergy_support or 0.0) * 0.04
    legitimacy -= max(0, len(owned_regions) - 2) * realm_penalty
    if succession.regency_turns > 0:
        legitimacy -= 0.05 if faction.government_form == "monarchy" else 0.02
    if succession.succession_crisis_turns > 0:
        legitimacy -= 0.045 if faction.government_form == "monarchy" else 0.035
    legitimacy += float(polity_profile["legitimacy"]) * 0.08
    succession.legitimacy = round(_clamp(legitimacy, 0.15, 0.95), 3)
    claimant_pressure = float(succession.claimant_pressure or 0.0)
    claimant_pressure += max(0.0, 0.52 - succession.legitimacy) * 0.12
    claimant_pressure -= SUCCESSION_CLAIMANT_PRESSURE_DECAY
    if succession.succession_crisis_turns > 0:
        claimant_pressure += 0.08
    if faction.government_form == "republic":
        claimant_pressure += max(0.0, average_unrest - 2.0) * 0.012
        claimant_pressure += max(0, len(owned_regions) - 2) * 0.01
    elif faction.government_form == "monarchy":
        claimant_pressure += max(0.0, 0.55 - float(succession.dynasty_prestige or 0.0)) * 0.08
    succession.claimant_pressure = round(_clamp(claimant_pressure, 0.0, 1.0), 3)
    succession.dynasty_prestige = round(
        _clamp(
            float(succession.dynasty_prestige or 0.0)
            + min(0.02, prosperity * 0.015)
            - min(0.025, average_unrest * 0.01),
            0.18,
            0.95,
        ),
        3,
    )


def _get_succession_trigger_chance(faction: Faction) -> float:
    ruler_age = int(faction.succession.ruler_age or 0)
    if ruler_age >= SUCCESSION_FORCED_AGE:
        return 1.0
    if ruler_age < SUCCESSION_TRIGGER_AGE:
        return 0.0
    age_ratio = (ruler_age - SUCCESSION_TRIGGER_AGE + 1) / max(1, SUCCESSION_FORCED_AGE - SUCCESSION_TRIGGER_AGE)
    chance = age_ratio * SUCCESSION_MAX_TRIGGER_CHANCE
    if faction.government_form in DYNASTIC_FORMS:
        chance += 0.06
    if faction.succession.succession_crisis_turns > 0:
        chance += 0.08
    return _clamp(chance, 0.0, 1.0)


def _get_next_successor_designate(faction: Faction, new_ruler_name: str) -> tuple[str, int, float]:
    if bool(_get_succession_form_profile(faction).get("adult_successor")):
        adult_min, adult_max = _get_successor_age_range(faction, adult=True)
        preparedness_floor = 0.46 if faction.government_form == "republic" else 0.4
        return (
            _generate_personal_name(faction, seed=new_ruler_name),
            random.randint(adult_min, adult_max),
            round(random.uniform(preparedness_floor, 0.88), 3),
        )
    heir_min, heir_max = _get_successor_age_range(faction)
    return (
        _generate_personal_name(faction, seed=new_ruler_name),
        random.randint(max(2, heir_min // 2), max(18, heir_max)),
        round(random.uniform(0.35, 0.82), 3),
    )


def _apply_succession_unrest(world: WorldState, faction_name: str, severity: float) -> None:
    for region in _get_faction_owned_regions(world, faction_name):
        base = 0.12
        if region.core_status == "homeland":
            base += 0.55
        elif region.core_status == "core":
            base += 0.34
        else:
            base += 0.18
        set_region_unrest(region, region.unrest + (base * severity))


def _resolve_faction_succession(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    succession = faction.succession
    succession.ruler_age += 1
    succession.ruler_reign_turns += 1
    succession.heir_age = max(0, int(succession.heir_age or 0) + 1)
    if succession.regency_turns > 0:
        succession.regency_turns -= 1
    if succession.succession_crisis_turns > 0:
        succession.succession_crisis_turns -= 1

    _update_faction_legitimacy(world, faction_name)
    trigger_chance = _get_succession_trigger_chance(faction)
    if trigger_chance <= 0.0 or random.random() >= trigger_chance:
        return

    owned_regions = _get_faction_owned_regions(world, faction_name)
    average_unrest = (
        sum(region.unrest for region in owned_regions) / max(1, len(owned_regions))
        if owned_regions
        else 0.0
    )
    can_have_regency = _can_have_regency(faction)
    new_ruler_name, heir_age, heir_preparedness = _inherit_successor_heir(faction)
    regency = can_have_regency and heir_age < SUCCESSION_MINOR_HEIR_AGE
    crisis_score = (
        max(0.0, 0.64 - float(succession.legitimacy or 0.0)) * 0.9
        + max(0.0, 0.55 - float(heir_preparedness or 0.0)) * 0.7
        + (average_unrest * 0.06)
        + (max(0, len(owned_regions) - 2) * 0.05)
        + (0.16 if regency else 0.0)
        + (0.1 if faction.government_form == "monarchy" else -0.02 if faction.government_form in {"council", "assembly"} else 0.0)
        + (0.06 if faction.government_form == "republic" else 0.0)
        + (float(succession.claimant_pressure or 0.0) * 0.35)
    )
    crisis_score = _clamp(crisis_score, 0.0, 1.15)
    treasury_before = faction.treasury
    previous_ruler = succession.ruler_name or faction.display_name
    previous_dynasty = succession.dynasty_name or _generate_dynasty_name(faction)
    treasury_hit = SUCCESSION_STABLE_TREASURY_HIT
    succession_type = "orderly"
    claimant_faction = None
    claimant_region = None

    succession.ruler_name = new_ruler_name
    succession.ruler_age = max(SUCCESSION_MINOR_HEIR_AGE, heir_age) if not regency else max(10, heir_age)
    succession.ruler_reign_turns = 0
    if faction.government_form == "republic" and random.random() < _get_dynasty_rotation_chance(
        faction,
        float(succession.claimant_pressure or 0.0),
    ):
        succession.dynasty_name = _generate_dynasty_name(faction)
    heir_designate_name, successor_age, successor_preparedness = _get_next_successor_designate(
        faction,
        new_ruler_name,
    )
    succession.heir_name = heir_designate_name
    succession.heir_age = successor_age
    succession.heir_preparedness = successor_preparedness
    succession.last_succession_turn = world.turn
    succession.last_succession_type = succession_type

    if regency:
        succession.regency_turns = max(succession.regency_turns, SUCCESSION_REGENCY_TURNS)
        succession.legitimacy = round(_clamp(succession.legitimacy - 0.12, 0.12, 0.95), 3)

    if crisis_score >= 0.52:
        succession_type = "crisis"
        succession.succession_crisis_turns = max(
            succession.succession_crisis_turns,
            SUCCESSION_CRISIS_TURNS,
        )
        succession.claimant_pressure = round(
            _clamp(float(succession.claimant_pressure or 0.0) + (crisis_score * 0.35), 0.0, 1.0),
            3,
        )
        succession.legitimacy = round(_clamp(succession.legitimacy - 0.12, 0.1, 0.9), 3)
        treasury_hit = SUCCESSION_CRISIS_TREASURY_HIT
        _apply_succession_unrest(world, faction_name, SUCCESSION_CRISIS_UNREST_PRESSURE + (0.2 if regency else 0.0))

    if regency and succession_type != "crisis":
        succession_type = "regency"
        _apply_succession_unrest(world, faction_name, SUCCESSION_REGENCY_UNREST_PRESSURE)

    if (
        succession_type == "crisis"
        and crisis_score >= SUCCESSION_CLAIMANT_TRIGGER_THRESHOLD
        and len(owned_regions) >= 2
    ):
        claimant_region_obj = _choose_succession_claimant_region(world, faction_name)
        if claimant_region_obj is not None:
            claimant_region_obj.unrest = max(claimant_region_obj.unrest, 9.4)
            claimant_region_obj.unrest_event_level = "crisis"
            claimant_region_obj.unrest_event_turns_remaining = max(
                claimant_region_obj.unrest_event_turns_remaining,
                2,
            )
            claimant_region_obj.secession_cooldown_turns = 0
            apply_unrest_secession(world, claimant_region_obj)
            claimant_faction = claimant_region_obj.owner
            claimant_region = claimant_region_obj.name
            if claimant_faction in world.factions:
                claimant_state = world.factions[claimant_faction].succession
                claimant_state.dynasty_name = previous_dynasty
                claimant_state.ruler_name = _generate_personal_name(world.factions[claimant_faction], seed=previous_ruler)
                claimant_state.legitimacy = round(_clamp(claimant_state.legitimacy + 0.12, 0.2, 0.95), 3)
                claimant_state.claimant_pressure = round(_clamp(claimant_state.claimant_pressure + 0.22, 0.0, 1.0), 3)
                claimant_state.last_succession_type = "claimant"

    succession.last_succession_type = succession_type
    faction.treasury = max(0, faction.treasury - treasury_hit)
    world.events.append(Event(
        turn=world.turn,
        type="succession",
        faction=faction_name,
        details={
            "old_ruler": previous_ruler,
            "new_ruler": succession.ruler_name,
            "dynasty_name": succession.dynasty_name,
            "old_dynasty": previous_dynasty,
            "heir_age": heir_age,
            "regency": regency,
            "succession_type": succession_type,
            "legitimacy": round(succession.legitimacy, 3),
            "claimant_pressure": round(succession.claimant_pressure, 3),
            "claimant_faction": claimant_faction,
            "claimant_region": claimant_region,
        },
        context={
            "treasury_before": treasury_before,
        },
        impact={
            "treasury_after": faction.treasury,
            "treasury_change": faction.treasury - treasury_before,
            "regency_turns": succession.regency_turns,
            "succession_crisis_turns": succession.succession_crisis_turns,
            "claimant_faction": claimant_faction,
        },
        tags=[
            "politics",
            "succession",
            succession_type,
            *(["regency"] if regency else []),
            *(["claimant"] if claimant_faction else []),
        ],
        significance=crisis_score,
    ))

    if succession_type == "crisis":
        world.events.append(Event(
            turn=world.turn,
            type="succession_crisis",
            faction=faction_name,
            region=claimant_region,
            details={
                "new_ruler": succession.ruler_name,
                "dynasty_name": succession.dynasty_name,
                "regency": regency,
                "claimant_faction": claimant_faction,
                "claimant_region": claimant_region,
                "claimant_pressure": round(succession.claimant_pressure, 3),
            },
            impact={
                "treasury_after": faction.treasury,
                "regency_turns": succession.regency_turns,
                "succession_crisis_turns": succession.succession_crisis_turns,
            },
            tags=[
                "politics",
                "succession",
                "crisis",
                *(["claimant"] if claimant_faction else []),
            ],
            significance=crisis_score,
        ))


def resolve_dynastic_succession(world: WorldState) -> None:
    faction_names = sorted(world.factions)
    for faction_name in faction_names:
        faction = world.factions[faction_name]
        if faction.is_rebel or get_owned_region_counts(world).get(faction_name, 0) <= 0:
            continue
        if not faction.succession.dynasty_name or not faction.succession.ruler_name:
            initialize_faction_succession_state(faction)
        if not faction.religion.official_religion:
            homeland_region_name = faction.doctrine_state.homeland_region
            homeland_region = world.regions.get(homeland_region_name) if homeland_region_name else None
            initialize_faction_religion_state(world, faction, region=homeland_region)
        _resolve_faction_succession(world, faction_name)


def get_rebel_reclaim_bonus(
    attacker_faction_name: str,
    defender_faction_name: str | None,
    world: WorldState,
) -> int:
    if defender_faction_name is None or defender_faction_name not in world.factions:
        return 0

    defender_faction = world.factions[defender_faction_name]
    if (
        not defender_faction.is_rebel
        or defender_faction.origin_faction != attacker_faction_name
        or not defender_faction.proto_state
    ):
        return 0

    independence_ratio = min(
        1.0,
        defender_faction.independence_score / max(0.1, REBEL_FULL_INDEPENDENCE_THRESHOLD),
    )
    bonus = int(round(REBEL_PARENT_RECLAIM_MAX_BONUS * (1.0 - independence_ratio)))
    return max(0, bonus)


def update_rebel_faction_status(world: WorldState) -> None:
    owned_region_counts = get_owned_region_counts(world)

    for faction_name, faction in world.factions.items():
        if not faction.is_rebel:
            continue

        owned_regions = owned_region_counts.get(faction_name, 0)
        if owned_regions <= 0:
            continue

        faction.rebel_age += 1
        faction.independence_score = round(
            min(
                REBEL_FULL_INDEPENDENCE_THRESHOLD,
                faction.independence_score
                + REBEL_INDEPENDENCE_PER_TURN
                + max(0, owned_regions - 1) * REBEL_INDEPENDENCE_PER_EXTRA_REGION,
            ),
            2,
        )
        if (
            faction.proto_state
            and faction.independence_score >= REBEL_FULL_INDEPENDENCE_THRESHOLD
        ):
            mature_rebel_faction(world, faction_name)


def initialize_heartlands(world: WorldState) -> None:
    owned_counts: dict[str, int] = {}

    for region_name, region in sorted(world.regions.items()):
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.unrest = 0.0
            clear_region_unrest_event(region)
            reset_region_crisis_streak(region)
            region.ownership_turns = 0
            continue

        owned_count = owned_counts.get(region.owner, 0)
        if owned_count == 0:
            region.homeland_faction_id = region.owner
            set_region_integration(
                region,
                owner=region.owner,
                score=HOMELAND_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="homeland",
            )
        else:
            set_region_integration(
                region,
                owner=region.owner,
                score=CORE_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="core",
            )
        owned_counts[region.owner] = owned_count + 1
        region.unrest = 0.0
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)


def handle_region_owner_change(region: Region, new_owner: str | None) -> None:
    previous_owner = region.owner
    if previous_owner == new_owner:
        return

    region.owner = new_owner
    if previous_owner is not None and new_owner is not None:
        region.conquest_count += 1

    if new_owner is None:
        set_region_integration(
            region,
            owner=None,
            score=0.0,
            ownership_turns=0,
            core_status="frontier",
        )
        set_region_unrest(region, 0.0)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
        return

    base_score = HOMELAND_INTEGRATION_SCORE if region.homeland_faction_id == new_owner else CONQUEST_INTEGRATION_SCORE
    base_status = "homeland" if region.homeland_faction_id == new_owner else "frontier"
    set_region_integration(
        region,
        owner=new_owner,
        score=base_score,
        ownership_turns=1,
        core_status=base_status,
    )
    if region.homeland_faction_id == new_owner:
        set_region_unrest(region, 0.0)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)
    elif previous_owner is None:
        set_region_unrest(region, UNREST_EXPANSION_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
    else:
        set_region_unrest(region, UNREST_CONQUEST_START)
        clear_region_unrest_event(region)
        reset_region_crisis_streak(region)
        set_region_secession_cooldown(region, REBEL_SECESSION_COOLDOWN_TURNS)


def get_region_unrest_pressure(region: Region, world: WorldState) -> float:
    if region.owner is None or region.owner not in world.factions:
        return 0.0
    if region.homeland_faction_id == region.owner:
        return -UNREST_DECAY_PER_TURN

    season_name = get_turn_season_name(world.turn)
    owner_faction = world.factions[region.owner]
    climate_affinity = get_region_climate_affinity(region, world)
    climate_pressure = (1.0 - climate_affinity) * UNREST_CLIMATE_PRESSURE_FACTOR
    integration_gap = max(0.0, CORE_INTEGRATION_SCORE - region.integration_score) / CORE_INTEGRATION_SCORE
    integration_pressure = integration_gap * UNREST_INTEGRATION_PRESSURE_FACTOR
    frontier_pressure = (
        UNREST_FRONTIER_PRESSURE
        if get_region_core_status(region) == "frontier"
        else 0.0
    )
    frontier_burden = (
        get_faction_frontier_burden(world, region.owner)
        * UNREST_FRONTIER_BURDEN_FACTOR
        * get_faction_realm_size_unrest_factor(owner_faction)
    )
    ethnic_pressure = get_region_ethnic_unrest_modifier(region, world)
    regime_pressure = get_region_regime_contestation_unrest_modifier(region, world)
    external_regime_pressure = get_region_external_regime_agitation_modifier(region, world)
    salt_shortage_pressure = min(
        0.65,
        owner_faction.resource_shortages.get(RESOURCE_SALT, 0.0) * 0.12,
    )
    succession_pressure = (
        (owner_faction.succession.succession_crisis_turns * SUCCESSION_CRISIS_UNREST_PRESSURE)
        + (owner_faction.succession.regency_turns * SUCCESSION_REGENCY_UNREST_PRESSURE)
        + (float(owner_faction.succession.claimant_pressure or 0.0) * 0.08)
    )
    religion_pressure = max(
        0.0,
        float(region.religious_unrest or 0.0)
        - (float(owner_faction.religion.religious_tolerance or 0.0) * RELIGION_TOLERANCE_UNREST_REDUCTION),
    )
    administrative_pressure = float(region.administrative_autonomy or 0.0) * ADMIN_UNREST_AUTONOMY_FACTOR
    stability_divisor = max(0.5, get_faction_stability_modifier(owner_faction))
    pressure = (
        climate_pressure
        + integration_pressure
        + frontier_pressure
        + frontier_burden
        + ethnic_pressure
        + regime_pressure
        + external_regime_pressure
        + salt_shortage_pressure
        + succession_pressure
        + religion_pressure
        + administrative_pressure
    ) * get_seasonal_unrest_pressure_modifier(season_name)
    pressure *= get_seasonal_terrain_unrest_multiplier(region, season_name)
    return pressure / stability_divisor - UNREST_DECAY_PER_TURN


def resolve_unrest_events(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            clear_region_unrest_event(region)
            continue
        if region.unrest_event_turns_remaining > 0:
            continue

        if region.unrest >= UNREST_CRITICAL_THRESHOLD:
            set_region_unrest_event(region, level="crisis", duration=UNREST_CRISIS_DURATION)
        elif region.unrest >= UNREST_MODERATE_THRESHOLD:
            set_region_unrest_event(region, level="disturbance", duration=UNREST_DISTURBANCE_DURATION)
        else:
            continue

        _emit_regime_agitation_event(world, region)
        faction = world.factions[region.owner]
        treasury_hit = min(get_region_unrest_event_cost(region), faction.treasury)
        faction.treasury -= treasury_hit
        world.events.append(Event(
            turn=world.turn,
            type=f"unrest_{region.unrest_event_level}",
            faction=region.owner,
            region=region.name,
            details={
                "unrest": round(region.unrest, 2),
                "event_level": region.unrest_event_level,
                "duration": region.unrest_event_turns_remaining,
            },
            impact={
                "treasury_change": -treasury_hit,
                "treasury_after": faction.treasury,
                "integration_stalled": region.unrest_event_level == "crisis",
            },
            tags=["unrest", region.unrest_event_level],
            significance=region.unrest,
        ))


def apply_unrest_secession(world: WorldState, region: Region) -> None:
    if region.owner is None:
        return

    former_owner = region.owner
    conflict_type = _determine_rebel_conflict_type(world, region, former_owner)
    adjacent_rebel = _find_adjacent_rebel_destination(
        world,
        region,
        former_owner,
        conflict_type,
    )
    restored_faction = False
    joined_existing_rebellion = adjacent_rebel is not None
    if adjacent_rebel is not None:
        rebel_faction_name = adjacent_rebel
    else:
        rebel_faction_name, restored_faction = create_rebel_faction(world, region, former_owner)
        if restored_faction:
            conflict_type = "restoration"
        else:
            conflict_type = world.factions[rebel_faction_name].rebel_conflict_type or conflict_type

    seed_transfer = _transfer_region_to_rebellion(world, region, rebel_faction_name)
    joined_region_names = _collect_multi_region_rebellion_joiners(
        world,
        region.name,
        former_owner,
        conflict_type if conflict_type != "restoration" else REBEL_CONFLICT_SECESSION,
    )
    joined_region_transfers = [
        _transfer_region_to_rebellion(world, world.regions[joined_region_name], rebel_faction_name)
        for joined_region_name in joined_region_names
    ]
    total_resource_change = seed_transfer["resource_change"] + sum(
        transfer["resource_change"]
        for transfer in joined_region_transfers
    )
    total_population_before = seed_transfer["population_before"] + sum(
        transfer["population_before"]
        for transfer in joined_region_transfers
    )
    total_population_after = seed_transfer["population_after"] + sum(
        transfer["population_after"]
        for transfer in joined_region_transfers
    )

    world.events.append(Event(
        turn=world.turn,
        type="unrest_secession",
        faction=former_owner,
        region=region.name,
        details={
            "former_owner": former_owner,
            "rebel_faction": rebel_faction_name,
            "conflict_type": conflict_type,
            "civil_war": conflict_type == REBEL_CONFLICT_CIVIL_WAR,
            "restored_faction": rebel_faction_name if restored_faction else None,
            "restoration": restored_faction,
            "joined_existing_rebellion": joined_existing_rebellion,
            "revived_ethnicity": (
                world.factions[rebel_faction_name].primary_ethnicity
                if restored_faction
                else None
            ),
            "restoration_region_count": (
                len(
                    [
                        other_region
                        for other_region in world.regions.values()
                        if (
                            other_region.owner != former_owner
                            and get_region_dominant_ethnicity(other_region)
                            == world.factions[rebel_faction_name].primary_ethnicity
                        )
                    ]
                )
                if restored_faction
                else 0
            ),
            "unrest": seed_transfer["unrest_before"],
            "population_before": seed_transfer["population_before"],
            "population_after": region.population,
            "population_loss": seed_transfer["population_loss"],
            "joined_regions": joined_region_names,
            "joined_region_count": len(joined_region_names),
            "joined_region_population_loss": sum(
                transfer["population_loss"]
                for transfer in joined_region_transfers
            ),
        },
        impact={
            "owner_after": rebel_faction_name,
            "resource_change": total_resource_change,
            "new_resources": region.resources,
            "population_change": total_population_after - total_population_before,
            "population_after": total_population_after,
            "joined_region_count": len(joined_region_names),
        },
        tags=[
            "unrest",
            "secession" if conflict_type != REBEL_CONFLICT_CIVIL_WAR else "civil_war",
            "collapse",
            *(["regional_uprising"] if joined_region_names else []),
            *(["restoration", "revival"] if restored_faction else []),
        ],
        significance=UNREST_SECESSION_THRESHOLD,
    ))


def update_region_integration(world: WorldState, *, time_step_years: float = 1.0) -> None:
    refresh_administrative_state(world)
    for region in world.regions.values():
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.unrest = 0.0
            clear_region_unrest_event(region)
            region.ownership_turns = 0
            reset_region_crisis_streak(region)
            set_region_secession_cooldown(region, 0)
            continue

        if region.secession_cooldown_turns > 0:
            region.secession_cooldown_turns -= 1

        if region.integrated_owner != region.owner:
            handle_region_owner_change(region, region.owner)
            continue

        if region.homeland_faction_id == region.owner:
            region.integration_score = max(region.integration_score, HOMELAND_INTEGRATION_SCORE)
            region.ownership_turns += time_step_years
            region.core_status = "homeland"
            set_region_unrest(region, region.unrest - (UNREST_DECAY_PER_TURN * time_step_years))
            reset_region_crisis_streak(region)
            if region.unrest_event_turns_remaining > 0:
                region.unrest_event_turns_remaining -= 1
                if region.unrest_event_turns_remaining <= 0:
                    clear_region_unrest_event(region)
            continue

        region.ownership_turns += time_step_years
        if region.unrest_event_level == "crisis":
            region.unrest_crisis_streak += 1
            apply_region_population_loss(
                region,
                POPULATION_UNREST_CRISIS_LOSS,
                minimum_loss=1,
            )
        else:
            reset_region_crisis_streak(region)

        if region.unrest_event_level != "crisis":
            climate_modifier = get_region_climate_integration_modifier(region, world)
            ethnic_multiplier = get_region_ethnic_integration_multiplier(region, world)
            government_multiplier = get_faction_integration_modifier(
                world.factions.get(region.owner),
            )
            administrative_multiplier = max(
                0.54,
                0.35
                + (
                    float(world.factions.get(region.owner).administrative_efficiency or 1.0)
                    * ADMIN_INTEGRATION_EFFICIENCY_FACTOR
                )
                + (float(region.administrative_support or 0.0) * ADMIN_INTEGRATION_SUPPORT_FACTOR)
                - (float(region.administrative_autonomy or 0.0) * ADMIN_INTEGRATION_AUTONOMY_FACTOR),
            )
            if region.integration_score < CORE_INTEGRATION_SCORE:
                base_gain = PER_TURN_FRONTIER_GAIN
            else:
                base_gain = PER_TURN_CORE_GAIN
            region.integration_score += max(
                0.0,
                (
                    (base_gain * ethnic_multiplier * government_multiplier * administrative_multiplier)
                    + climate_modifier
                ) * time_step_years,
            )
        region.core_status = get_region_core_status(region)
        set_region_unrest(
            region,
            region.unrest + (get_region_unrest_pressure(region, world) * time_step_years),
        )
        owner_faction = world.factions.get(region.owner)
        if owner_faction is not None and owner_faction.is_rebel:
            if (
                region.unrest_event_level == "crisis"
                and region.unrest_crisis_streak >= UNREST_SECESSION_CRISIS_TURNS
                and region.unrest >= UNREST_SECESSION_THRESHOLD
            ):
                set_region_unrest(
                    region,
                    max(
                        UNREST_CRITICAL_THRESHOLD - 0.5,
                        region.unrest - REBEL_RECURSIVE_UNREST_REDUCTION,
                    ),
                )
                clear_region_unrest_event(region)
                reset_region_crisis_streak(region)
            if region.unrest_event_turns_remaining > 0:
                region.unrest_event_turns_remaining -= 1
                if region.unrest_event_turns_remaining <= 0:
                    clear_region_unrest_event(region)
            continue
        if (
            region.unrest_event_level == "crisis"
            and region.secession_cooldown_turns <= 0
            and region.unrest_crisis_streak >= UNREST_SECESSION_CRISIS_TURNS
            and region.unrest >= UNREST_SECESSION_THRESHOLD
        ):
            apply_unrest_secession(world, region)
            continue
        if region.unrest_event_turns_remaining > 0:
            region.unrest_event_turns_remaining -= 1
            if region.unrest_event_turns_remaining <= 0:
                clear_region_unrest_event(region)


def build_region_snapshot(world: WorldState) -> dict[str, dict]:
    return {
        region_name: {
            "owner": region.owner,
            "resources": region.resources,
            "resource_fixed_endowments": normalize_resource_map(region.resource_fixed_endowments),
            "resource_wild_endowments": normalize_resource_map(region.resource_wild_endowments),
            "resource_suitability": normalize_resource_map(region.resource_suitability),
            "resource_established": normalize_resource_map(region.resource_established),
            "resource_output": normalize_resource_map(region.resource_output),
            "resource_retained_output": normalize_resource_map(region.resource_retained_output),
            "resource_routed_output": normalize_resource_map(region.resource_routed_output),
            "resource_effective_output": normalize_resource_map(region.resource_effective_output),
            "resource_damage": normalize_resource_map(region.resource_damage),
            "resource_monetized_value": round(region.resource_monetized_value, 3),
            "resource_isolation_factor": round(region.resource_isolation_factor, 3),
            "resource_route_depth": region.resource_route_depth,
            "resource_route_cost": round(region.resource_route_cost, 3),
            "resource_route_anchor": region.resource_route_anchor,
            "resource_route_bottleneck": round(region.resource_route_bottleneck, 3),
            "resource_route_mode": region.resource_route_mode,
            "trade_route_role": region.trade_route_role,
            "trade_route_parent": region.trade_route_parent,
            "trade_route_children": region.trade_route_children,
            "trade_served_regions": region.trade_served_regions,
            "trade_throughput": round(region.trade_throughput, 3),
            "trade_transit_flow": round(region.trade_transit_flow, 3),
            "trade_import_value": round(region.trade_import_value, 3),
            "trade_transit_value": round(region.trade_transit_value, 3),
            "trade_hub_value": round(region.trade_hub_value, 3),
            "trade_value_bonus": round(region.trade_value_bonus, 3),
            "trade_import_reliance": round(region.trade_import_reliance, 3),
            "trade_disruption_risk": round(region.trade_disruption_risk, 3),
            "trade_warfare_pressure": round(float(region.trade_warfare_pressure or 0.0), 3),
            "trade_warfare_turns": int(region.trade_warfare_turns or 0),
            "trade_blockade_strength": round(float(region.trade_blockade_strength or 0.0), 3),
            "trade_blockade_turns": int(region.trade_blockade_turns or 0),
            "trade_value_denied": round(float(region.trade_value_denied or 0.0), 3),
            "trade_foreign_partner": region.trade_foreign_partner,
            "trade_foreign_partner_region": region.trade_foreign_partner_region,
            "trade_foreign_flow": round(region.trade_foreign_flow, 3),
            "trade_foreign_value": round(region.trade_foreign_value, 3),
            "trade_gateway_role": region.trade_gateway_role,
            "resource_profile": get_region_resource_summary(
                fixed_endowments=region.resource_fixed_endowments,
                wild_endowments=region.resource_wild_endowments,
                established=region.resource_established,
                output=region.resource_output,
            )["resource_profile"],
            "resource_output_summary": get_region_resource_summary(
                fixed_endowments=region.resource_fixed_endowments,
                wild_endowments=region.resource_wild_endowments,
                established=region.resource_established,
                output=region.resource_effective_output or region.resource_output,
            )["resource_output"],
            "resource_retained_output_summary": get_region_resource_summary(
                output=region.resource_retained_output or region.resource_output,
            )["resource_output"],
            "resource_routed_output_summary": get_region_resource_summary(
                output=region.resource_routed_output or region.resource_effective_output or region.resource_output,
            )["resource_output"],
            "taxable_value": get_region_taxable_value(region, world),
            "infrastructure_level": round(region.infrastructure_level, 2),
            "granary_level": round(region.granary_level, 2),
            "storehouse_level": round(region.storehouse_level, 2),
            "market_level": round(region.market_level, 2),
            "irrigation_level": round(region.irrigation_level, 2),
            "pasture_level": round(region.pasture_level, 2),
            "logging_camp_level": round(region.logging_camp_level, 2),
            "road_level": round(region.road_level, 2),
            "copper_mine_level": round(region.copper_mine_level, 2),
            "stone_quarry_level": round(region.stone_quarry_level, 2),
            "agriculture_level": round(region.agriculture_level, 2),
            "pastoral_level": round(region.pastoral_level, 2),
            "extractive_level": round(region.extractive_level, 2),
            "food_stored": round(region.food_stored, 3),
            "food_storage_capacity": round(region.food_storage_capacity, 3),
            "food_produced": round(region.food_produced, 3),
            "food_consumption": round(region.food_consumption, 3),
            "food_balance": round(region.food_balance, 3),
            "food_deficit": round(region.food_deficit, 3),
            "food_spoilage": round(region.food_spoilage, 3),
            "food_overflow": round(region.food_overflow, 3),
            "migration_inflow": int(region.migration_inflow or 0),
            "migration_outflow": int(region.migration_outflow or 0),
            "refugee_inflow": int(region.refugee_inflow or 0),
            "refugee_outflow": int(region.refugee_outflow or 0),
            "frontier_settler_inflow": int(region.frontier_settler_inflow or 0),
            "migration_pressure": round(float(region.migration_pressure or 0.0), 3),
            "migration_attraction": round(float(region.migration_attraction or 0.0), 3),
            "administrative_burden": round(float(region.administrative_burden or 0.0), 3),
            "administrative_support": round(float(region.administrative_support or 0.0), 3),
            "administrative_distance": round(float(region.administrative_distance or 0.0), 3),
            "administrative_autonomy": round(float(region.administrative_autonomy or 0.0), 3),
            "administrative_tax_capture": round(float(region.administrative_tax_capture or 1.0), 3),
            "population": region.population,
            "productive_capacity": get_region_productive_capacity(region, world),
            "population_pressure": get_region_population_pressure(region),
            "surplus": get_region_surplus(region, world),
            "surplus_label": get_region_surplus_label(region, world),
            "ethnic_composition": dict(region.ethnic_composition),
            "dominant_ethnicity": get_region_dominant_ethnicity(region),
            "religious_composition": dict(region.religious_composition),
            "dominant_religion": get_region_dominant_religion(region),
            "sacred_religion": region.sacred_religion,
            "shrine_level": round(float(region.shrine_level or 0.0), 2),
            "pilgrimage_value": round(float(region.pilgrimage_value or 0.0), 3),
            "religious_unrest": round(float(region.religious_unrest or 0.0), 3),
            "ethnic_claimants": get_region_ethnic_claimants(region, world),
            "owner_primary_ethnicity": get_region_owner_primary_ethnicity(region, world),
            "owner_has_ethnic_claim": faction_has_ethnic_claim(world, region, region.owner),
            "ruling_ethnic_affinity": round(get_region_ruling_ethnic_affinity(region, world), 2),
            "external_regime_agitators": get_region_external_regime_agitators(region, world),
            "external_regime_agitation": round(get_region_external_regime_agitation_modifier(region, world), 3),
            "display_name": region.display_name,
            "founding_name": region.founding_name,
            "original_namer_faction_id": region.original_namer_faction_id,
            "name_metadata": deepcopy(region.name_metadata),
            "terrain_tags": list(region.terrain_tags),
            "climate": region.climate,
            "homeland_faction_id": region.homeland_faction_id,
            "integrated_owner": region.integrated_owner,
            "integration_score": round(region.integration_score, 2),
            "core_status": region.core_status,
            "settlement_level": region.settlement_level,
            "unrest": round(region.unrest, 2),
            "unrest_event_level": region.unrest_event_level,
            "unrest_event_turns_remaining": region.unrest_event_turns_remaining,
            "unrest_crisis_streak": region.unrest_crisis_streak,
        }
        for region_name, region in world.regions.items()
    }


def initialize_region_history(world: WorldState) -> None:
    refresh_administrative_state(world)
    world.region_history = [deepcopy(build_region_snapshot(world))]


def record_region_history(world: WorldState) -> None:
    refresh_administrative_state(world)
    world.region_history.append(deepcopy(build_region_snapshot(world)))
