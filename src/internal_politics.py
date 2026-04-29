from __future__ import annotations

from src.models import EliteBloc, Event, Faction, Region, WorldState
from src.region_state import get_region_core_status
from src.resources import PRODUCED_GOOD_TOOLS, PRODUCED_GOOD_URBAN_SURPLUS
from src.urban import (
    URBAN_CRAFT_CENTER,
    URBAN_FRONTIER_FORT,
    URBAN_MARKET_TOWN,
    URBAN_MINING_TOWN,
    URBAN_PORT_CITY,
    URBAN_TEMPLE_CITY,
)

BLOC_NOBLES = "nobles"
BLOC_PRIESTHOOD = "priesthood"
BLOC_MERCHANT_HOUSES = "merchant_houses"
BLOC_MILITARY_ELITES = "military_elites"
BLOC_PROVINCIAL_GOVERNORS = "provincial_governors"
BLOC_TRIBAL_LINEAGES = "tribal_lineages"
BLOC_GUILDS = "guilds"
BLOC_URBAN_COMMONS = "urban_commons"

ALL_ELITE_BLOCS = (
    BLOC_NOBLES,
    BLOC_PRIESTHOOD,
    BLOC_MERCHANT_HOUSES,
    BLOC_MILITARY_ELITES,
    BLOC_PROVINCIAL_GOVERNORS,
    BLOC_TRIBAL_LINEAGES,
    BLOC_GUILDS,
    BLOC_URBAN_COMMONS,
)

ELITE_BLOC_LABELS = {
    BLOC_NOBLES: "Nobles",
    BLOC_PRIESTHOOD: "Priesthood",
    BLOC_MERCHANT_HOUSES: "Merchant Houses",
    BLOC_MILITARY_ELITES: "Military Elites",
    BLOC_PROVINCIAL_GOVERNORS: "Provincial Governors",
    BLOC_TRIBAL_LINEAGES: "Tribal Lineages",
    BLOC_GUILDS: "Guilds",
    BLOC_URBAN_COMMONS: "Urban Commons",
}

ELITE_BLOC_AGENDAS = {
    BLOC_NOBLES: "landed privilege and dynastic continuity",
    BLOC_PRIESTHOOD: "cult authority and sacred legitimacy",
    BLOC_MERCHANT_HOUSES: "secure routes and favorable markets",
    BLOC_MILITARY_ELITES: "prestige, spoils, and frontier command",
    BLOC_PROVINCIAL_GOVERNORS: "regional autonomy and reliable administration",
    BLOC_TRIBAL_LINEAGES: "customary rights and kin authority",
    BLOC_GUILDS: "craft privileges and protected workshops",
    BLOC_URBAN_COMMONS: "food security, taxes, and civic stability",
}

ELITE_BLOC_EVENT_THRESHOLD = 0.68


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def format_elite_bloc(bloc_type: str | None) -> str:
    return ELITE_BLOC_LABELS.get(bloc_type or "", str(bloc_type or "None").replace("_", " ").title())


def _owned_regions(world: WorldState, faction_name: str) -> list[Region]:
    return [region for region in world.regions.values() if region.owner == faction_name]


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _count_regions(regions: list[Region], role: str) -> int:
    return sum(1 for region in regions if region.urban_specialization == role)


def _best_base_region(regions: list[Region], bloc_type: str) -> str | None:
    if not regions:
        return None
    if bloc_type == BLOC_PRIESTHOOD:
        key = lambda region: (
            region.shrine_level + region.pilgrimage_value + (0.4 if region.urban_specialization == URBAN_TEMPLE_CITY else 0.0),
            region.name,
        )
    elif bloc_type == BLOC_MERCHANT_HOUSES:
        key = lambda region: (
            region.trade_foreign_value + region.trade_value_bonus + region.market_level,
            region.name,
        )
    elif bloc_type == BLOC_GUILDS:
        key = lambda region: (
            region.resource_effective_output.get("textiles", 0.0)
            + region.market_level
            + (0.5 if region.urban_specialization == URBAN_CRAFT_CENTER else 0.0),
            region.name,
        )
    elif bloc_type == BLOC_MILITARY_ELITES:
        key = lambda region: (
            region.road_level + (0.5 if region.urban_specialization == URBAN_FRONTIER_FORT else 0.0),
            region.name,
        )
    elif bloc_type == BLOC_PROVINCIAL_GOVERNORS:
        key = lambda region: (
            region.administrative_burden + region.administrative_autonomy,
            region.name,
        )
    else:
        key = lambda region: (
            region.population + (200 if get_region_core_status(region) == "homeland" else 0),
            region.name,
        )
    return max(regions, key=key).name


