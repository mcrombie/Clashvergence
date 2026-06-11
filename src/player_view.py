from __future__ import annotations

from collections import Counter
from typing import Any

from src.calendar import format_turn_label
from src.diplomacy import get_faction_diplomacy_summary, get_relationship_status
from src.faction_arrivals import is_faction_inactive
from src.map_visualization import build_map_layout, get_map_edges
from src.player_actions import get_available_actions
from src.region_naming import format_region_reference
from src.visibility import (
    faction_knows_faction,
    get_faction_known_regions,
    get_faction_visible_regions,
)


def build_player_view_model(world, faction_name: str) -> dict[str, Any]:
    """Build a limited-visibility view of the world for one playable faction."""
    if faction_name not in world.factions:
        raise ValueError(f"Unknown player faction: {faction_name}")

    faction = world.factions[faction_name]
    known_regions = get_faction_known_regions(world, faction_name)
    visible_regions = get_faction_visible_regions(world, faction_name)
    controlled_regions = {
        region.name
        for region in world.regions.values()
        if region.owner == faction_name
    }
    visible_or_controlled = visible_regions | controlled_regions
    known_or_controlled = known_regions | controlled_regions

    return {
        "turn": world.turn,
        "turn_label": format_turn_label(world.turn),
        "player_faction": _serialize_player_faction(world, faction_name),
        "known_regions": [
            _serialize_player_region(
                world,
                faction_name,
                region_name,
                is_visible=region_name in visible_or_controlled,
                is_controlled=region_name in controlled_regions,
            )
            for region_name in sorted(known_or_controlled)
            if region_name in world.regions
        ],
        "map": _serialize_player_map(world, known_or_controlled),
        "known_factions": [
            _serialize_known_faction(world, faction_name, other_name)
            for other_name in sorted(world.factions)
            if faction_knows_faction(world, faction_name, other_name)
        ],
        "recent_visible_events": _serialize_visible_events(world, faction_name),
        "available_actions": [
            option.to_dict()
            for option in get_available_actions(world, faction_name)
        ],
        "visibility": {
            "known_region_count": len(known_or_controlled),
            "visible_region_count": len(visible_or_controlled),
            "total_region_count": len(world.regions),
        },
        "notes": [
            "This view intentionally hides regions, factions, and exact values outside faction visibility.",
        ],
    }


def _serialize_player_map(world, known_region_names: set[str]) -> dict[str, Any]:
    layout_regions = {
        region_name: {
            "neighbors": list(region.neighbors),
            "owner": region.owner,
            "resources": region.resources,
            "terrain_tags": list(region.terrain_tags or []),
            "climate": region.climate,
        }
        for region_name, region in world.regions.items()
    }
    positions = build_map_layout(layout_regions, width=900, height=900)
    known_regions = {
        region_name
        for region_name in known_region_names
        if region_name in world.regions and region_name in positions
    }
    edges = [
        {"source": first_name, "target": second_name}
        for first_name, second_name in get_map_edges(layout_regions)
        if first_name in known_regions and second_name in known_regions
    ]
    return {
        "width": 900,
        "height": 900,
        "regions": [
            {
                "name": region_name,
                "x": round(float(positions[region_name][0]), 3),
                "y": round(float(positions[region_name][1]), 3),
            }
            for region_name in sorted(known_regions)
        ],
        "edges": edges,
    }


def build_observer_snapshot(world) -> dict[str, Any]:
    """Build a compact omniscient snapshot for incremental non-player runs."""
    active_faction_names = [
        faction_name
        for faction_name in sorted(world.factions)
        if not is_faction_inactive(world, faction_name)
    ]
    owned_regions_by_faction = Counter(
        region.owner
        for region in world.regions.values()
        if region.owner is not None
    )
    owned_regions = sum(owned_regions_by_faction.values())
    total_regions = len(world.regions)
    recent_events = [event.to_dict() for event in world.events[-30:]]

    return {
        "turn": world.turn,
        "turn_label": format_turn_label(world.turn),
        "summary": _serialize_observer_summary(
            world,
            active_faction_names=active_faction_names,
            owned_regions=owned_regions,
            total_regions=total_regions,
        ),
        "factions": [
            _serialize_observer_faction(
                world,
                faction_name,
                owned_region_count=owned_regions_by_faction[faction_name],
            )
            for faction_name in active_faction_names
        ],
        "regions": [
            {
                "name": region.name,
                "display_name": region.display_name or region.name,
                "owner": region.owner,
                "population": region.population,
                "resources": region.resources,
                "unrest": round(float(region.unrest or 0.0), 3),
            }
            for region in sorted(world.regions.values(), key=lambda item: item.name)
        ],
        "recent_events": recent_events,
        "hot_regions": _serialize_hot_regions(world),
        "active_wars": _serialize_active_wars(world),
        "active_shocks": _serialize_active_shocks(world),
    }


