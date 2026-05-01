from __future__ import annotations

from src.internal_politics import (
    BLOC_GUILDS,
    BLOC_MERCHANT_HOUSES,
    BLOC_MILITARY_ELITES,
    BLOC_NOBLES,
    BLOC_PRIESTHOOD,
    BLOC_PROVINCIAL_GOVERNORS,
    BLOC_TRIBAL_LINEAGES,
    BLOC_URBAN_COMMONS,
    get_bloc,
)
from src.models import Event, Faction, FactionIdeologyState, Region, WorldState
from src.technology import (
    TECH_MARKET_ACCOUNTING,
    TECH_ORGANIZED_LEVIES,
    TECH_ROAD_ADMINISTRATION,
    TECH_TEMPLE_RECORDKEEPING,
    get_faction_institutional_technology,
)
from src.urban import URBAN_FRONTIER_FORT, URBAN_MARKET_TOWN, URBAN_PORT_CITY, URBAN_TEMPLE_CITY


IDEOLOGY_CUSTOMARY_PLURALISM = "customary_pluralism"
IDEOLOGY_IMPERIAL_UNIVERSALISM = "imperial_universalism"
IDEOLOGY_CIVIC_REPUBLICANISM = "civic_republicanism"
IDEOLOGY_LEGALISM = "legalism"
IDEOLOGY_SACRED_KINGSHIP = "sacred_kingship"
IDEOLOGY_MERCHANT_CONSTITUTIONALISM = "merchant_constitutionalism"
IDEOLOGY_REFORM_MOVEMENT = "reform_movement"
IDEOLOGY_ANTI_TAX_PROVINCIALISM = "anti_tax_provincialism"
IDEOLOGY_MILITARY_FRONTIERISM = "military_frontierism"
IDEOLOGY_LINEAGE_TRADITIONALISM = "lineage_traditionalism"

ALL_IDEOLOGIES = (
    IDEOLOGY_IMPERIAL_UNIVERSALISM,
    IDEOLOGY_CIVIC_REPUBLICANISM,
    IDEOLOGY_LEGALISM,
    IDEOLOGY_SACRED_KINGSHIP,
    IDEOLOGY_MERCHANT_CONSTITUTIONALISM,
    IDEOLOGY_REFORM_MOVEMENT,
    IDEOLOGY_ANTI_TAX_PROVINCIALISM,
    IDEOLOGY_MILITARY_FRONTIERISM,
    IDEOLOGY_LINEAGE_TRADITIONALISM,
)

IDEOLOGY_LABELS = {
    IDEOLOGY_CUSTOMARY_PLURALISM: "Customary Pluralism",
    IDEOLOGY_IMPERIAL_UNIVERSALISM: "Imperial Universalism",
    IDEOLOGY_CIVIC_REPUBLICANISM: "Civic Republicanism",
    IDEOLOGY_LEGALISM: "Legalism",
    IDEOLOGY_SACRED_KINGSHIP: "Sacred Kingship",
    IDEOLOGY_MERCHANT_CONSTITUTIONALISM: "Merchant Constitutionalism",
    IDEOLOGY_REFORM_MOVEMENT: "Reform Movement",
    IDEOLOGY_ANTI_TAX_PROVINCIALISM: "Anti-Tax Provincialism",
    IDEOLOGY_MILITARY_FRONTIERISM: "Military Frontierism",
    IDEOLOGY_LINEAGE_TRADITIONALISM: "Lineage Traditionalism",
}

IDEOLOGY_SHIFT_THRESHOLD = 0.46
IDEOLOGY_SHIFT_MARGIN = 0.08


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def format_ideology(ideology_key: str | None) -> str:
    return IDEOLOGY_LABELS.get(ideology_key or "", str(ideology_key or "None").replace("_", " ").title())


def _owned_regions(world: WorldState, faction_name: str) -> list[Region]:
    return [region for region in world.regions.values() if region.owner == faction_name]


