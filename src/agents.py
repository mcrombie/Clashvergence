import random

from src.actions import (
    develop,
    get_attack_target_score_components,
    get_attackable_regions,
    get_developable_regions,
    get_development_target_score_components,
    expand,
    explore,
    get_expand_target_score_components,
    get_expandable_regions,
    get_explore_target_score_components,
    get_explorable_regions,
)
from src.calendar import get_annual_campaign_modifier, get_annual_dominant_season
from src.climate import get_climate_expansion_modifier
from src.config import (
    ATTACK_COST,
    ATTACK_OVEREXTENSION_MAX_PENALTY,
    ATTACK_OVEREXTENSION_PENALTY_FACTOR,
    DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD,
    DUAL_TRACK_MIN_REGIONS,
    DUAL_TRACK_MILITARY_MIN_UTILITY,
    DUAL_TRACK_OVEREXTENSION_MAX,
    EXPANSION_COST,
    REBEL_PROTO_ATTACK_UTILITY_PENALTY,
    REBEL_PROTO_INVEST_UTILITY_BONUS,
    STANDING_ORDER_EFFICIENCY,
)
from src.diplomacy import (
    demand_tribute,
    get_diplomacy_candidates,
    get_diplomacy_target_score_components,
    get_relationship_status,
    propose_alliance,
    send_envoy,
)
from src.models import StandingOrder
from src.doctrine import OPEN_TERRAIN_TAGS, ROUGH_TERRAIN_TAGS

CHAOS_PIONEER_FRONTIER_PRESSURE_CAP = 0.82   # vs normal 0.52
CHAOS_PIONEER_FRONTIER_PRESSURE_MULT = 1.55
CHAOS_PIONEER_EXPAND_UTILITY_BONUS = 0.18

MILITARY_EXPANSION_ATTACK_BONUS = 0.28
MILITARIST_ISOLATIONIST_ATTACK_BONUS = 0.22
MILITARIST_ISOLATIONIST_EXPAND_PENALTY = 0.24
DEVELOPMENTAL_RELIGIOUS_DEVELOP_BONUS = 0.26
DEVELOPMENTAL_RELIGIOUS_EXPAND_PENALTY = 0.10
MILITARIST_PIONEERS_FRONTIER_PRESSURE_CAP = 0.72
MILITARIST_PIONEERS_FRONTIER_PRESSURE_MULT = 1.4
MILITARIST_PIONEERS_EXPAND_BONUS = 0.14
MILITARIST_PIONEERS_ATTACK_BONUS = 0.22

FRONTIER_PRESSURE_CAP = 0.70
FRONTIER_SETTLEMENT_PRESSURE_START_TURN = 60
FRONTIER_COMPONENT_PRESSURE_CAP = 0.24
FRONTIER_UNCLAIMED_RATIO_PRESSURE_CAP = 0.28
from src.internal_politics import (
    BLOC_ADMIN_PROJECT_BIAS,
    BLOC_PREFERRED_TRACK,
    get_bloc_action_biases,
)
from src.region_state import get_region_core_status
from src.resources import (
    CAPACITY_FOOD_SECURITY,
    CAPACITY_METAL,
    CAPACITY_MOBILITY,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_STONE,
)


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _normalize_expand_score(score):
    return _clamp((score - 5) / 8, 0.0, 1.0)


def _normalize_attack_score(score):
    return _clamp((score - 45) / 30, 0.0, 1.0)


def _normalize_develop_score(score):
    return _clamp(score / 12, 0.0, 1.0)


def _normalize_explore_score(score):
    return _clamp((score - 1) / 8, 0.0, 1.0)


def _get_owned_region_count(faction_name, world):
    return sum(1 for region in world.regions.values() if region.owner == faction_name)


def _get_unowned_region_ratio(world) -> float:
    total_regions = len(world.regions)
    if total_regions <= 0:
        return 0.0
    unowned_regions = sum(1 for region in world.regions.values() if region.owner is None)
    return unowned_regions / total_regions


def _get_frontier_component_pressure(best_expand_components) -> float:
    if not best_expand_components:
        return 0.0
    component_size = int(best_expand_components.get("frontier_component_size", 0) or 0)
    depth_regions = int(best_expand_components.get("frontier_depth_regions", 0) or 0)
    if component_size <= 4 and depth_regions <= 0:
        return 0.0
    return min(
        FRONTIER_COMPONENT_PRESSURE_CAP,
        max(0, component_size - 4) * 0.012 + max(0, depth_regions) * 0.006,
    )


def _get_faction_dominant_season(faction_name, world):
    faction = world.factions[faction_name]
    homeland_region = world.regions.get(faction.doctrine_state.homeland_region or "")
    if homeland_region is not None:
        return get_annual_dominant_season(homeland_region, world)
    owned_region = next(
        (region for region in world.regions.values() if region.owner == faction_name),
        None,
    )
    return get_annual_dominant_season(owned_region, world)


