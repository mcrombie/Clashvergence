from src.actions import (
    get_attack_target_score_components,
    get_attackable_regions,
    get_developable_regions,
    get_development_target_score_components,
    expand,
    get_expand_target_score_components,
    get_expandable_regions,
)
from src.calendar import get_annual_campaign_modifier, get_annual_dominant_season
from src.climate import get_climate_expansion_modifier
from src.config import (
    ATTACK_COST,
    DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD,
    DUAL_TRACK_MIN_REGIONS,
    EXPANSION_COST,
    REBEL_PROTO_ATTACK_UTILITY_PENALTY,
    REBEL_PROTO_INVEST_UTILITY_BONUS,
)
from src.doctrine import OPEN_TERRAIN_TAGS, ROUGH_TERRAIN_TAGS
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


def _get_owned_region_count(faction_name, world):
    return sum(1 for region in world.regions.values() if region.owner == faction_name)


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

    if faction.treasury >= EXPANSION_COST:
        pressure += 0.06
    if faction.treasury >= EXPANSION_COST * 2:
        pressure += 0.05

    if faction.doctrine_state.expansions <= 0 and owned_region_count <= 2:
        pressure += 0.06

    pressure *= _get_expansion_personality(faction)

    return _clamp(pressure, 0.0, 0.52)


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


def _score_expandable_regions(faction_name, expandable_regions, world):
    if not expandable_regions:
        return (0.0, None)
    best_region = max(
        expandable_regions,
        key=lambda region_name: (
            score_expand_target_for_faction(region_name, faction_name, world),
            region_name,
        ),
    )
    return (
        score_expand_target_for_faction(best_region, faction_name, world),
        best_region,
    )


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
    developable_regions = get_developable_regions(faction_name, world)

    can_attack = bool(attackable_regions) and faction.treasury >= ATTACK_COST
    can_expand = bool(expandable_regions) and faction.treasury >= EXPANSION_COST
    can_develop = bool(developable_regions)

    best_attack_target = None
    best_attack_score = 0
    best_attack_components = None
    best_expand_target = None
    best_expand_score = 0
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
        best_expand_score, best_expand_target = _score_expandable_regions(
            faction_name,
            expandable_regions,
            world,
        )

    frontier_pressure = _get_frontier_pressure(
        faction_name,
        world,
        expandable_regions=expandable_regions,
        best_expand_score=best_expand_score,
    )

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
        attack_utility += biases["attack"]
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
        expand_utility += biases["expand"]
        action_utilities["expand"] = expand_utility

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
        develop_utility += biases["develop"]
        action_utilities["develop"] = develop_utility

    return {
        "utilities": action_utilities,
        "targets": {
            "attack": best_attack_target,
            "expand": best_expand_target,
            "develop": best_develop_target,
        },
        "can_attack": can_attack,
        "can_expand": can_expand,
        "can_develop": can_develop,
    }

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
    if evaluation["can_develop"]:
        return ("develop", targets["develop"])
    if evaluation["can_attack"]:
        return ("attack", targets["attack"])

    return (None, None)


def get_available_tracks(faction_name, world):
    """Return (military_available, admin_available) for the faction this turn."""
    faction = world.factions[faction_name]
    if faction.proto_state:
        return (True, False)

    owned_count = _get_owned_region_count(faction_name, world)
    if owned_count < DUAL_TRACK_MIN_REGIONS:
        return (True, True)

    admin_efficiency = float(faction.administrative_efficiency or 1.0)
    return (
        True,
        admin_efficiency >= DUAL_TRACK_ADMIN_EFFICIENCY_THRESHOLD,
    )


def _choose_military_action(faction_name, world, bloc_biases=None):
    evaluation = _evaluate_action_utilities(faction_name, world, bloc_biases=bloc_biases)
    military_utilities = {
        action_name: evaluation["utilities"][action_name]
        for action_name in ("attack", "expand")
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


def choose_actions(faction_name, world):
    """Return up to one military-track and one admin-track action."""
    faction = world.factions[faction_name]
    owned_count = _get_owned_region_count(faction_name, world)
    military_available, admin_available = get_available_tracks(faction_name, world)
    is_dual = (
        military_available
        and admin_available
        and not faction.proto_state
        and owned_count >= DUAL_TRACK_MIN_REGIONS
    )

    if not is_dual:
        action_name, target_region_name = choose_action(faction_name, world)
        return (
            [(action_name, target_region_name)]
            if action_name is not None and action_name != "skip"
            else []
        )

    bloc_biases = get_bloc_action_biases(faction)
    actions = []
    military_action = _choose_military_action(
        faction_name,
        world,
        bloc_biases=bloc_biases,
    )
    if military_action[0] is not None:
        actions.append(military_action)

    admin_action = _choose_admin_action(
        faction_name,
        world,
        bloc_biases=bloc_biases,
        minimum_utility=0.10,
    )
    if admin_action[0] is not None:
        actions.append(admin_action)

    return actions


def choose_invest_target(faction_name, world):
    """Backward-compatible alias for development target selection."""
    return choose_develop_target(faction_name, world)