def _bloc_support(faction: Faction, bloc_type: str) -> float:
    bloc = get_bloc(faction, bloc_type)
    if bloc is None:
        return 0.0
    return bloc.influence * bloc.loyalty


def _bloc_alienation(faction: Faction, bloc_type: str) -> float:
    bloc = get_bloc(faction, bloc_type)
    if bloc is None:
        return 0.0
    return bloc.influence * max(0.0, 0.56 - bloc.loyalty)


def _bloc_influence(faction: Faction, bloc_type: str) -> float:
    bloc = get_bloc(faction, bloc_type)
    return 0.0 if bloc is None else bloc.influence


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _build_ideology_context(world: WorldState, faction_name: str) -> dict[str, float | int]:
    faction = world.factions[faction_name]
    regions = _owned_regions(world, faction_name)
    region_count = len(regions)
    town_count = sum(1 for region in regions if region.settlement_level == "town")
    city_count = sum(1 for region in regions if region.settlement_level == "city")
    urban_count = town_count + city_count
    frontier_count = sum(1 for region in regions if region.core_status == "frontier")
    port_count = sum(1 for region in regions if region.urban_specialization == URBAN_PORT_CITY)
    market_count = sum(1 for region in regions if region.urban_specialization == URBAN_MARKET_TOWN)
    temple_count = sum(1 for region in regions if region.urban_specialization == URBAN_TEMPLE_CITY)
    fort_count = sum(1 for region in regions if region.urban_specialization == URBAN_FRONTIER_FORT)
    average_autonomy = _average([float(region.administrative_autonomy or 0.0) for region in regions])
    average_tax_capture = _average([float(region.administrative_tax_capture or 1.0) for region in regions]) or 1.0
    average_unrest = _average([float(region.unrest or 0.0) for region in regions])
    trade_strength = (
        float(faction.trade_income or 0.0)
        + float(faction.trade_transit_value or 0.0)
        + float(faction.trade_foreign_income or 0.0)
    )
    institutional_methods = (
        get_faction_institutional_technology(faction, TECH_ROAD_ADMINISTRATION)
        + get_faction_institutional_technology(faction, TECH_TEMPLE_RECORDKEEPING)
        + get_faction_institutional_technology(faction, TECH_MARKET_ACCOUNTING)
        + get_faction_institutional_technology(faction, TECH_ORGANIZED_LEVIES)
    ) / 4
    return {
        "region_count": region_count,
        "town_count": town_count,
        "city_count": city_count,
        "urban_count": urban_count,
        "frontier_count": frontier_count,
        "frontier_share": frontier_count / max(1, region_count),
        "port_count": port_count,
        "market_count": market_count,
        "temple_count": temple_count,
        "fort_count": fort_count,
        "average_autonomy": average_autonomy,
        "average_tax_capture": average_tax_capture,
        "average_unrest": average_unrest,
        "trade_strength": trade_strength,
        "institutional_methods": institutional_methods,
        "urban_network_value": float(faction.urban_network_value or 0.0),
    }