def _get_expansion_personality(faction):
    doctrine = faction.doctrine_profile
    homeland_tags = set(faction.doctrine_state.homeland_terrain_tags or [])
    open_homeland = sum(1 for tag in homeland_tags if tag in OPEN_TERRAIN_TAGS)
    rough_homeland = sum(1 for tag in homeland_tags if tag in ROUGH_TERRAIN_TAGS)
    terrain_count = max(1, open_homeland + rough_homeland)
    open_ratio = open_homeland / terrain_count
    rough_ratio = rough_homeland / terrain_count

    climate_modifier = get_climate_expansion_modifier(faction.doctrine_state.homeland_climate)
    terrain_personality = 0.72 + (open_ratio * 0.42) - (rough_ratio * 0.32) + climate_modifier
    doctrine_personality = (
        0.72
        + (doctrine.expansion_posture * 0.5)
        - (doctrine.insularity * 0.36)
        + (doctrine.war_posture * 0.12)
        - (doctrine.development_posture * 0.08)
    )
    return _clamp(terrain_personality * doctrine_personality, 0.28, 1.45)


def _get_frontier_pressure(
    faction_name,
    world,
    *,
    expandable_regions,
    best_expand_score,
    best_expand_components=None,
):
    if not expandable_regions:
        return 0.0

    faction = world.factions[faction_name]
    owned_region_count = _get_owned_region_count(faction_name, world)
    pressure = 0.0

    if owned_region_count <= 1:
        pressure += 0.18
    elif owned_region_count <= 2:
        pressure += 0.1

    pressure += min(0.12, len(expandable_regions) * 0.018)
    pressure += min(0.14, max(0.0, best_expand_score - 11.0) * 0.014)
    pressure += _get_frontier_component_pressure(best_expand_components)
    if world.turn >= FRONTIER_SETTLEMENT_PRESSURE_START_TURN:
        unowned_ratio = _get_unowned_region_ratio(world)
        late_pressure = min(FRONTIER_UNCLAIMED_RATIO_PRESSURE_CAP, unowned_ratio * 0.55)
        if world.turn >= FRONTIER_SETTLEMENT_PRESSURE_START_TURN * 2:
            late_pressure += min(0.08, unowned_ratio * 0.25)
        pressure += late_pressure

    if faction.treasury >= EXPANSION_COST:
        pressure += 0.06
    if faction.treasury >= EXPANSION_COST * 2:
        pressure += 0.05

    if faction.doctrine_state.expansions <= 0 and owned_region_count <= 2:
        pressure += 0.06

    pressure *= _get_expansion_personality(faction)

    if "chaos_pioneers" in faction.faction_traits:
        return _clamp(pressure * CHAOS_PIONEER_FRONTIER_PRESSURE_MULT, 0.0, CHAOS_PIONEER_FRONTIER_PRESSURE_CAP)
    if "militarist_pioneers" in faction.faction_traits:
        return _clamp(pressure * MILITARIST_PIONEERS_FRONTIER_PRESSURE_MULT, 0.0, MILITARIST_PIONEERS_FRONTIER_PRESSURE_CAP)
    if faction.social_form == "nomadic_tribe":
        return _clamp((pressure * 1.35) + 0.1, 0.0, 0.76)
    return _clamp(pressure, 0.0, FRONTIER_PRESSURE_CAP)


def _get_acute_development_need(faction):
    shortages = faction.resource_shortages
    return (
        shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 0.45
        + shortages.get(CAPACITY_MOBILITY, 0.0) * 0.3
        + shortages.get(CAPACITY_METAL, 0.0) * 0.3
        + faction.food_deficit * 0.35
        + faction.trade_import_dependency * 0.45
        + faction.trade_corridor_exposure * 0.4
    )


def _normalize_action_biases(bloc_biases=None):
    return {
        "attack": float((bloc_biases or {}).get("attack", 0.0)),
        "expand": float((bloc_biases or {}).get("expand", 0.0)),
        "develop": float((bloc_biases or {}).get("develop", 0.0)),
    }


def _get_diplomacy_attack_modifier(attack_components):
    if attack_components is None:
        return 0.0
    diplomacy_status = attack_components.get("diplomacy_status")
    if diplomacy_status == "non_aggression_pact":
        return -0.45
    if diplomacy_status == "overlord":
        return -0.48
    if diplomacy_status == "tributary":
        return -0.36
    if diplomacy_status == "rival":
        return 0.08
    return 0.0


