from __future__ import annotations

from src.config import (
    ADMIN_BASE_CAPACITY_PER_REGION,
    ADMIN_BURDEN_CORE,
    ADMIN_BURDEN_FRONTIER,
    ADMIN_BURDEN_HOMELAND,
    ADMIN_CAPITAL_ISOLATION_CAPACITY_FACTOR,
    ADMIN_CAPITAL_ISOLATION_INITIAL_PENALTY,
    ADMIN_CAPITAL_ISOLATION_MARITIME_MITIGATION_FACTOR,
    ADMIN_CAPITAL_ISOLATION_MAX_PENALTY,
    ADMIN_CAPITAL_ISOLATION_TURN_PENALTY,
    ADMIN_DISTANCE_CAP,
    ADMIN_DISTANCE_DEPTH_QUADRATIC,
    ADMIN_DISTANCE_PER_ROUTE_DEPTH,
    ADMIN_FOREIGN_BORDER_DISTANCE,
    ADMIN_HOSTILE_BORDER_DISTANCE,
    ADMIN_LEGITIMACY_WEIGHT,
    ADMIN_MONARCHY_SPLIT_REALM_FACTOR,
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
    ADMIN_UNREST_BURDEN_FACTOR,
)
from src.diplomacy import get_relationship_status
from src.governance import (
    get_faction_administrative_capacity_modifier,
    get_faction_administrative_reach_modifier,
)
from src.internal_politics import get_faction_elite_effects
from src.models import Region, WorldState
from src.movement import (
    get_faction_seafaring_level,
    get_maritime_threshold,
    region_supports_maritime_access,
)
from src.resources import RESOURCE_GOLD
from src.region_state import get_region_core_status
from src.technology import (
    TECH_ROAD_ADMINISTRATION,
    TECH_TEMPLE_RECORDKEEPING,
    get_faction_institutional_technology,
    get_region_institutional_technology,
    get_region_technology_adoption,
)
from src.urban import (
    choose_faction_capital,
    get_faction_urban_capacity_bonus,
    get_region_urban_effects,
)


ADMIN_MARITIME_CONNECTION_THRESHOLD = get_maritime_threshold("contact")


def _owned_region_names(world: WorldState, faction_name: str) -> list[str]:
    return sorted(
        region.name
        for region in world.regions.values()
        if region.owner == faction_name
    )


def _ensure_faction_capital(world: WorldState, faction_name: str) -> str | None:
    faction = world.factions[faction_name]
    current_capital = faction.capital_region
    if (
        current_capital in world.regions
        and world.regions[current_capital].owner == faction_name
    ):
        return current_capital

    faction.capital_region = choose_faction_capital(world, faction_name)
    return faction.capital_region


def _split_realm_government_factor(world: WorldState, faction_name: str) -> float:
    faction = world.factions[faction_name]
    if faction.government_form == "monarchy":
        return ADMIN_MONARCHY_SPLIT_REALM_FACTOR
    return 1.0


def _build_capital_connection_adjacency(
    world: WorldState,
    faction_name: str,
) -> dict[str, list[tuple[str, str]]]:
    owned_names = set(_owned_region_names(world, faction_name))
    adjacency = {region_name: [] for region_name in owned_names}
    if not owned_names:
        return adjacency

    for region_name in owned_names:
        region = world.regions[region_name]
        for neighbor_name in region.neighbors:
            neighbor = world.regions.get(neighbor_name)
            if neighbor is not None and neighbor.owner == faction_name:
                adjacency[region_name].append((neighbor_name, "land"))

    seafaring_level = get_faction_seafaring_level(world, faction_name)
    if seafaring_level < ADMIN_MARITIME_CONNECTION_THRESHOLD:
        return adjacency

    for first_name, second_name in world.sea_links:
        if first_name not in owned_names or second_name not in owned_names:
            continue
        first = world.regions[first_name]
        second = world.regions[second_name]
        if not (
            region_supports_maritime_access(first)
            and region_supports_maritime_access(second)
        ):
            continue
        adjacency[first_name].append((second_name, "sea"))
        adjacency[second_name].append((first_name, "sea"))

    return adjacency