def _build_elite_context(world: WorldState, faction_name: str) -> dict[str, float | int | list[Region]]:
    faction = world.factions[faction_name]
    regions = _owned_regions(world, faction_name)
    region_count = len(regions)
    frontier_regions = sum(1 for region in regions if get_region_core_status(region) == "frontier")
    core_regions = sum(1 for region in regions if get_region_core_status(region) in {"homeland", "core"})
    city_regions = sum(1 for region in regions if region.settlement_level == "city")
    town_regions = sum(1 for region in regions if region.settlement_level == "town")
    average_unrest = _average([float(region.unrest or 0.0) for region in regions])
    average_autonomy = _average([float(region.administrative_autonomy or 0.0) for region in regions])
    trade_strength = (
        float(faction.trade_income or 0.0)
        + float(faction.trade_transit_value or 0.0)
        + float(faction.trade_foreign_income or 0.0)
    )
    return {
        "regions": regions,
        "region_count": region_count,
        "frontier_regions": frontier_regions,
        "core_regions": core_regions,
        "city_regions": city_regions,
        "town_regions": town_regions,
        "average_unrest": average_unrest,
        "average_autonomy": average_autonomy,
        "trade_strength": trade_strength,
        "port_cities": _count_regions(regions, URBAN_PORT_CITY),
        "market_towns": _count_regions(regions, URBAN_MARKET_TOWN),
        "craft_centers": _count_regions(regions, URBAN_CRAFT_CENTER),
        "temple_cities": _count_regions(regions, URBAN_TEMPLE_CITY),
        "frontier_forts": _count_regions(regions, URBAN_FRONTIER_FORT),
        "mining_towns": _count_regions(regions, URBAN_MINING_TOWN),
        "urban_population": sum(
            region.population
            for region in regions
            if region.settlement_level in {"town", "city"}
        ),
    }


def _target_influence(faction: Faction, context: dict[str, float | int | list[Region]], bloc_type: str) -> float:
    region_count = int(context["region_count"])
    frontier_regions = int(context["frontier_regions"])
    city_regions = int(context["city_regions"])
    town_regions = int(context["town_regions"])
    urban_count = city_regions + town_regions
    trade_strength = float(context["trade_strength"])
    if bloc_type == BLOC_NOBLES:
        return _clamp(
            0.1
            + (0.18 if faction.government_form in {"monarchy", "oligarchy"} else 0.0)
            + (0.12 if faction.polity_tier in {"chiefdom", "state"} else 0.0)
            + min(0.28, int(context["core_regions"]) * 0.045),
            0.0,
            0.9,
        )
    if bloc_type == BLOC_PRIESTHOOD:
        return _clamp(
            0.12
            + (0.14 if faction.religion.official_religion else 0.0)
            + float(faction.religion.clergy_support or 0.0) * 0.24
            + int(context["temple_cities"]) * 0.08,
            0.0,
            0.9,
        )
    if bloc_type == BLOC_MERCHANT_HOUSES:
        return _clamp(
            0.08
            + min(0.32, trade_strength * 0.025)
            + int(context["port_cities"]) * 0.1
            + int(context["market_towns"]) * 0.06,
            0.0,
            0.9,
        )
    if bloc_type == BLOC_MILITARY_ELITES:
        return _clamp(
            0.12
            + float(faction.doctrine_profile.war_posture or 0.0) * 0.18
            + min(0.2, frontier_regions * 0.04)
            + int(context["frontier_forts"]) * 0.08,
            0.0,
            0.9,
        )
    if bloc_type == BLOC_PROVINCIAL_GOVERNORS:
        return _clamp(
            0.05
            + min(0.34, max(0, region_count - 2) * 0.055)
            + frontier_regions * 0.035
            + float(faction.administrative_overextension or 0.0) * 0.12,
            0.0,
            0.9,
        )
    if bloc_type == BLOC_TRIBAL_LINEAGES:
        return _clamp(
            0.12
            + (0.28 if faction.polity_tier in {"band", "tribe"} else 0.1 if faction.polity_tier == "chiefdom" else 0.0)
            + (0.1 if faction.government_form in {"council", "leader"} else 0.0),
            0.0,
            0.85,
        )
    if bloc_type == BLOC_GUILDS:
        produced = faction.produced_goods or {}
        return _clamp(
            0.06
            + int(context["craft_centers"]) * 0.12
            + city_regions * 0.04
            + min(0.2, produced.get(PRODUCED_GOOD_TOOLS, 0.0) * 0.05)
            + min(0.12, produced.get(PRODUCED_GOOD_URBAN_SURPLUS, 0.0) * 0.035),
            0.0,
            0.85,
        )
    if bloc_type == BLOC_URBAN_COMMONS:
        return _clamp(
            0.04
            + urban_count * 0.075
            + min(0.22, int(context["urban_population"]) / 2200.0)
            + float(faction.urban_network_value or 0.0) * 0.035,
            0.0,
            0.85,
        )
    return 0.0