def _get_identity_action_bias(faction, action_name: str) -> float:
    identity = str(getattr(faction, "economic_identity", "") or "").lower()
    if identity == "agricultural":
        if action_name == "develop":
            return 0.07 + min(0.08, faction.resource_shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 0.03)
        if action_name == "attack":
            return -0.04
    elif identity == "pastoral":
        if action_name in {"expand", "attack"}:
            return 0.05
    elif identity == "commercial":
        if action_name == "develop":
            return 0.08
        if action_name == "attack":
            return -0.03
    elif identity == "industrial":
        if action_name == "attack":
            return 0.08
        if action_name == "develop":
            return 0.04
    elif identity == "maritime":
        if action_name in {"expand", "attack"}:
            return 0.05
        if action_name == "develop":
            return 0.03
    elif identity == "imperial":
        if action_name == "develop":
            return 0.05
        if action_name == "expand":
            return 0.03
    return 0.0


def _score_expandable_regions(faction_name, expandable_regions, world):
    if not expandable_regions:
        return (0.0, None, None)
    scored = [
        (score_expand_target_for_faction(r, faction_name, world), r)
        for r in expandable_regions
    ]
    best_score = max(s for s, _ in scored)
    # Allow randomness among near-optimal targets so different seeds produce
    # genuinely different expansion patterns, not always the same deterministic choice.
    threshold = max(1.5, best_score * 0.12)
    near_optimal = [r for s, r in scored if s >= best_score - threshold]
    best_region = random.choice(near_optimal)
    components = get_expand_target_score_components(
        best_region,
        world,
        faction_name=faction_name,
    )
    return (
        components["score"],
        best_region,
        components,
    )


def _score_explorable_regions(faction_name, explorable_regions, world):
    if not explorable_regions:
        return (0.0, None, None)
    best_region = max(
        explorable_regions,
        key=lambda region_name: (
            get_explore_target_score_components(region_name, faction_name, world)["score"],
            region_name,
        ),
    )
    components = get_explore_target_score_components(best_region, faction_name, world)
    return (components["score"], best_region, components)


def _score_attackable_regions(faction_name, attackable_regions, world):
    if not attackable_regions:
        return (0.0, None, None)
    best_region = max(
        attackable_regions,
        key=lambda region_name: (
            score_attack_target(region_name, faction_name, world),
            region_name,
        ),
    )
    components = get_attack_target_score_components(best_region, faction_name, world)
    return (components["score"], best_region, components)


def _get_dominant_admin_agenda(faction):
    admin_blocs = [
        bloc
        for bloc in faction.elite_blocs
        if BLOC_PREFERRED_TRACK.get(bloc.bloc_type) == "admin"
    ]
    if not admin_blocs:
        return ""
    dominant = max(
        admin_blocs,
        key=lambda bloc: (bloc.influence * bloc.loyalty, bloc.bloc_type),
    )
    return BLOC_ADMIN_PROJECT_BIAS.get(dominant.bloc_type, "")


def _get_agenda_region_bonus(region_name, agenda, world):
    region = world.regions[region_name]
    if agenda == "trade":
        return (
            2.0
            if (
                region.market_level >= 0.4
                or region.trade_gateway_role != "none"
                or region.trade_route_role in {"hub", "corridor"}
                or region.trade_foreign_value > 0
            )
            else 0.0
        )
    if agenda == "production":
        return (
            2.0
            if (
                region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0) > 0.25
                or region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0) > 0.25
                or region.resource_output.get(RESOURCE_COPPER, 0.0) > 0
                or region.resource_output.get(RESOURCE_STONE, 0.0) > 0
            )
            else 0.0
        )
    if agenda == "frontier":
        return 2.0 if get_region_core_status(region) == "frontier" else 0.0
    if agenda == "food":
        return (
            2.0
            if (
                region.irrigation_level < 1.0
                and (
                    region.resource_suitability.get(RESOURCE_GRAIN, 0.0) > 0.35
                    or region.resource_established.get(RESOURCE_GRAIN, 0.0) > 0
                    or region.resource_output.get(RESOURCE_GRAIN, 0.0) > 0
                )
            )
            else 0.0
        )
    if agenda == "religious":
        return 2.0 if region.shrine_level <= 0 else 0.0
    return 0.0


def _score_developable_regions(faction_name, developable_regions, world, bloc_biases=None):
    if not developable_regions:
        return (0.0, None, None)

    faction = world.factions[faction_name]
    dominant_agenda = _get_dominant_admin_agenda(faction) if bloc_biases is not None else ""
    best_score = -999.0
    best_region = None
    best_components = None

    for region_name in developable_regions:
        components = get_development_target_score_components(
            region_name,
            faction_name,
            world,
        )
        if not components:
            continue
        score = float(components["score"])
        if dominant_agenda:
            score += _get_agenda_region_bonus(region_name, dominant_agenda, world)
        if best_region is None or (score, region_name) > (best_score, best_region):
            best_score = score
            best_region = region_name
            best_components = components

    return (best_score, best_region, best_components)