def _walk_capital_connections(
    adjacency: dict[str, list[tuple[str, str]]],
    capital_region_name: str | None,
) -> dict[str, dict[str, int | str | bool | None]]:
    connection = {
        region_name: {
            "connected": False,
            "mode": "isolated",
            "depth": None,
        }
        for region_name in adjacency
    }
    if capital_region_name not in adjacency:
        return connection

    connection[capital_region_name] = {
        "connected": True,
        "mode": "capital",
        "depth": 0,
    }
    queue = [capital_region_name]
    while queue:
        current_name = queue.pop(0)
        current_depth = int(connection[current_name]["depth"] or 0)
        current_mode = str(connection[current_name]["mode"])
        for next_name, edge_mode in adjacency[current_name]:
            if connection[next_name]["connected"]:
                continue
            connection[next_name] = {
                "connected": True,
                "mode": "sea" if edge_mode == "sea" or current_mode == "sea" else "land",
                "depth": current_depth + 1,
            }
            queue.append(next_name)
    return connection


def _count_capital_connection_components(
    adjacency: dict[str, list[tuple[str, str]]],
) -> int:
    remaining = set(adjacency)
    components = 0
    while remaining:
        components += 1
        queue = [remaining.pop()]
        while queue:
            current_name = queue.pop(0)
            for next_name, _mode in adjacency[current_name]:
                if next_name in remaining:
                    remaining.remove(next_name)
                    queue.append(next_name)
    return components


def _capital_fragment_penalty(
    region: Region,
    world: WorldState,
    faction_name: str,
) -> float:
    if region.capital_connection_mode != "isolated":
        return 0.0

    turns = max(1, int(region.capital_disconnection_turns or 0))
    penalty = ADMIN_CAPITAL_ISOLATION_INITIAL_PENALTY + min(
        ADMIN_CAPITAL_ISOLATION_MAX_PENALTY - ADMIN_CAPITAL_ISOLATION_INITIAL_PENALTY,
        max(0, turns - 1) * ADMIN_CAPITAL_ISOLATION_TURN_PENALTY,
    )

    seafaring_level = get_faction_seafaring_level(world, faction_name)
    if (
        region_supports_maritime_access(region)
        and seafaring_level >= ADMIN_MARITIME_CONNECTION_THRESHOLD
    ):
        maritime_factor = max(
            0.55,
            1.0 - (seafaring_level * ADMIN_CAPITAL_ISOLATION_MARITIME_MITIGATION_FACTOR),
        )
        penalty *= maritime_factor

    penalty *= _split_realm_government_factor(world, faction_name)
    return round(max(0.0, penalty), 3)


def _apply_capital_connectivity(world: WorldState, faction_name: str) -> None:
    faction = world.factions[faction_name]
    owned_names = _owned_region_names(world, faction_name)
    if not owned_names:
        faction.capital_connected_regions = 0
        faction.capital_isolated_regions = 0
        faction.capital_fragment_count = 0
        faction.capital_connectivity_penalty = 0.0
        return

    capital_region_name = _ensure_faction_capital(world, faction_name)
    adjacency = _build_capital_connection_adjacency(world, faction_name)
    connection = _walk_capital_connections(adjacency, capital_region_name)
    fragment_count = _count_capital_connection_components(adjacency)
    connected_count = 0
    isolated_count = 0
    penalty_sum = 0.0

    for region_name in owned_names:
        region = world.regions[region_name]
        state = connection.get(region_name, {})
        connected = bool(state.get("connected", False))
        if connected:
            connected_count += 1
            region.capital_connection_mode = str(state.get("mode") or "land")
            region.capital_connection_depth = state.get("depth")
            region.capital_disconnection_turns = 0
        else:
            isolated_count += 1
            region.capital_connection_mode = "isolated"
            region.capital_connection_depth = None
            region.capital_disconnection_turns = int(region.capital_disconnection_turns or 0) + 1

        region.capital_fragment_penalty = _capital_fragment_penalty(
            region,
            world,
            faction_name,
        )
        penalty_sum += float(region.capital_fragment_penalty or 0.0)

    faction.capital_connected_regions = connected_count
    faction.capital_isolated_regions = isolated_count
    faction.capital_fragment_count = fragment_count
    faction.capital_connectivity_penalty = round(
        penalty_sum / max(1, len(owned_names)),
        3,
    )