def _target_loyalty(faction: Faction, context: dict[str, float | int | list[Region]], bloc_type: str) -> float:
    legitimacy = float(faction.succession.legitimacy or 0.0)
    religious_legitimacy = float(faction.religion.religious_legitimacy or 0.0)
    admin_efficiency = float(faction.administrative_efficiency or 1.0)
    average_unrest = float(context["average_unrest"])
    overextension = float(faction.administrative_overextension or 0.0)
    food_balance = float(faction.food_balance or 0.0)
    base = 0.43 + legitimacy * 0.18 + religious_legitimacy * 0.08
    if bloc_type == BLOC_NOBLES:
        base += float(faction.succession.dynasty_prestige or 0.0) * 0.18
        base -= float(faction.succession.claimant_pressure or 0.0) * 0.14
    elif bloc_type == BLOC_PRIESTHOOD:
        base += float(faction.religion.clergy_support or 0.0) * 0.25
        base += float(faction.religion.state_cult_strength or 0.0) * 0.08
        base -= float(faction.religion.reform_pressure or 0.0) * 0.08
    elif bloc_type == BLOC_MERCHANT_HOUSES:
        base += min(0.16, float(context["trade_strength"]) * 0.012)
        base -= float(faction.trade_blockade_losses or 0.0) * 0.02
    elif bloc_type == BLOC_MILITARY_ELITES:
        base += float(faction.doctrine_profile.war_posture or 0.0) * 0.12
        base += min(0.08, float(faction.derived_capacity.get("mobility_capacity", 0.0)) * 0.02)
        base -= max(0.0, 0.45 - legitimacy) * 0.12
    elif bloc_type == BLOC_PROVINCIAL_GOVERNORS:
        base += admin_efficiency * 0.12
        base -= overextension * 0.22
        base -= float(context["average_autonomy"]) * 0.1
    elif bloc_type == BLOC_TRIBAL_LINEAGES:
        base += 0.09 if faction.government_form in {"council", "leader"} else -0.03
        base -= 0.08 if faction.polity_tier == "state" else 0.0
    elif bloc_type == BLOC_GUILDS:
        base += min(0.14, float(faction.produced_goods.get(PRODUCED_GOOD_TOOLS, 0.0)) * 0.05)
        base += min(0.08, float(faction.urban_network_value or 0.0) * 0.025)
    elif bloc_type == BLOC_URBAN_COMMONS:
        base += min(0.12, max(-2.0, food_balance) * 0.025)
        base -= max(0.0, average_unrest - 2.0) * 0.04
        base -= max(0.0, 0.75 - float(faction.administrative_reach or 1.0)) * 0.12
    base -= max(0.0, average_unrest - 4.0) * 0.025
    return _clamp(base, 0.05, 0.95)