def _evaluate_action_utilities(faction_name, world, bloc_biases=None):
    faction = world.factions[faction_name]
    doctrine = faction.doctrine_profile
    is_proto_state = faction.is_rebel and faction.proto_state
    campaign_modifier = get_annual_campaign_modifier(_get_faction_dominant_season(faction_name, world))
    biases = _normalize_action_biases(bloc_biases)

    attackable_regions = get_attackable_regions(faction_name, world)
    expandable_regions = get_expandable_regions(faction_name, world)
    explorable_regions = get_explorable_regions(faction_name, world)
    developable_regions = get_developable_regions(faction_name, world)

    can_attack = bool(attackable_regions) and faction.treasury >= ATTACK_COST
    can_expand = (
        bool(expandable_regions)
        and faction.treasury >= EXPANSION_COST
        and faction.polity_tier != "band"
    )
    can_explore = bool(explorable_regions) and faction.polity_tier != "band"
    can_develop = bool(developable_regions)

    best_attack_target = None
    best_attack_score = 0
    best_attack_components = None
    best_expand_target = None
    best_expand_score = 0
    best_expand_components = None
    best_explore_target = None
    best_explore_score = 0
    best_explore_components = None
    best_develop_target = None
    best_develop_components = None
    action_utilities = {}

    if can_attack:
        best_attack_score, best_attack_target, best_attack_components = _score_attackable_regions(
            faction_name,
            attackable_regions,
            world,
        )

    if can_expand:
        best_expand_score, best_expand_target, best_expand_components = _score_expandable_regions(
            faction_name,
            expandable_regions,
            world,
        )

    if can_explore:
        best_explore_score, best_explore_target, best_explore_components = _score_explorable_regions(
            faction_name,
            explorable_regions,
            world,
        )

    frontier_pressure = _get_frontier_pressure(
        faction_name,
        world,
        expandable_regions=expandable_regions,
        best_expand_score=best_expand_score,
        best_expand_components=best_expand_components,
    )

    acute_development_need = 0.0
    if can_develop:
        best_develop_score, best_develop_target, best_develop_components = _score_developable_regions(
            faction_name,
            developable_regions,
            world,
            bloc_biases=bloc_biases,
        )
    else:
        best_develop_score = 0

    if can_attack:
        attack_utility = (
            _normalize_attack_score(best_attack_score)
            * (0.72 + (doctrine.war_posture * 0.42))
            + (doctrine.expansion_posture * 0.08)
            - (doctrine.insularity * 0.10)
        )
        if faction.treasury <= ATTACK_COST:
            attack_utility -= 0.04
        if is_proto_state:
            attack_utility -= REBEL_PROTO_ATTACK_UTILITY_PENALTY
        attack_utility += _get_diplomacy_attack_modifier(best_attack_components)
        attack_utility += campaign_modifier * 0.7
        attack_utility += _get_identity_action_bias(faction, "attack")
        attack_utility += biases["attack"]
        if "military_expansion" in faction.faction_traits:
            attack_utility += MILITARY_EXPANSION_ATTACK_BONUS
        if "militarist_isolationist" in faction.faction_traits:
            attack_utility += MILITARIST_ISOLATIONIST_ATTACK_BONUS
        if "militarist_pioneers" in faction.faction_traits:
            attack_utility += MILITARIST_PIONEERS_ATTACK_BONUS
        overextension_penalty = float(faction.administrative_overextension_penalty or 0.0)
        attack_utility -= min(
            ATTACK_OVEREXTENSION_MAX_PENALTY,
            overextension_penalty * ATTACK_OVEREXTENSION_PENALTY_FACTOR,
        )
        action_utilities["attack"] = attack_utility

    if can_expand:
        expansion_personality = _get_expansion_personality(faction)
        expand_utility = (
            _normalize_expand_score(best_expand_score)
            * (0.72 + (doctrine.expansion_posture * 0.42))
            * expansion_personality
            + ((1.0 - doctrine.insularity) * 0.08)
            + frontier_pressure
        )
        if faction.treasury >= EXPANSION_COST * 2:
            expand_utility += 0.05
        expand_utility += campaign_modifier * 0.12
        expand_utility += _get_identity_action_bias(faction, "expand")
        expand_utility += biases["expand"]
        if "chaos_pioneers" in faction.faction_traits:
            expand_utility += CHAOS_PIONEER_EXPAND_UTILITY_BONUS
        if faction.social_form == "nomadic_tribe":
            expand_utility += 0.16
        if "militarist_pioneers" in faction.faction_traits:
            expand_utility += MILITARIST_PIONEERS_EXPAND_BONUS
        if "militarist_isolationist" in faction.faction_traits:
            expand_utility -= MILITARIST_ISOLATIONIST_EXPAND_PENALTY
        if "developmental_religious" in faction.faction_traits:
            expand_utility -= DEVELOPMENTAL_RELIGIOUS_EXPAND_PENALTY
        action_utilities["expand"] = expand_utility

    if can_explore:
        explore_utility = (
            _normalize_explore_score(best_explore_score)
            * (0.48 + (doctrine.expansion_posture * 0.24))
            * _get_expansion_personality(faction)
            + ((1.0 - doctrine.insularity) * 0.05)
            + frontier_pressure * 0.25
        )
        if faction.treasury < EXPANSION_COST:
            explore_utility += 0.12
        if can_expand:
            explore_utility -= _normalize_expand_score(best_expand_score) * 0.22
        if "chaos_pioneers" in faction.faction_traits:
            explore_utility += 0.08
        if "militarist_pioneers" in faction.faction_traits:
            explore_utility += 0.06
        if "militarist_isolationist" in faction.faction_traits:
            explore_utility -= 0.08
        action_utilities["explore"] = explore_utility

    if can_develop and best_develop_target is not None:
        acute_development_need = _get_acute_development_need(faction)
        develop_need = acute_development_need + _normalize_develop_score(best_develop_score)
        develop_utility = (
            develop_need * (0.4 + (doctrine.development_posture * 0.32))
            + (doctrine.insularity * 0.14)
            - (doctrine.expansion_posture * 0.06)
        )
        if faction.treasury < EXPANSION_COST:
            develop_utility += 0.03
        elif can_expand and acute_development_need < 0.45:
            develop_utility -= frontier_pressure * 0.4
        if is_proto_state:
            develop_utility += REBEL_PROTO_INVEST_UTILITY_BONUS
        develop_utility += _get_identity_action_bias(faction, "develop")
        develop_utility += biases["develop"]
        if "developmental_religious" in faction.faction_traits:
            develop_utility += DEVELOPMENTAL_RELIGIOUS_DEVELOP_BONUS
        action_utilities["develop"] = develop_utility

    return {
        "utilities": action_utilities,
        "targets": {
            "attack": best_attack_target,
            "expand": best_expand_target,
            "explore": best_explore_target,
            "develop": best_develop_target,
        },
        "components": {
            "attack": best_attack_components or {},
            "expand": best_expand_components or {},
            "explore": best_explore_components or {},
            "develop": best_develop_components or {},
        },
        "pressures": {
            "frontier_pressure": frontier_pressure,
            "acute_development_need": acute_development_need,
        },
        "bloc_biases": biases,
        "can_attack": can_attack,
        "can_expand": can_expand,
        "can_explore": can_explore,
        "can_develop": can_develop,
    }