def _score_ideological_currents(world: WorldState, faction_name: str) -> dict[str, float]:
    faction = world.factions[faction_name]
    context = _build_ideology_context(world, faction_name)
    region_count = int(context["region_count"])
    urban_count = int(context["urban_count"])
    frontier_share = float(context["frontier_share"])
    institutional_methods = float(context["institutional_methods"])
    trade_strength = float(context["trade_strength"])
    average_autonomy = float(context["average_autonomy"])
    average_tax_capture = float(context["average_tax_capture"])
    average_unrest = float(context["average_unrest"])

    state_tier = 1.0 if faction.polity_tier == "state" else 0.65 if faction.polity_tier == "chiefdom" else 0.25
    urbanization = _clamp((urban_count * 0.13) + float(context["urban_network_value"]) * 0.04, 0.0, 1.0)
    imperial_scale = _clamp(max(0, region_count - 2) * 0.095 + state_tier * 0.18, 0.0, 1.0)
    trade_factor = _clamp(trade_strength * 0.035 + int(context["port_count"]) * 0.08 + int(context["market_count"]) * 0.06, 0.0, 1.0)
    provincial_strain = _clamp(
        average_autonomy * 0.28
        + max(0.0, 0.72 - average_tax_capture) * 0.8
        + float(faction.administrative_overextension or 0.0) * 0.11
        + frontier_share * 0.18,
        0.0,
        1.0,
    )
    reform_pressure = _clamp(
        float(faction.religion.reform_pressure or 0.0) * 0.32
        + sum(bloc.reform_pressure for bloc in faction.elite_blocs) * 0.22
        + average_unrest * 0.035,
        0.0,
        1.0,
    )

    scores = {
        IDEOLOGY_IMPERIAL_UNIVERSALISM: (
            0.08
            + imperial_scale * 0.42
            + _bloc_support(faction, BLOC_NOBLES) * 0.16
            + _bloc_support(faction, BLOC_PROVINCIAL_GOVERNORS) * 0.14
            + _bloc_support(faction, BLOC_MILITARY_ELITES) * 0.12
            + max(0.0, 0.55 - faction.doctrine_profile.insularity) * 0.12
        ),
        IDEOLOGY_CIVIC_REPUBLICANISM: (
            0.07
            + (0.18 if faction.government_form in {"assembly", "republic", "council"} else 0.0)
            + urbanization * 0.24
            + _bloc_support(faction, BLOC_URBAN_COMMONS) * 0.2
            + _bloc_support(faction, BLOC_GUILDS) * 0.12
            + institutional_methods * 0.1
        ),
        IDEOLOGY_LEGALISM: (
            0.06
            + state_tier * 0.18
            + institutional_methods * 0.24
            + float(faction.administrative_efficiency or 1.0) * 0.1
            + _bloc_support(faction, BLOC_PROVINCIAL_GOVERNORS) * 0.18
            + _bloc_support(faction, BLOC_GUILDS) * 0.08
        ),
        IDEOLOGY_SACRED_KINGSHIP: (
            0.07
            + (0.16 if faction.government_form in {"leader", "monarchy"} else 0.0)
            + float(faction.religion.religious_legitimacy or 0.0) * 0.14
            + float(faction.religion.state_cult_strength or 0.0) * 0.18
            + _bloc_support(faction, BLOC_PRIESTHOOD) * 0.22
            + _bloc_support(faction, BLOC_NOBLES) * 0.1
            + int(context["temple_count"]) * 0.05
        ),
        IDEOLOGY_MERCHANT_CONSTITUTIONALISM: (
            0.05
            + trade_factor * 0.32
            + _bloc_support(faction, BLOC_MERCHANT_HOUSES) * 0.24
            + _bloc_support(faction, BLOC_GUILDS) * 0.12
            + _bloc_support(faction, BLOC_URBAN_COMMONS) * 0.08
            + (0.1 if faction.government_form in {"republic", "oligarchy", "council"} else 0.0)
        ),
        IDEOLOGY_REFORM_MOVEMENT: (
            0.03
            + reform_pressure * 0.44
            + _bloc_alienation(faction, BLOC_PRIESTHOOD) * 0.12
            + _bloc_alienation(faction, BLOC_GUILDS) * 0.12
            + _bloc_alienation(faction, BLOC_URBAN_COMMONS) * 0.14
            + max(0.0, 0.54 - float(faction.succession.legitimacy or 0.0)) * 0.16
        ),
        IDEOLOGY_ANTI_TAX_PROVINCIALISM: (
            0.06
            + provincial_strain * 0.42
            + _bloc_alienation(faction, BLOC_PROVINCIAL_GOVERNORS) * 0.22
            + _bloc_alienation(faction, BLOC_TRIBAL_LINEAGES) * 0.12
            + _bloc_influence(faction, BLOC_PROVINCIAL_GOVERNORS) * max(0.0, average_autonomy - 0.4) * 0.1
        ),
        IDEOLOGY_MILITARY_FRONTIERISM: (
            0.05
            + frontier_share * 0.2
            + int(context["fort_count"]) * 0.08
            + float(faction.doctrine_profile.war_posture or 0.0) * 0.16
            + _bloc_support(faction, BLOC_MILITARY_ELITES) * 0.25
            + _bloc_support(faction, BLOC_TRIBAL_LINEAGES) * 0.08
        ),
        IDEOLOGY_LINEAGE_TRADITIONALISM: (
            0.06
            + (0.2 if faction.polity_tier in {"band", "tribe"} else 0.08 if faction.polity_tier == "chiefdom" else 0.0)
            + (0.1 if faction.government_form in {"leader", "council"} else 0.0)
            + _bloc_support(faction, BLOC_TRIBAL_LINEAGES) * 0.3
            + max(0.0, 0.55 - urbanization) * 0.12
            + max(0.0, 0.55 - institutional_methods) * 0.08
            - provincial_strain * 0.18
        ),
    }
    return {key: round(_clamp(value, 0.0, 1.0), 3) for key, value in scores.items()}