def get_region_administrative_support(region: Region) -> float:
    support = ADMIN_SUPPORT_SETTLEMENT_BONUSES.get(region.settlement_level, 0.0)
    support += region.infrastructure_level * ADMIN_SUPPORT_INFRASTRUCTURE_FACTOR
    support += region.road_level * ADMIN_SUPPORT_ROAD_FACTOR
    support += region.market_level * ADMIN_SUPPORT_MARKET_FACTOR
    support += region.storehouse_level * ADMIN_SUPPORT_STOREHOUSE_FACTOR
    support += region.integration_score * ADMIN_SUPPORT_INTEGRATION_FACTOR
    support += get_region_technology_adoption(region, TECH_ROAD_ADMINISTRATION) * 0.05
    support += get_region_technology_adoption(region, TECH_TEMPLE_RECORDKEEPING) * 0.06
    support += get_region_urban_effects(region).get("administrative_support_bonus", 0.0)
    status = get_region_core_status(region)
    if status == "homeland":
        support += 0.18
    elif status == "core":
        support += 0.08
    return round(max(0.0, support), 3)


def get_region_administrative_distance(region: Region, world: WorldState) -> float:
    if region.owner is None or get_region_core_status(region) == "homeland":
        return 0.0

    depth = float(region.resource_route_depth or 0)
    distance = depth * ADMIN_DISTANCE_PER_ROUTE_DEPTH + (depth ** 1.5) * ADMIN_DISTANCE_DEPTH_QUADRATIC
    if not region.resource_route_depth:
        distance += 0.1 if get_region_core_status(region) == "frontier" else 0.04
    if region.resource_route_mode in {"sea", "river"}:
        distance = max(0.0, distance - 0.04)
    distance += float(region.capital_fragment_penalty or 0.0)

    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None or neighbor.owner == region.owner:
            continue
        distance += ADMIN_FOREIGN_BORDER_DISTANCE
        relation = get_relationship_status(world, region.owner, neighbor.owner)
        if relation in {"rival", "war", "truce"}:
            distance += ADMIN_HOSTILE_BORDER_DISTANCE

    return round(min(ADMIN_DISTANCE_CAP, distance), 3)