def _select_single_action(evaluation):
    action_utilities = evaluation["utilities"]
    targets = evaluation["targets"]

    if action_utilities:
        best_action = max(
            action_utilities,
            key=lambda action_name: (action_utilities[action_name], action_name),
        )
        return (best_action, targets[best_action])

    if evaluation["can_expand"]:
        return ("expand", targets["expand"])
    if evaluation["can_explore"]:
        return ("explore", targets["explore"])
    if evaluation["can_develop"]:
        return ("develop", targets["develop"])
    if evaluation["can_attack"]:
        return ("attack", targets["attack"])

    return (None, None)


def _select_dual_track_actions(evaluation):
    military_utilities = {
        action_name: evaluation["utilities"][action_name]
        for action_name in ("attack", "expand", "explore")
        if action_name in evaluation["utilities"]
    }
    actions = []
    if military_utilities:
        military_action = max(
            military_utilities,
            key=lambda action_name: (military_utilities[action_name], action_name),
        )
        if military_utilities[military_action] >= DUAL_TRACK_MILITARY_MIN_UTILITY:
            actions.append((military_action, evaluation["targets"][military_action]))

    develop_utility = evaluation["utilities"].get("develop")
    if develop_utility is not None and develop_utility >= 0.10:
        actions.append(("develop", evaluation["targets"]["develop"]))

    return actions

def score_expand_target(region_name, world):
    """Returns a numeric score representing the strategic value of expanding into a region."""
    return get_expand_target_score_components(region_name, world)["score"]


def score_expand_target_for_faction(region_name, faction_name, world):
    return get_expand_target_score_components(
        region_name,
        world,
        faction_name=faction_name,
    )["score"]

def choose_expand_target(faction_name, world):
    expandable_regions = get_expandable_regions(faction_name, world)

    if not expandable_regions:
        return None

    best_region = max(
        expandable_regions,
        key=lambda region_name: (
            score_expand_target_for_faction(region_name, faction_name, world),
            region_name,
        )
    )

    return best_region

def choose_develop_target(faction_name, world):
    developable_regions = get_developable_regions(faction_name, world)

    if not developable_regions:
        return None

    best_region = max(
        developable_regions,
        key=lambda name: (
            get_development_target_score_components(name, faction_name, world)["score"],
            name,
        )
    )

    return best_region