def _choose_dominant_ideology(currents: dict[str, float]) -> str:
    if not currents:
        return IDEOLOGY_CUSTOMARY_PLURALISM
    ranked = sorted(currents.items(), key=lambda item: (-item[1], item[0]))
    leader, leader_score = ranked[0]
    runner_up_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if leader_score < IDEOLOGY_SHIFT_THRESHOLD or leader_score - runner_up_score < IDEOLOGY_SHIFT_MARGIN:
        return IDEOLOGY_CUSTOMARY_PLURALISM
    return leader


def _legitimacy_model(dominant_ideology: str) -> str:
    if dominant_ideology == IDEOLOGY_SACRED_KINGSHIP:
        return "sacred_dynastic"
    if dominant_ideology in {IDEOLOGY_CIVIC_REPUBLICANISM, IDEOLOGY_MERCHANT_CONSTITUTIONALISM}:
        return "civic_institutional"
    if dominant_ideology in {IDEOLOGY_LEGALISM, IDEOLOGY_IMPERIAL_UNIVERSALISM}:
        return "administrative_universal"
    if dominant_ideology in {IDEOLOGY_REFORM_MOVEMENT, IDEOLOGY_ANTI_TAX_PROVINCIALISM}:
        return "contentious_reform"
    if dominant_ideology == IDEOLOGY_MILITARY_FRONTIERISM:
        return "martial_frontier"
    if dominant_ideology == IDEOLOGY_LINEAGE_TRADITIONALISM:
        return "customary_lineage"
    return "customary"


def _build_ideology_state(
    world: WorldState,
    faction_name: str,
    *,
    previous: FactionIdeologyState | None = None,
) -> FactionIdeologyState:
    faction = world.factions[faction_name]
    currents = _score_ideological_currents(world, faction_name)
    dominant = _choose_dominant_ideology(currents)
    ranked_scores = sorted(currents.values(), reverse=True)
    leader_score = ranked_scores[0] if ranked_scores else 0.0
    runner_up_score = ranked_scores[1] if len(ranked_scores) > 1 else 0.0
    reform_pressure = _clamp(
        currents.get(IDEOLOGY_REFORM_MOVEMENT, 0.0) * 0.55
        + currents.get(IDEOLOGY_ANTI_TAX_PROVINCIALISM, 0.0) * 0.35,
        0.0,
        1.0,
    )
    radicalism = _clamp(
        reform_pressure * 0.55
        + sum(max(0.0, 0.5 - bloc.loyalty) * bloc.influence for bloc in faction.elite_blocs) * 0.32,
        0.0,
        1.0,
    )
    institutionalism = _clamp(
        currents.get(IDEOLOGY_LEGALISM, 0.0) * 0.45
        + currents.get(IDEOLOGY_CIVIC_REPUBLICANISM, 0.0) * 0.25
        + currents.get(IDEOLOGY_MERCHANT_CONSTITUTIONALISM, 0.0) * 0.2
        + currents.get(IDEOLOGY_IMPERIAL_UNIVERSALISM, 0.0) * 0.16,
        0.0,
        1.0,
    )
    cohesion = _clamp(0.48 + (leader_score - runner_up_score) * 0.65 - radicalism * 0.22, 0.08, 0.95)
    return FactionIdeologyState(
        dominant_ideology=dominant,
        dominant_label=format_ideology(dominant),
        currents=currents,
        cohesion=round(cohesion, 3),
        radicalism=round(radicalism, 3),
        institutionalism=round(institutionalism, 3),
        reform_pressure=round(reform_pressure, 3),
        legitimacy_model=_legitimacy_model(dominant),
        last_shift_turn=previous.last_shift_turn if previous is not None else None,
    )


