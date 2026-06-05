from __future__ import annotations

from src.config import (
    SEAFARING_ATTACK_THRESHOLD,
    SEAFARING_CONTACT_THRESHOLD,
    SEAFARING_EXPANSION_THRESHOLD,
)
from src.models import Region, WorldState
from src.technology import TECH_SEAFARING, get_faction_institutional_technology


MARITIME_PURPOSE_THRESHOLDS = {
    "contact": SEAFARING_CONTACT_THRESHOLD,
    "expand": SEAFARING_EXPANSION_THRESHOLD,
    "attack": SEAFARING_ATTACK_THRESHOLD,
}


def get_faction_seafaring_level(world: WorldState, faction_name: str) -> float:
    """Return the faction's practical maritime movement capability."""
    faction = world.factions.get(faction_name)
    if faction is None:
        return 0.0
    institutional = get_faction_institutional_technology(faction, TECH_SEAFARING)
    known = float((faction.known_technologies or {}).get(TECH_SEAFARING, 0.0))
    naval_practice = min(0.2, float(faction.naval_power or 0.0) * 0.025)
    return round(max(institutional, known * 0.85, naval_practice), 3)


def get_maritime_threshold(purpose: str) -> float:
    return MARITIME_PURPOSE_THRESHOLDS.get(purpose, SEAFARING_EXPANSION_THRESHOLD)


def region_supports_maritime_access(region: Region) -> bool:
    return (
        "coast" in (region.terrain_tags or [])
        or region.resource_route_mode == "sea"
        or region.trade_gateway_role == "sea_gateway"
        or float(region.naval_base_level or 0.0) > 0.0
    )


def has_land_connection(world: WorldState, faction_name: str, target_region_name: str) -> bool:
    target = world.regions.get(target_region_name)
    if target is None:
        return False
    return any(
        world.regions.get(neighbor_name) is not None
        and world.regions[neighbor_name].owner == faction_name
        for neighbor_name in target.neighbors
    )


def get_maritime_route(
    world: WorldState,
    faction_name: str,
    target_region_name: str,
    *,
    purpose: str,
    prefer_land: bool = True,
) -> dict[str, float | str | bool] | None:
    """Return a direct sea-link route to a target if the faction can use it."""
    if prefer_land and has_land_connection(world, faction_name, target_region_name):
        return None
    target = world.regions.get(target_region_name)
    if target is None or not region_supports_maritime_access(target):
        return None

    threshold = get_maritime_threshold(purpose)
    seafaring_level = get_faction_seafaring_level(world, faction_name)
    if seafaring_level < threshold:
        return None

    candidates = []
    for a_name, b_name in world.sea_links:
        if target_region_name not in {a_name, b_name}:
            continue
        source_name = b_name if a_name == target_region_name else a_name
        source = world.regions.get(source_name)
        if (
            source is None
            or source.owner != faction_name
            or not region_supports_maritime_access(source)
        ):
            continue
        score = (
            float(source.population or 0) / 500.0
            + float(source.naval_base_level or 0.0) * 2.0
            + float(source.market_level or 0.0)
            + float(source.infrastructure_level or 0.0) * 0.5
            + (0.3 if source.trade_gateway_role == "sea_gateway" else 0.0)
        )
        candidates.append((score, source.name))

    if not candidates:
        return None
    _score, source_name = max(candidates)
    return {
        "mode": "sea",
        "source_region": source_name,
        "target_region": target_region_name,
        "seafaring_level": seafaring_level,
        "threshold": threshold,
        "maritime_operation": True,
    }


def get_maritime_reachable_region_names(
    world: WorldState,
    faction_name: str,
    *,
    purpose: str,
    prefer_land: bool = True,
) -> list[str]:
    reachable = set()
    for region_name in world.regions:
        if get_maritime_route(
            world,
            faction_name,
            region_name,
            purpose=purpose,
            prefer_land=prefer_land,
        ):
            reachable.add(region_name)
    return sorted(reachable)