def score_attack_target(region_name, faction_name, world):
    """Returns a numeric score representing the value of an attack target."""
    return get_attack_target_score_components(region_name, faction_name, world)["score"]


def choose_attack_target(faction_name, world):
    attackable_regions = get_attackable_regions(faction_name, world)

    if not attackable_regions:
        return None

    return max(
        attackable_regions,
        key=lambda region_name: (
            score_attack_target(region_name, faction_name, world),
            region_name,
        )
    )


def choose_action(faction_name, world):
    """Return the single best action for backward-compatible callers."""
    faction = world.factions[faction_name]
    evaluation = _evaluate_action_utilities(
        faction_name,
        world,
        bloc_biases=get_bloc_action_biases(faction),
    )
    return _select_single_action(evaluation)


def _get_diplomacy_track_available(faction_name, world):
    """Return True when the faction qualifies for the diplomacy track this turn."""
    faction = world.factions[faction_name]
    if "diplomacy" in faction.active_projects:
        return False
    return faction.action_capacity >= 3


def _choose_diplomacy_action(faction_name, world, mode=None):
    """Return (action_type, target_faction_name) for the best diplomacy action.

    mode: None = best overall; 'build_alliances'; 'extract_tribute'
    """
    candidates = get_diplomacy_candidates(faction_name, world)
    if not candidates:
        return (None, None)

    if mode == "extract_tribute":
        action_priority = ["demand_tribute", "send_envoy", "propose_alliance"]
    elif mode == "build_alliances":
        action_priority = ["propose_alliance", "send_envoy"]
    else:
        action_priority = ["propose_alliance", "demand_tribute", "send_envoy"]

    best_score = 0.0
    best_target = None
    best_action = None

    for action_type in action_priority:
        for target in candidates:
            components = get_diplomacy_target_score_components(
                faction_name, target, action_type, world
            )
            score = float(components.get("score", -1.0))
            if score > best_score:
                best_score = score
                best_target = target
                best_action = action_type

    return (best_action, best_target)


def get_available_tracks(faction_name, world):
    """Return (military_available, admin_available) for the faction this turn."""
    faction = world.factions[faction_name]
    if faction.proto_state:
        return (True, False)

    owned_count = _get_owned_region_count(faction_name, world)
    if owned_count < DUAL_TRACK_MIN_REGIONS:
        return (True, True)

    admin_efficiency = float(faction.administrative_efficiency or 1.0)
    overextension_penalty = float(faction.administrative_overextension_penalty or 0.0)
    admin_available = (
        admin_efficiency >= DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD
        and overextension_penalty < DUAL_TRACK_OVEREXTENSION_MAX
    )
    return (True, admin_available)


def _choose_military_action(faction_name, world, bloc_biases=None):
    evaluation = _evaluate_action_utilities(faction_name, world, bloc_biases=bloc_biases)
    military_utilities = {
        action_name: evaluation["utilities"][action_name]
        for action_name in ("attack", "expand", "explore")
        if action_name in evaluation["utilities"]
    }
    if not military_utilities:
        return (None, None)
    best_action = max(
        military_utilities,
        key=lambda action_name: (military_utilities[action_name], action_name),
    )
    return (best_action, evaluation["targets"][best_action])


def _choose_admin_action(faction_name, world, bloc_biases=None, *, minimum_utility=None):
    evaluation = _evaluate_action_utilities(faction_name, world, bloc_biases=bloc_biases)
    if "develop" not in evaluation["utilities"]:
        return (None, None)
    develop_utility = evaluation["utilities"]["develop"]
    if minimum_utility is not None and develop_utility < minimum_utility:
        return (None, None)
    return ("develop", evaluation["targets"]["develop"])


_FOOD_PROJECT_TYPES = frozenset({
    "introduce_grain", "build_irrigation", "expand_irrigation",
    "improve_agriculture", "build_granary",
})

_TRADE_PROJECT_TYPES = frozenset({
    "build_market", "expand_market", "build_logistics_node",
    "build_storehouse", "expand_storehouse", "build_road_station", "improve_road",
})


def _pick_standing_order_develop_target(faction_name, mode, world):
    """Return the best develop target given standing order mode, or None if nothing available."""
    developable = get_developable_regions(faction_name, world)
    if not developable:
        return None

    if mode in ("develop_food", "develop_trade"):
        allowed = _FOOD_PROJECT_TYPES if mode == "develop_food" else _TRADE_PROJECT_TYPES
        category_candidates = []
        for region_name in developable:
            components = get_development_target_score_components(region_name, faction_name, world)
            if components and components.get("project_type") in allowed:
                category_candidates.append((float(components["score"]), region_name))
        if category_candidates:
            return max(category_candidates)[1]

    return max(
        developable,
        key=lambda r: (get_development_target_score_components(r, faction_name, world)["score"], r),
    )