def _latest_metrics_for(world, faction_name: str) -> dict[str, Any]:
    if not world.metrics:
        return {}
    latest = world.metrics[-1] or {}
    factions = latest.get("factions", {}) if isinstance(latest, dict) else {}
    return dict(factions.get(faction_name, {}) or {})


def _metric(metrics: dict[str, Any], key: str, fallback: Any = 0) -> Any:
    value = metrics.get(key, fallback)
    return fallback if value is None else value


def _round_float(value: Any, digits: int = 2) -> float:
    try:
        return round(float(value or 0.0), digits)
    except (TypeError, ValueError):
        return 0.0


def _serialize_observer_summary(
    world,
    *,
    active_faction_names: list[str],
    owned_regions: int,
    total_regions: int,
) -> dict[str, Any]:
    relationships = Counter(state.status for state in world.relationships.values())
    active_wars = [
        war
        for war in world.wars.values()
        if war.active
    ]
    owned_region_values = [
        region
        for region in world.regions.values()
        if region.owner is not None
    ]
    high_unrest_regions = [
        region
        for region in owned_region_values
        if float(region.unrest or 0.0) >= 0.65
    ]
    current_turn_events = [
        event
        for event in world.events
        if event.turn in {world.turn, world.turn - 1}
    ]
    return {
        "active_factions": len(active_faction_names),
        "successor_factions": sum(
            1
            for faction_name in active_faction_names
            if world.factions[faction_name].is_rebel
        ),
        "owned_regions": owned_regions,
        "unowned_regions": max(0, total_regions - owned_regions),
        "total_regions": total_regions,
        "total_population": sum(region.population for region in owned_region_values),
        "total_treasury": _round_float(
            sum(world.factions[faction_name].treasury for faction_name in active_faction_names)
        ),
        "average_unrest": _round_float(
            sum(float(region.unrest or 0.0) for region in owned_region_values)
            / max(1, len(owned_region_values)),
            3,
        ),
        "high_unrest_regions": len(high_unrest_regions),
        "active_wars": len(active_wars),
        "active_shocks": len(world.active_shocks),
        "alliances": relationships["alliance"],
        "pacts": relationships["non_aggression_pact"],
        "rivalries": relationships["rival"],
        "tributaries": relationships["tributary"],
        "total_events": len(world.events),
        "recent_events": len(current_turn_events),
    }