def _target_wealth(faction: Faction, context: dict[str, float | int | list[Region]], bloc_type: str) -> float:
    trade_strength = float(context["trade_strength"])
    treasury_factor = min(0.18, max(0.0, float(faction.treasury or 0.0)) * 0.01)
    if bloc_type == BLOC_MERCHANT_HOUSES:
        return _clamp(0.28 + min(0.42, trade_strength * 0.025) + treasury_factor, 0.05, 0.95)
    if bloc_type == BLOC_GUILDS:
        return _clamp(0.24 + float(faction.produced_goods.get(PRODUCED_GOOD_TOOLS, 0.0)) * 0.04 + treasury_factor, 0.05, 0.9)
    if bloc_type == BLOC_NOBLES:
        return _clamp(0.26 + int(context["core_regions"]) * 0.04 + treasury_factor, 0.05, 0.9)
    if bloc_type == BLOC_PRIESTHOOD:
        return _clamp(0.2 + float(faction.religion.sacred_sites_controlled or 0) * 0.08 + treasury_factor, 0.05, 0.85)
    return _clamp(0.2 + treasury_factor + _target_influence(faction, context, bloc_type) * 0.22, 0.05, 0.85)


def _target_militarization(faction: Faction, context: dict[str, float | int | list[Region]], bloc_type: str) -> float:
    if bloc_type == BLOC_MILITARY_ELITES:
        return _clamp(0.24 + float(faction.doctrine_profile.war_posture or 0.0) * 0.4 + int(context["frontier_forts"]) * 0.08, 0.0, 0.95)
    if bloc_type == BLOC_PROVINCIAL_GOVERNORS:
        return _clamp(0.08 + int(context["frontier_regions"]) * 0.04 + float(context["average_autonomy"]) * 0.18, 0.0, 0.75)
    if bloc_type == BLOC_NOBLES:
        return _clamp(0.12 + float(faction.succession.claimant_pressure or 0.0) * 0.18, 0.0, 0.65)
    if bloc_type == BLOC_TRIBAL_LINEAGES:
        return _clamp(0.12 + (0.18 if faction.polity_tier in {"band", "tribe"} else 0.04), 0.0, 0.65)
    return 0.0


def _make_bloc(faction: Faction, context: dict[str, float | int | list[Region]], bloc_type: str) -> EliteBloc:
    regions = context["regions"]
    assert isinstance(regions, list)
    label = format_elite_bloc(bloc_type)
    culture = faction.culture_name or faction.name
    return EliteBloc(
        bloc_type=bloc_type,
        name=f"{culture} {label}",
        influence=round(_target_influence(faction, context, bloc_type), 3),
        loyalty=round(_target_loyalty(faction, context, bloc_type), 3),
        wealth=round(_target_wealth(faction, context, bloc_type), 3),
        militarization=round(_target_militarization(faction, context, bloc_type), 3),
        reform_pressure=0.0,
        base_region=_best_base_region(regions, bloc_type),
        agenda=ELITE_BLOC_AGENDAS[bloc_type],
    )


def _desired_bloc_types(faction: Faction, context: dict[str, float | int | list[Region]]) -> list[str]:
    desired = []
    for bloc_type in ALL_ELITE_BLOCS:
        current = get_bloc(faction, bloc_type)
        if (
            _target_influence(faction, context, bloc_type) >= 0.16
            or (current is not None and (current.influence >= 0.18 or current.reform_pressure >= 0.08))
        ):
            desired.append(bloc_type)
    if not desired:
        desired.append(BLOC_TRIBAL_LINEAGES if faction.polity_tier in {"band", "tribe"} else BLOC_NOBLES)
    return desired


def initialize_elite_blocs(world: WorldState) -> None:
    for faction_name, faction in world.factions.items():
        context = _build_elite_context(world, faction_name)
        faction.elite_blocs = [
            _make_bloc(faction, context, bloc_type)
            for bloc_type in _desired_bloc_types(faction, context)
        ]
        _refresh_elite_summary(faction)