def initialize_ideologies(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        faction.ideology = _build_ideology_state(world, faction_name)


def update_ideologies(world: WorldState, *, emit_events: bool = True) -> None:
    for faction_name, faction in world.factions.items():
        previous = faction.ideology
        next_state = _build_ideology_state(world, faction_name, previous=previous)
        previous_dominant = previous.dominant_ideology
        previous_label = previous.dominant_label
        faction.ideology = next_state
        if (
            emit_events
            and previous_dominant != next_state.dominant_ideology
            and next_state.dominant_ideology != IDEOLOGY_CUSTOMARY_PLURALISM
        ):
            faction.ideology.last_shift_turn = world.turn
            world.events.append(Event(
                turn=world.turn,
                type="ideology_shift",
                faction=faction_name,
                details={
                    "previous_ideology": previous_dominant,
                    "previous_label": previous_label,
                    "new_ideology": next_state.dominant_ideology,
                    "new_label": next_state.dominant_label,
                    "cohesion": next_state.cohesion,
                    "radicalism": next_state.radicalism,
                    "reform_pressure": next_state.reform_pressure,
                    "legitimacy_model": next_state.legitimacy_model,
                },
                tags=["politics", "ideology", next_state.dominant_ideology],
                significance=max(0.1, next_state.currents.get(next_state.dominant_ideology, 0.0)),
            ))


def get_faction_ideology_effects(faction: Faction | None) -> dict[str, float]:
    if faction is None:
        return {}
    ideology = faction.ideology
    currents = ideology.currents or {}
    legalism = currents.get(IDEOLOGY_LEGALISM, 0.0)
    civic = currents.get(IDEOLOGY_CIVIC_REPUBLICANISM, 0.0)
    imperial = currents.get(IDEOLOGY_IMPERIAL_UNIVERSALISM, 0.0)
    sacred = currents.get(IDEOLOGY_SACRED_KINGSHIP, 0.0)
    merchant = currents.get(IDEOLOGY_MERCHANT_CONSTITUTIONALISM, 0.0)
    reform = currents.get(IDEOLOGY_REFORM_MOVEMENT, 0.0)
    provincial = currents.get(IDEOLOGY_ANTI_TAX_PROVINCIALISM, 0.0)
    military = currents.get(IDEOLOGY_MILITARY_FRONTIERISM, 0.0)
    lineage = currents.get(IDEOLOGY_LINEAGE_TRADITIONALISM, 0.0)
    cohesion = float(ideology.cohesion or 0.0)
    radicalism = float(ideology.radicalism or 0.0)

    return {
        "income_factor": round(_clamp(merchant * 0.08 + legalism * 0.04 + civic * 0.03 - provincial * 0.05, -0.08, 0.12), 4),
        "trade_income_factor": round(_clamp(merchant * 0.1 + civic * 0.03 - provincial * 0.03, -0.06, 0.14), 4),
        "administrative_capacity_factor": round(_clamp(legalism * 0.11 + imperial * 0.06 + civic * 0.035 - provincial * 0.12 - reform * 0.03, -0.1, 0.16), 4),
        "administrative_reach_factor": round(_clamp(legalism * 0.08 + imperial * 0.07 - provincial * 0.09, -0.1, 0.14), 4),
        "integration_factor": round(_clamp(imperial * 0.08 + legalism * 0.05 + civic * 0.04 - provincial * 0.04, -0.06, 0.14), 4),
        "stability_factor": round(_clamp(sacred * 0.05 + civic * 0.06 + legalism * 0.035 + lineage * 0.03 - radicalism * 0.08, -0.12, 0.12), 4),
        "realm_size_unrest_factor": round(_clamp(1.0 - imperial * 0.12 - legalism * 0.06 + provincial * 0.16 + reform * 0.08, 0.82, 1.22), 4),
        "unrest_pressure": round(_clamp(provincial * 0.08 + reform * 0.07 + max(0.0, 0.42 - cohesion) * 0.12 - civic * 0.035 - legalism * 0.025, -0.04, 0.16), 4),
        "claimant_pressure": round(_clamp(provincial * 0.045 + reform * 0.04 - sacred * 0.035 - lineage * 0.025, -0.04, 0.08), 4),
        "attack_strength_factor": round(_clamp(military * 0.08 + imperial * 0.035 + lineage * 0.025 - merchant * 0.03, -0.05, 0.12), 4),
        "regime_agitation_factor": round(_clamp(reform * 0.18 + provincial * 0.16 + civic * 0.05 + imperial * 0.04 - sacred * 0.04, -0.06, 0.24), 4),
        "diplomatic_affinity_factor": round(_clamp(cohesion * 0.06 + civic * 0.03 + merchant * 0.03 - radicalism * 0.07, -0.08, 0.1), 4),
    }


def get_ideology_distance(faction_a: Faction, faction_b: Faction) -> float:
    keys = set(faction_a.ideology.currents) | set(faction_b.ideology.currents)
    if not keys:
        return 0.0
    return sum(abs(faction_a.ideology.currents.get(key, 0.0) - faction_b.ideology.currents.get(key, 0.0)) for key in keys) / len(keys)


def get_ideological_diplomacy_modifier(faction_a: Faction, faction_b: Faction) -> float:
    distance = get_ideology_distance(faction_a, faction_b)
    modifier = (0.22 - distance) * 2.0
    if faction_a.ideology.dominant_ideology == faction_b.ideology.dominant_ideology:
        modifier += 0.35
    if IDEOLOGY_IMPERIAL_UNIVERSALISM in {faction_a.ideology.dominant_ideology, faction_b.ideology.dominant_ideology}:
        modifier -= 0.12
    if IDEOLOGY_ANTI_TAX_PROVINCIALISM in {faction_a.ideology.dominant_ideology, faction_b.ideology.dominant_ideology}:
        modifier -= 0.1
    return round(_clamp(modifier, -1.25, 1.0), 2)


def factions_have_ideological_regime_tension(faction_a: Faction, faction_b: Faction) -> bool:
    if faction_a.ideology.dominant_ideology == faction_b.ideology.dominant_ideology:
        return False
    if (
        faction_a.ideology.dominant_ideology == IDEOLOGY_CUSTOMARY_PLURALISM
        or faction_b.ideology.dominant_ideology == IDEOLOGY_CUSTOMARY_PLURALISM
    ):
        return get_ideology_distance(faction_a, faction_b) >= 0.2
    return True


def get_faction_ideology_summary(faction: Faction) -> dict[str, object]:
    currents = faction.ideology.currents or {}
    ranked = sorted(currents.items(), key=lambda item: (-item[1], item[0]))
    return {
        "dominant_ideology": faction.ideology.dominant_ideology,
        "dominant_ideology_label": faction.ideology.dominant_label,
        "ideology_cohesion": round(float(faction.ideology.cohesion or 0.0), 3),
        "ideology_radicalism": round(float(faction.ideology.radicalism or 0.0), 3),
        "ideology_institutionalism": round(float(faction.ideology.institutionalism or 0.0), 3),
        "ideology_reform_pressure": round(float(faction.ideology.reform_pressure or 0.0), 3),
        "legitimacy_model": faction.ideology.legitimacy_model,
        "ideology_currents": [
            {
                "ideology": ideology_key,
                "label": format_ideology(ideology_key),
                "strength": round(strength, 3),
            }
            for ideology_key, strength in ranked
        ],
    }