def _serialize_observer_faction(
    world,
    faction_name: str,
    *,
    owned_region_count: int,
) -> dict[str, Any]:
    faction = world.factions[faction_name]
    metrics = _latest_metrics_for(world, faction_name)
    diplomacy = get_faction_diplomacy_summary(world, faction_name)
    owned_population = sum(
        region.population
        for region in world.regions.values()
        if region.owner == faction_name
    )
    return {
        "name": faction_name,
        "display_name": faction.display_name,
        "treasury": _round_float(faction.treasury, 3),
        "owned_regions": owned_region_count,
        "population": owned_population,
        "doctrine_label": faction.doctrine_label,
        "government_type": faction.government_type,
        "polity_tier": faction.polity_tier,
        "culture_name": faction.culture_name,
        "is_rebel": faction.is_rebel,
        "origin_faction": faction.origin_faction,
        "economic_identity": _metric(metrics, "economic_identity", faction.economic_identity),
        "economic_identity_secondary": _metric(
            metrics,
            "economic_identity_secondary",
            faction.economic_identity_secondary,
        ),
        "net_income": _round_float(_metric(metrics, "net_income", 0.0), 2),
        "effective_income": _round_float(_metric(metrics, "effective_income", 0.0), 2),
        "maintenance": _round_float(_metric(metrics, "maintenance", 0.0), 2),
        "food_balance": _round_float(_metric(metrics, "food_balance", faction.food_balance), 2),
        "food_stored": _round_float(_metric(metrics, "food_stored", faction.food_stored), 1),
        "food_capacity": _round_float(
            _metric(metrics, "food_storage_capacity", faction.food_storage_capacity),
            1,
        ),
        "administrative_efficiency": _round_float(
            _metric(metrics, "administrative_efficiency", faction.administrative_efficiency),
            3,
        ),
        "administrative_overextension": _round_float(
            _metric(metrics, "administrative_overextension", faction.administrative_overextension),
            3,
        ),
        "capital_region": faction.capital_region,
        "capital_connected_regions": int(_metric(metrics, "capital_connected_regions", faction.capital_connected_regions) or 0),
        "capital_isolated_regions": int(_metric(metrics, "capital_isolated_regions", faction.capital_isolated_regions) or 0),
        "capital_fragment_count": int(_metric(metrics, "capital_fragment_count", faction.capital_fragment_count) or 0),
        "capital_connectivity_penalty": _round_float(
            _metric(metrics, "capital_connectivity_penalty", faction.capital_connectivity_penalty),
            3,
        ),
        "military_readiness": _round_float(
            _metric(metrics, "military_readiness", faction.military_readiness),
            3,
        ),
        "naval_power": _round_float(_metric(metrics, "naval_power", faction.naval_power), 3),
        "army_quality": _round_float(_metric(metrics, "army_quality", faction.army_quality), 3),
        "logistics_radius": _round_float(_metric(metrics, "logistics_radius", faction.logistics_radius), 3),
        "campaign_supply_draw": _round_float(
            _metric(metrics, "campaign_supply_draw", faction.campaign_supply_draw),
            3,
        ),
        "campaign_supply_crisis": _round_float(
            _metric(metrics, "campaign_supply_crisis", faction.campaign_supply_crisis),
            3,
        ),
        "weapons_quality_bonus": _round_float(
            _metric(metrics, "weapons_quality_bonus", faction.weapons_quality_bonus),
            3,
        ),
        "campaign_cost_pressure": _round_float(
            _metric(metrics, "campaign_cost_pressure", faction.campaign_cost_pressure),
            3,
        ),
        "standing_forces": _round_float(
            _metric(metrics, "standing_forces", faction.standing_forces),
            1,
        ),
        "manpower_pool": _round_float(_metric(metrics, "manpower_pool", faction.manpower_pool), 1),
        "shock_exposure": _round_float(_metric(metrics, "shock_exposure", faction.shock_exposure), 3),
        "famine_pressure": _round_float(_metric(metrics, "famine_pressure", faction.famine_pressure), 3),
        "trade_collapse_exposure": _round_float(
            _metric(metrics, "trade_collapse_exposure", faction.trade_collapse_exposure),
            3,
        ),
        "merchant_capacity": _round_float(_metric(metrics, "merchant_capacity", faction.merchant_capacity), 3),
        "iron_access": _round_float(_metric(metrics, "iron_access", 0.0), 3),
        "gold_access": _round_float(_metric(metrics, "gold_access", 0.0), 3),
        "weapons_output": _round_float(_metric(metrics, "weapons_output", 0.0), 3),
        "provisions_output": _round_float(_metric(metrics, "provisions_output", 0.0), 3),
        "crafted_goods_output": _round_float(_metric(metrics, "crafted_goods_output", 0.0), 3),
        "grain_stockpile": _round_float(_metric(metrics, "grain_stockpile", 0.0), 3),
        "copper_stockpile": _round_float(_metric(metrics, "copper_stockpile", 0.0), 3),
        "iron_stockpile": _round_float(_metric(metrics, "iron_stockpile", 0.0), 3),
        "salt_stockpile": _round_float(_metric(metrics, "salt_stockpile", 0.0), 3),
        "technology": _round_float(_metric(metrics, "average_technology_presence", 0.0), 3),
        "institutional_technology": _round_float(
            _metric(metrics, "average_institutional_technology", 0.0),
            3,
        ),
        "seafaring": _round_float(_metric(metrics, "seafaring_level", 0.0), 3),
        "maritime_expansion_reach": int(_metric(metrics, "maritime_expansion_reach", 0) or 0),
        "maritime_attack_reach": int(_metric(metrics, "maritime_attack_reach", 0) or 0),
        "ruler_name": _metric(metrics, "ruler_name", faction.succession.ruler_name),
        "legitimacy": _round_float(_metric(metrics, "legitimacy", faction.succession.legitimacy), 3),
        "top_ally": diplomacy.get("top_ally"),
        "top_rival": diplomacy.get("top_rival"),
        "overlord": diplomacy.get("overlord"),
        "overlord_type": diplomacy.get("overlord_type"),
        "top_tributary": diplomacy.get("top_tributary"),
        "tributary_count": int(diplomacy.get("tributary_count", 0) or 0),
        "alliance_count": int(diplomacy.get("alliance_count", 0) or 0),
        "pact_count": int(diplomacy.get("pact_count", 0) or 0),
        "truce_count": int(diplomacy.get("truce_count", 0) or 0),
        "rival_count": int(diplomacy.get("rival_count", 0) or 0),
        "active_war_count": int(diplomacy.get("active_war_count", 0) or 0),
        "claim_dispute_count": int(diplomacy.get("claim_dispute_count", 0) or 0),
        "war_enemies": list(diplomacy.get("war_enemies", []))[:8],
        "allies": list(diplomacy.get("allies", []))[:8],
        "pacts": list(diplomacy.get("pacts", []))[:8],
        "truces": list(diplomacy.get("truces", []))[:8],
        "rivals": list(diplomacy.get("rivals", []))[:8],
        "tributaries": list(diplomacy.get("tributaries", []))[:8],
        "claim_disputes": list(diplomacy.get("claim_disputes", []))[:8],
    }