def _refresh_elite_summary(faction: Faction) -> None:
    faction.elite_balance = {
        bloc.bloc_type: round(bloc.influence * (bloc.loyalty - 0.5), 3)
        for bloc in faction.elite_blocs
    }
    faction.elite_unrest_pressure = round(
        sum(bloc.influence * max(0.0, 0.5 - bloc.loyalty) * (1.0 + bloc.militarization * 0.6) for bloc in faction.elite_blocs),
        3,
    )
    strongest = max(faction.elite_blocs, key=lambda bloc: (bloc.influence, bloc.bloc_type), default=None)
    alienated = max(
        faction.elite_blocs,
        key=lambda bloc: (bloc.influence * max(0.0, 0.55 - bloc.loyalty), bloc.bloc_type),
        default=None,
    )
    faction.strongest_elite_bloc = strongest.bloc_type if strongest is not None else ""
    faction.alienated_elite_bloc = (
        alienated.bloc_type
        if alienated is not None and alienated.loyalty < 0.5
        else ""
    )


def update_elite_blocs(world: WorldState, *, emit_events: bool = True) -> None:
    for faction_name, faction in world.factions.items():
        context = _build_elite_context(world, faction_name)
        existing = {bloc.bloc_type: bloc for bloc in faction.elite_blocs}
        next_blocs = []
        for bloc_type in _desired_bloc_types(faction, context):
            target = _make_bloc(faction, context, bloc_type)
            current = existing.get(bloc_type)
            if current is None:
                current = target
            previous_loyalty = current.loyalty
            previous_influence = current.influence
            current.name = current.name or target.name
            current.influence = round(_clamp(current.influence * 0.82 + target.influence * 0.18, 0.0, 1.0), 3)
            current.loyalty = round(_clamp(current.loyalty * 0.76 + target.loyalty * 0.24, 0.0, 1.0), 3)
            current.wealth = round(_clamp(current.wealth * 0.82 + target.wealth * 0.18, 0.0, 1.0), 3)
            current.militarization = round(
                _clamp(current.militarization * 0.82 + target.militarization * 0.18, 0.0, 1.0),
                3,
            )
            current.reform_pressure = round(
                _clamp(current.influence * max(0.0, 0.56 - current.loyalty) + max(0.0, current.influence - 0.7) * 0.08, 0.0, 1.0),
                3,
            )
            current.base_region = current.base_region if current.base_region in world.regions else target.base_region
            current.agenda = target.agenda
            if emit_events:
                _maybe_emit_elite_event(world, faction_name, current, previous_influence, previous_loyalty)
            next_blocs.append(current)
        faction.elite_blocs = sorted(next_blocs, key=lambda bloc: (-bloc.influence, bloc.bloc_type))
        _refresh_elite_summary(faction)


def _maybe_emit_elite_event(
    world: WorldState,
    faction_name: str,
    bloc: EliteBloc,
    previous_influence: float,
    previous_loyalty: float,
) -> None:
    if previous_influence < ELITE_BLOC_EVENT_THRESHOLD <= bloc.influence:
        world.events.append(Event(
            turn=world.turn,
            type="elite_bloc_rises",
            faction=faction_name,
            region=bloc.base_region,
            details={
                "bloc_type": bloc.bloc_type,
                "bloc_label": format_elite_bloc(bloc.bloc_type),
                "influence": bloc.influence,
                "loyalty": bloc.loyalty,
            },
            tags=["politics", "elite_bloc", bloc.bloc_type],
            significance=bloc.influence,
        ))
    if previous_loyalty >= 0.42 > bloc.loyalty and bloc.influence >= 0.32:
        world.events.append(Event(
            turn=world.turn,
            type="elite_bloc_alienated",
            faction=faction_name,
            region=bloc.base_region,
            details={
                "bloc_type": bloc.bloc_type,
                "bloc_label": format_elite_bloc(bloc.bloc_type),
                "influence": bloc.influence,
                "loyalty": bloc.loyalty,
                "reform_pressure": bloc.reform_pressure,
            },
            tags=["politics", "elite_bloc", "alienation", bloc.bloc_type],
            significance=bloc.influence * (1.0 - bloc.loyalty),
        ))


def get_bloc(faction: Faction, bloc_type: str) -> EliteBloc | None:
    for bloc in faction.elite_blocs:
        if bloc.bloc_type == bloc_type:
            return bloc
    return None