def _auto_start_standing_order(faction_name, track, world):
    """Fire a standing order for the given track. Returns True if an action was started."""
    faction = world.factions[faction_name]
    order = faction.standing_orders.get(track)
    if order is None:
        return False

    if track == "admin":
        target = _pick_standing_order_develop_target(faction_name, order.mode, world)
        if target is None:
            return False
        success = develop(faction_name, target, world)
        if success and "admin" in faction.active_projects:
            project = faction.active_projects["admin"]
            project.is_standing_order = True
            project.efficiency = order.efficiency_modifier
        return success

    return False


def _get_standing_order_military_action(faction_name, world, bloc_biases=None):
    """Return (action_name, target) for the military standing order."""
    faction = world.factions[faction_name]
    order = faction.standing_orders.get("military")
    if order is None or order.mode not in ("expand_frontier",):
        return _choose_military_action(faction_name, world, bloc_biases)

    if order.mode == "expand_frontier":
        expandable = get_expandable_regions(faction_name, world)
        if expandable:
            best = max(
                expandable,
                key=lambda r: (
                    get_expand_target_score_components(r, world, faction_name=faction_name)["score"],
                    r,
                ),
            )
            return ("expand", best)

    return _choose_military_action(faction_name, world, bloc_biases)


def choose_standing_orders(faction_name, world):
    """Set faction.standing_orders for each available track at year-end."""
    faction = world.factions[faction_name]
    military_available, admin_available = get_available_tracks(faction_name, world)
    new_orders = {}

    if admin_available:
        food_deficit = float(faction.food_deficit or 0.0) if hasattr(faction, "food_deficit") else 0.0
        economic_identity = str(faction.economic_identity or "")
        if food_deficit > 0.0:
            new_orders["admin"] = StandingOrder(track="admin", mode="develop_food")
        elif economic_identity in ("commercial", "trade", "mercantile"):
            new_orders["admin"] = StandingOrder(track="admin", mode="develop_trade")
        else:
            new_orders["admin"] = StandingOrder(track="admin", mode="develop_priority")

    if military_available:
        expandable = get_expandable_regions(faction_name, world)
        overextension = float(faction.administrative_overextension_penalty or 0.0)
        if overextension > DUAL_TRACK_OVEREXTENSION_MAX * 0.75:
            new_orders["military"] = StandingOrder(track="military", mode="consolidate")
        elif expandable:
            new_orders["military"] = StandingOrder(track="military", mode="expand_frontier")
        else:
            new_orders["military"] = StandingOrder(track="military", mode="patrol")

    # Diplomacy track: available to large empires (capacity 3)
    if _get_diplomacy_track_available(faction_name, world):
        at_war_count = sum(
            1 for name in world.factions
            if name != faction_name
            and get_relationship_status(world, faction_name, name) == "war"
        )
        faction_region_names = {r for r, reg in world.regions.items() if reg.owner == faction_name}
        rival_neighbor_factions = {
            world.regions[n].owner
            for r in faction_region_names
            for n in world.regions[r].neighbors
            if world.regions.get(n) and world.regions[n].owner not in (None, faction_name)
            and get_relationship_status(world, faction_name, world.regions[n].owner) in ("rival", "neutral")
        }
        if at_war_count > 0 or len(rival_neighbor_factions) >= 2:
            new_orders["diplomacy"] = StandingOrder(track="diplomacy", mode="build_alliances")
        else:
            new_orders["diplomacy"] = StandingOrder(track="diplomacy", mode="extract_tribute")

    faction.standing_orders = new_orders