def _serialize_hot_regions(world) -> list[dict[str, Any]]:
    hotspots = []
    for region in world.regions.values():
        if region.owner is None:
            continue
        pressure = (
            float(region.unrest or 0.0) * 2.0
            + float(region.trade_warfare_pressure or 0.0)
            + abs(float(region.climate_anomaly or 0.0))
            + float(region.food_deficit or 0.0) / 25.0
            + float(region.shock_exposure or 0.0)
        )
        if pressure <= 0.05:
            continue
        hotspots.append(
            {
                "name": region.name,
                "display_name": region.display_name or region.name,
                "owner": region.owner,
                "population": region.population,
                "unrest": _round_float(region.unrest, 3),
                "food_deficit": _round_float(region.food_deficit, 2),
                "trade_warfare_pressure": _round_float(region.trade_warfare_pressure, 3),
                "climate_anomaly": _round_float(region.climate_anomaly, 3),
                "shock_exposure": _round_float(region.shock_exposure, 3),
                "pressure": _round_float(pressure, 3),
            }
        )
    return sorted(hotspots, key=lambda item: (-item["pressure"], item["display_name"]))[:8]


def _serialize_active_wars(world) -> list[dict[str, Any]]:
    wars = []
    for pair, war in sorted(world.wars.items()):
        if not war.active:
            continue
        first, second = pair
        wars.append(
            {
                "factions": [first, second],
                "aggressor": war.aggressor,
                "defender": war.defender,
                "objective": war.objective_label,
                "target_region": war.target_region,
                "turns_active": war.turns_active,
                "attacks": war.total_attacks,
                "war_exhaustion": _round_float(war.war_exhaustion, 3),
                "score": _round_float(war.aggressor_score - war.defender_score, 2),
            }
        )
    return sorted(wars, key=lambda item: (-item["turns_active"], item["aggressor"]))[:6]


def _serialize_active_shocks(world) -> list[dict[str, Any]]:
    return [
        {
            "kind": shock.kind,
            "origin_region": shock.origin_region,
            "faction": shock.faction,
            "phase": shock.phase,
            "intensity": _round_float(shock.intensity, 3),
            "turns_remaining": max(0, shock.duration_turns - (world.turn - shock.started_turn)),
            "affected_regions": len(shock.affected_regions),
        }
        for shock in sorted(
            world.active_shocks,
            key=lambda item: (-float(item.intensity or 0.0), item.kind),
        )[:6]
    ]