def _signed_support(bloc: EliteBloc | None) -> float:
    if bloc is None:
        return 0.0
    return bloc.influence * (bloc.loyalty - 0.5)


def _alienation(bloc: EliteBloc | None) -> float:
    if bloc is None:
        return 0.0
    return bloc.influence * max(0.0, 0.52 - bloc.loyalty)


def get_faction_elite_effects(faction: Faction) -> dict[str, float]:
    nobles = get_bloc(faction, BLOC_NOBLES)
    priesthood = get_bloc(faction, BLOC_PRIESTHOOD)
    merchants = get_bloc(faction, BLOC_MERCHANT_HOUSES)
    military = get_bloc(faction, BLOC_MILITARY_ELITES)
    governors = get_bloc(faction, BLOC_PROVINCIAL_GOVERNORS)
    lineages = get_bloc(faction, BLOC_TRIBAL_LINEAGES)
    guilds = get_bloc(faction, BLOC_GUILDS)
    commons = get_bloc(faction, BLOC_URBAN_COMMONS)
    direct_unrest_pressure = sum(
        bloc.influence * max(0.0, 0.5 - bloc.loyalty) * (1.0 + bloc.militarization * 0.6)
        for bloc in faction.elite_blocs
    )
    return {
        "administrative_capacity_factor": round(
            _clamp(
                _signed_support(nobles) * 0.08
                + _signed_support(governors) * 0.14
                + _signed_support(lineages) * 0.04,
                -0.08,
                0.16,
            ),
            4,
        ),
        "administrative_reach_factor": round(_clamp(_signed_support(governors) * 0.12, -0.08, 0.12), 4),
        "trade_income_factor": round(_clamp(_signed_support(merchants) * 0.18 + _signed_support(commons) * 0.04, -0.08, 0.16), 4),
        "tools_output_factor": round(_clamp(_signed_support(guilds) * 0.2 + _signed_support(merchants) * 0.04, -0.05, 0.16), 4),
        "urban_surplus_factor": round(_clamp(_signed_support(guilds) * 0.08 + _signed_support(commons) * 0.12, -0.06, 0.14), 4),
        "religious_legitimacy_factor": round(_clamp(_signed_support(priesthood) * 0.12, -0.08, 0.12), 4),
        "clergy_support_delta": round(_clamp(_signed_support(priesthood) * 0.035, -0.025, 0.03), 4),
        "claimant_pressure": round(
            _clamp(
                _alienation(nobles) * 0.16
                + _alienation(military) * 0.12
                + _alienation(governors) * 0.1,
                0.0,
                0.12,
            ),
            4,
        ),
        "unrest_pressure": round(
            _clamp(max(float(faction.elite_unrest_pressure or 0.0), direct_unrest_pressure), 0.0, 0.45),
            4,
        ),
        "attack_strength_factor": round(_clamp(_signed_support(military) * 0.1 + _signed_support(lineages) * 0.04, -0.06, 0.12), 4),
    }


def get_faction_elite_summary(faction: Faction) -> dict[str, object]:
    return {
        "strongest_elite_bloc": faction.strongest_elite_bloc,
        "strongest_elite_bloc_label": format_elite_bloc(faction.strongest_elite_bloc),
        "alienated_elite_bloc": faction.alienated_elite_bloc,
        "alienated_elite_bloc_label": format_elite_bloc(faction.alienated_elite_bloc) if faction.alienated_elite_bloc else "None",
        "elite_unrest_pressure": round(float(faction.elite_unrest_pressure or 0.0), 3),
        "elite_blocs": [
            {
                "bloc_type": bloc.bloc_type,
                "label": format_elite_bloc(bloc.bloc_type),
                "name": bloc.name,
                "influence": round(bloc.influence, 3),
                "loyalty": round(bloc.loyalty, 3),
                "wealth": round(bloc.wealth, 3),
                "militarization": round(bloc.militarization, 3),
                "reform_pressure": round(bloc.reform_pressure, 3),
                "base_region": bloc.base_region,
                "agenda": bloc.agenda,
            }
            for bloc in faction.elite_blocs
        ],
    }