def get_region_administrative_burden(region: Region, world: WorldState) -> float:
    status = get_region_core_status(region)
    burden = {
        "homeland": ADMIN_BURDEN_HOMELAND,
        "core": ADMIN_BURDEN_CORE,
        "frontier": ADMIN_BURDEN_FRONTIER,
    }.get(status, ADMIN_BURDEN_FRONTIER)
    administrative_distance = get_region_administrative_distance(region, world)
    burden += administrative_distance
    burden += min(
        ADMIN_POPULATION_BURDEN_MAX,
        max(0.0, region.population) * ADMIN_POPULATION_BURDEN_FACTOR,
    )
    if region.owner in world.factions:
        faction = world.factions[region.owner]
        gold_access = max(0.0, float((faction.resource_effective_access or {}).get(RESOURCE_GOLD, 0.0)))
        if gold_access >= 0.18 and administrative_distance > 0:
            burden -= min(
                0.18,
                gold_access * 0.022 * (1.0 + min(0.6, administrative_distance * 0.35)),
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
        faction.capital_connected_regions = 0
        faction.capital_isolated_regions = 0
        faction.capital_fragment_count = 0
        faction.capital_connectivity_penalty = 0.0

    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            region.administrative_burden = 0.0
            region.administrative_support = 0.0
            region.administrative_distance = 0.0
            region.administrative_autonomy = 0.0
            region.administrative_tax_capture = 1.0
            region.capital_connection_mode = "none"
            region.capital_connection_depth = None
            region.capital_disconnection_turns = 0
            region.capital_fragment_penalty = 0.0
            continue

        region.administrative_support = get_region_administrative_support(region)
        region.administrative_distance = 0.0
        region.administrative_burden = 0.0
        region.administrative_autonomy = 0.0
        region.administrative_tax_capture = 1.0
        region.capital_connection_mode = "none"
        region.capital_connection_depth = None
        region.capital_fragment_penalty = 0.0

    for faction_name in world.factions:
        _apply_capital_connectivity(world, faction_name)

    for region in world.regions.values():
        if region.owner is None or region.owner not in world.factions:
            continue

        owner_name = region.owner
        region.administrative_distance = get_region_administrative_distance(region, world)
        region.administrative_burden = get_region_administrative_burden(region, world)
        per_faction_support[owner_name] = (
            per_faction_support.get(owner_name, 0.0) + region.administrative_support
        )
        per_faction_distance[owner_name] = (
            per_faction_distance.get(owner_name, 0.0) + region.administrative_distance
        )
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
            + (
                float(faction.religion.religious_legitimacy or 0.0)
                * ADMIN_RELIGIOUS_LEGITIMACY_WEIGHT
            )
        )
        capacity = (
            region_count
            * ADMIN_BASE_CAPACITY_PER_REGION
            * get_faction_administrative_capacity_modifier(faction)
            * (1.0 + (average_support * ADMIN_SUPPORT_CAPACITY_FACTOR))
            * legitimacy_support
        )
        capacity += (
            max(0.0, float(faction.derived_capacity.get("mobility_capacity", 0.0)))
            * ADMIN_MOBILITY_CAPACITY_FACTOR
        )
        capacity += (
            max(0.0, float(faction.derived_capacity.get("taxable_value", 0.0)))
            * ADMIN_TAXABLE_CAPACITY_FACTOR
        )
        gold_access = max(0.0, float((faction.resource_effective_access or {}).get(RESOURCE_GOLD, 0.0)))
        capacity *= 1.0 + min(0.08, gold_access * 0.018)
        capacity *= 1.0 + get_faction_urban_capacity_bonus(world, faction_name)
        capacity *= 1.0 + get_faction_elite_effects(faction).get("administrative_capacity_factor", 0.0)
        capacity *= (
            1.0
            + get_faction_institutional_technology(faction, TECH_TEMPLE_RECORDKEEPING) * 0.08
            + get_faction_institutional_technology(faction, TECH_ROAD_ADMINISTRATION) * 0.05
        )
        capacity *= max(
            0.65,
            1.0
            - (
                float(faction.capital_connectivity_penalty or 0.0)
                * ADMIN_CAPITAL_ISOLATION_CAPACITY_FACTOR
            ),
        )

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
        reach *= 1.0 + get_faction_elite_effects(faction).get("administrative_reach_factor", 0.0)
        reach *= 1.0 + min(0.04, gold_access * 0.01)
        reach = max(0.35, min(1.18, reach))
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
                - (
                    0.62
                    + (region.administrative_support * 0.9)
                    + (efficiency * 0.85)
                    + (reach * 0.35)
                ),
            )
            tax_capture = (
                (efficiency * 0.78)
                + (reach * 0.18)
                + (region.administrative_support * 0.14)
                - (autonomy * 0.16)
            )
            tax_capture += get_region_institutional_technology(
                region,
                world,
                TECH_TEMPLE_RECORDKEEPING,
            ) * 0.035
            status = get_region_core_status(region)
            if status == "homeland":
                tax_capture += 0.05
            elif status == "core":
                tax_capture += 0.02
            elif status == "frontier":
                tax_capture -= 0.04
            region.administrative_autonomy = round(min(2.5, autonomy), 3)
            region.administrative_tax_capture = round(max(0.42, min(1.05, tax_capture)), 3)