def _serialize_player_faction(world, faction_name: str) -> dict[str, Any]:
    faction = world.factions[faction_name]
    owned_regions = [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]
    return {
        "name": faction_name,
        "display_name": faction.display_name,
        "treasury": round(float(faction.treasury), 3),
        "owned_region_count": len(owned_regions),
        "population": sum(region.population for region in owned_regions),
        "doctrine_label": faction.doctrine_label,
        "government_type": faction.government_type,
        "polity_tier": faction.polity_tier,
        "economic_identity": faction.economic_identity,
        "economic_identity_secondary": faction.economic_identity_secondary,
        "food_stored": round(float(faction.food_stored or 0.0), 3),
        "food_balance": round(float(faction.food_balance or 0.0), 3),
        "manpower_pool": round(float(faction.manpower_pool or 0.0), 3),
        "army_quality": round(float(faction.army_quality or 0.0), 3),
        "logistics_radius": round(float(faction.logistics_radius or 0.0), 3),
        "campaign_supply_draw": round(float(faction.campaign_supply_draw or 0.0), 3),
        "campaign_supply_crisis": round(float(faction.campaign_supply_crisis or 0.0), 3),
        "weapons_quality_bonus": round(float(faction.weapons_quality_bonus or 0.0), 3),
        "campaign_cost_pressure": round(float(faction.campaign_cost_pressure or 0.0), 3),
        "known_regions": list(world.factions[faction_name].known_regions or []),
        "visible_regions": list(world.factions[faction_name].visible_regions or []),
    }


def _serialize_player_region(
    world,
    faction_name: str,
    region_name: str,
    *,
    is_visible: bool,
    is_controlled: bool,
) -> dict[str, Any]:
    region = world.regions[region_name]
    known_owner = region.owner if is_visible or is_controlled else None
    data: dict[str, Any] = {
        "name": region.name,
        "display_name": region.display_name or region.name,
        "reference": format_region_reference(region, include_code=True),
        "visibility": (
            "controlled"
            if is_controlled
            else "visible"
            if is_visible
            else "known"
        ),
        "owner": known_owner,
        "neighbors": [
            neighbor_name
            for neighbor_name in region.neighbors
            if neighbor_name in get_faction_known_regions(world, faction_name)
        ],
        "terrain_tags": list(region.terrain_tags or []),
        "climate": region.climate,
    }

    if is_controlled:
        data.update(
            {
                "population": region.population,
                "resources": region.resources,
                "unrest": round(float(region.unrest or 0.0), 3),
                "settlement_level": region.settlement_level,
                "food_stored": round(float(region.food_stored or 0.0), 3),
                "food_balance": round(float(region.food_balance or 0.0), 3),
                "resource_depletion": round(float(region.resource_depletion or 0.0), 3),
                "urbanization_pressure": round(float(region.urbanization_pressure or 0.0), 3),
                "resource_short_summary": _known_resource_summary(region),
            }
        )
    elif is_visible:
        data.update(
            {
                "population_estimate": _estimate_band(region.population),
                "resource_estimate": _estimate_band(region.resources),
                "unrest_estimate": _estimate_unrest(region.unrest),
                "settlement_level": region.settlement_level,
            }
        )

    return data


def _serialize_known_faction(world, faction_name: str, other_name: str) -> dict[str, Any]:
    faction = world.factions[other_name]
    data = {
        "name": other_name,
        "display_name": faction.display_name,
        "relationship": (
            "self"
            if faction_name == other_name
            else get_relationship_status(world, faction_name, other_name)
        ),
    }
    if faction_name == other_name:
        data["treasury"] = round(float(faction.treasury), 3)
        data["doctrine_label"] = faction.doctrine_label
    return data


def _serialize_visible_events(world, faction_name: str) -> list[dict[str, Any]]:
    known_regions = get_faction_known_regions(world, faction_name)
    known_factions = set(world.factions[faction_name].known_factions or [])
    known_factions.add(faction_name)
    events = []
    for event in world.events[-30:]:
        if event.region not in known_regions and event.faction not in known_factions:
            continue
        events.append(
            {
                "turn": event.turn,
                "type": event.type,
                "faction": event.faction if event.faction in known_factions else None,
                "region": event.region if event.region in known_regions else None,
                "tags": list(event.tags or []),
                "significance": event.significance,
            }
        )
    return events[-10:]


def _estimate_band(value: float | int) -> str:
    value = float(value or 0)
    if value <= 0:
        return "none"
    if value < 100:
        return "low"
    if value < 300:
        return "moderate"
    if value < 700:
        return "high"
    return "very high"


def _estimate_unrest(value: float | int) -> str:
    value = float(value or 0)
    if value < 2:
        return "calm"
    if value < 5:
        return "uneasy"
    if value < 8:
        return "unstable"
    return "crisis"


def _known_resource_summary(region) -> dict[str, float]:
    output = region.resource_effective_output or region.resource_output or {}
    return {
        key: round(float(value), 3)
        for key, value in sorted(output.items())
        if value
    }
