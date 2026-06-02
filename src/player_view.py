from __future__ import annotations

from typing import Any

from src.calendar import format_turn_label
from src.diplomacy import get_relationship_status
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
    return {
        "turn": world.turn,
        "turn_label": format_turn_label(world.turn),
        "factions": [
            {
                "name": faction_name,
                "display_name": faction.display_name,
                "treasury": round(float(faction.treasury), 3),
                "owned_regions": sum(
                    1 for region in world.regions.values() if region.owner == faction_name
                ),
                "population": sum(
                    region.population
                    for region in world.regions.values()
                    if region.owner == faction_name
                ),
                "doctrine_label": faction.doctrine_label,
            }
            for faction_name, faction in sorted(world.factions.items())
            if not is_faction_inactive(world, faction_name)
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
        "recent_events": [
            event.to_dict()
            for event in world.events[-20:]
        ],
    }


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
        "food_stored": round(float(faction.food_stored or 0.0), 3),
        "food_balance": round(float(faction.food_balance or 0.0), 3),
        "manpower_pool": round(float(faction.manpower_pool or 0.0), 3),
        "army_quality": round(float(faction.army_quality or 0.0), 3),
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