def choose_actions(faction_name, world):
    """Return up to one action per track (military, admin, diplomacy).

    Skips any track that already has an active project in progress.
    Standing orders auto-fire develop on the admin track before deliberate choices.
    Diplomacy track is independent and only available to large empires (capacity >= 3).
    """
    faction = world.factions[faction_name]
    owned_count = _get_owned_region_count(faction_name, world)
    military_available, admin_available = get_available_tracks(faction_name, world)
    diplomacy_available = _get_diplomacy_track_available(faction_name, world)

    admin_track_occupied = "admin" in faction.active_projects
    military_track_occupied = "military" in faction.active_projects

    if admin_track_occupied:
        admin_available = False
    if military_track_occupied:
        military_available = False

    # Auto-fire admin standing order if track is free
    if admin_available and "admin" in faction.standing_orders:
        if _auto_start_standing_order(faction_name, "admin", world):
            admin_available = False
            admin_track_occupied = True

    is_dual = (
        military_available
        and admin_available
        and not faction.proto_state
        and owned_count >= DUAL_TRACK_MIN_REGIONS
    )

    mil_admin_actions = []

    if not is_dual:
        if military_available or admin_available:
            bloc_biases = get_bloc_action_biases(faction)
            if admin_track_occupied:
                if "military" in faction.standing_orders:
                    action_name, target_region_name = _get_standing_order_military_action(
                        faction_name, world, bloc_biases
                    )
                else:
                    action_name, target_region_name = _choose_military_action(faction_name, world, bloc_biases)
                if action_name is not None:
                    mil_admin_actions = [(action_name, target_region_name)]
            else:
                evaluation = _evaluate_action_utilities(faction_name, world, bloc_biases=bloc_biases)
                action_name, target_region_name = _select_single_action(evaluation)
                if action_name is not None and action_name != "skip":
                    mil_admin_actions = [(action_name, target_region_name)]
    else:
        bloc_biases = get_bloc_action_biases(faction)
        evaluation = _evaluate_action_utilities(faction_name, world, bloc_biases=bloc_biases)
        mil_admin_actions = _select_dual_track_actions(evaluation)

        if military_available and "military" in faction.standing_orders:
            standing_military = _get_standing_order_military_action(faction_name, world, bloc_biases)
            if standing_military[0] is not None:
                mil_admin_actions = [a for a in mil_admin_actions if a[0] not in ("attack", "expand", "explore")]
                mil_admin_actions.append(standing_military)

    # Diplomacy track: independent of military/admin, only for large empires
    diplomacy_actions = []
    if diplomacy_available:
        order = faction.standing_orders.get("diplomacy")
        mode = order.mode if isinstance(order, StandingOrder) else None
        diplo_action, diplo_target = _choose_diplomacy_action(faction_name, world, mode=mode)
        if diplo_action is not None:
            diplomacy_actions.append((diplo_action, diplo_target))

    return mil_admin_actions + diplomacy_actions


def evaluate_action_diagnostics(faction_name, world):
    """Return dashboard-only action utility and candidate detail for one faction-turn."""
    faction = world.factions[faction_name]
    owned_count = _get_owned_region_count(faction_name, world)
    military_available, admin_available = get_available_tracks(faction_name, world)
    diplomacy_available = _get_diplomacy_track_available(faction_name, world)
    is_dual = (
        military_available
        and admin_available
        and not faction.proto_state
        and owned_count >= DUAL_TRACK_MIN_REGIONS
    )
    bloc_biases = get_bloc_action_biases(faction)
    evaluation = _evaluate_action_utilities(
        faction_name,
        world,
        bloc_biases=bloc_biases,
    )

    if is_dual:
        selected_actions = _select_dual_track_actions(evaluation)
    else:
        action_name, target_region_name = _select_single_action(evaluation)
        selected_actions = (
            [(action_name, target_region_name)]
            if action_name is not None and action_name != "skip"
            else []
        )

    if diplomacy_available:
        order = faction.standing_orders.get("diplomacy")
        mode = order.mode if isinstance(order, StandingOrder) else None
        diplo_action, diplo_target = _choose_diplomacy_action(faction_name, world, mode=mode)
        if diplo_action is not None:
            selected_actions = list(selected_actions) + [(diplo_action, diplo_target)]

    dominant_admin_agenda = _get_dominant_admin_agenda(faction)
    return {
        "turn": world.turn + 1,
        "faction": faction_name,
        "regions": owned_count,
        "dual_track_qualified": bool(is_dual),
        "military_track_available": bool(military_available),
        "admin_track_available": bool(admin_available),
        "diplomacy_track_available": bool(diplomacy_available),
        "selected_actions": [
            {
                "action": action_name,
                "target": target_region_name,
            }
            for action_name, target_region_name in selected_actions
        ],
        "utilities": {
            action_name: round(float(value), 4)
            for action_name, value in evaluation["utilities"].items()
        },
        "targets": dict(evaluation["targets"]),
        "components": evaluation["components"],
        "pressures": {
            key: round(float(value), 4)
            for key, value in evaluation["pressures"].items()
        },
        "bloc_biases": {
            action_name: round(float(value), 4)
            for action_name, value in evaluation["bloc_biases"].items()
        },
        "dominant_admin_agenda": dominant_admin_agenda,
        "resource_shortages": {
            CAPACITY_FOOD_SECURITY: round(
                float(faction.resource_shortages.get(CAPACITY_FOOD_SECURITY, 0.0) or 0.0),
                4,
            ),
            CAPACITY_MOBILITY: round(
                float(faction.resource_shortages.get(CAPACITY_MOBILITY, 0.0) or 0.0),
                4,
            ),
            CAPACITY_METAL: round(
                float(faction.resource_shortages.get(CAPACITY_METAL, 0.0) or 0.0),
                4,
            ),
        },
    }


def choose_invest_target(faction_name, world):
    """Backward-compatible alias for development target selection."""
    return choose_develop_target(faction_name, world)
