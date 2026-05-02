from __future__ import annotations

from src.models import Event, WorldState
from src.region_state import get_region_core_status
from src.resources import (
    CAPACITY_FOOD_SECURITY,
    CAPACITY_METAL,
    CAPACITY_MOBILITY,
)
from src.technology import (
    TECH_COPPER_WORKING,
    TECH_ORGANIZED_LEVIES,
    TECH_ROAD_ADMINISTRATION,
    get_faction_institutional_technology,
    get_region_institutional_technology,
)


PROJECT_BUILD_FORTIFICATIONS = "build_fortifications"
PROJECT_RAISE_GARRISON = "raise_garrison"
PROJECT_BUILD_LOGISTICS_NODE = "build_logistics_node"
PROJECT_BUILD_NAVAL_BASE = "build_naval_base"
PROJECT_MILITARY_REFORM = "military_reform"

MILITARY_PROJECT_TYPES = {
    PROJECT_BUILD_FORTIFICATIONS,
    PROJECT_RAISE_GARRISON,
    PROJECT_BUILD_LOGISTICS_NODE,
    PROJECT_BUILD_NAVAL_BASE,
    PROJECT_MILITARY_REFORM,
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _owned_regions(world: WorldState, faction_name: str):
    return [
        region
        for region in world.regions.values()
        if region.owner == faction_name
    ]


def _frontier_edges(world: WorldState, faction_name: str, region) -> int:
    edges = 0
    for neighbor_name in region.neighbors:
        neighbor = world.regions.get(neighbor_name)
        if neighbor is not None and neighbor.owner not in {None, faction_name}:
            edges += 1
    return edges


def _population_manpower(population: int) -> float:
    return max(0.0, float(population or 0) / 28.0)


def get_region_military_value(region, world: WorldState | None = None) -> float:
    """Returns durable local military infrastructure value for summaries."""
    value = (
        float(region.fortification_level or 0.0) * 1.6
        + float(region.garrison_strength or 0.0) * 1.25
        + float(region.logistics_node_level or 0.0) * 0.9
        + float(region.naval_base_level or 0.0) * 0.9
    )
    if world is not None:
        value += get_region_institutional_technology(region, world, TECH_ORGANIZED_LEVIES) * 0.9
    return round(max(0.0, value), 3)


def get_region_fortification_defense_bonus(region, world: WorldState | None = None) -> int:
    fortification = float(region.fortification_level or 0.0)
    garrison = float(region.garrison_strength or 0.0)
    logistics = float(region.logistics_node_level or 0.0)
    settlement_bonus = {
        "wild": 0.0,
        "rural": 0.3,
        "town": 0.75,
        "city": 1.2,
    }.get(region.settlement_level, 0.0)
    damage_factor = 1.0 - min(0.45, float(region.military_damage or 0.0))
    technology_bonus = 0.0
    if world is not None:
        technology_bonus = get_region_institutional_technology(region, world, TECH_ORGANIZED_LEVIES) * 1.4
    return int(round(max(0.0, (
        fortification * 4.0
        + garrison * 2.6
        + logistics * 0.9
        + settlement_bonus
        + technology_bonus
    ) * damage_factor)))


def get_region_logistics_value(region) -> float:
    return round(
        float(region.logistics_node_level or 0.0) * 1.35
        + float(region.road_level or 0.0) * 0.8
        + float(region.storehouse_level or 0.0) * 0.45
        + float(region.infrastructure_level or 0.0) * 0.35,
        3,
    )


def is_maritime_operation(world: WorldState, attacker_name: str, target_region) -> bool:
    if "coast" not in target_region.terrain_tags and target_region.trade_gateway_role != "sea_gateway":
        return False
    for neighbor_name in target_region.neighbors:
        neighbor = world.regions.get(neighbor_name)
        if neighbor is not None and neighbor.owner == attacker_name:
            return "coast" in neighbor.terrain_tags or neighbor.resource_route_mode == "sea"
    sea_edges = {tuple(sorted(edge)) for edge in getattr(world, "sea_links", [])}
    return any(
        tuple(sorted((target_region.name, other_name))) in sea_edges
        and world.regions.get(other_name) is not None
        and world.regions[other_name].owner == attacker_name
        for other_name in world.regions
    )


def refresh_military_state(world: WorldState, *, emit_events: bool = False) -> None:
    """Refreshes faction manpower, standing forces, quality, logistics, and naval rollups."""
    for faction_name, faction in world.factions.items():
        regions = _owned_regions(world, faction_name)
        total_population = sum(int(region.population or 0) for region in regions)
        manpower_capacity = sum(_population_manpower(region.population) for region in regions)
        polity_factor = {
            "band": 0.64,
            "tribe": 0.82,
            "chiefdom": 1.0,
            "state": 1.16,
        }.get(faction.polity_tier, 0.82)
        levy_tech = get_faction_institutional_technology(faction, TECH_ORGANIZED_LEVIES)
        copper_tech = get_faction_institutional_technology(faction, TECH_COPPER_WORKING)
        road_tech = get_faction_institutional_technology(faction, TECH_ROAD_ADMINISTRATION)
        food_shortage = float((faction.resource_shortages or {}).get(CAPACITY_FOOD_SECURITY, 0.0) or 0.0)
        mobility_shortage = float((faction.resource_shortages or {}).get(CAPACITY_MOBILITY, 0.0) or 0.0)
        metal_shortage = float((faction.resource_shortages or {}).get(CAPACITY_METAL, 0.0) or 0.0)
        shortage_drag = min(0.42, (food_shortage * 0.18) + (mobility_shortage * 0.18) + (metal_shortage * 0.16))
        manpower_capacity = round(max(0.0, manpower_capacity * polity_factor * (1.0 + levy_tech * 0.28)), 3)

        can_recover = faction.last_military_recovery_turn != world.turn
        initialized_pool = False
        if faction.manpower_capacity <= 0 and faction.manpower_pool <= 0:
            manpower_pool = manpower_capacity * 0.72
            initialized_pool = True
        elif can_recover:
            recovery = max(0.18, manpower_capacity * (0.055 + levy_tech * 0.025))
            manpower_pool = min(manpower_capacity, float(faction.manpower_pool or 0.0) + recovery)
        else:
            manpower_pool = min(manpower_capacity, float(faction.manpower_pool or 0.0))
        manpower_pool *= (1.0 - min(0.3, food_shortage * 0.1))

        garrison_total = sum(float(region.garrison_strength or 0.0) for region in regions)
        fort_total = sum(float(region.fortification_level or 0.0) for region in regions)
        logistics_total = sum(get_region_logistics_value(region) for region in regions)
        naval_base_total = sum(float(region.naval_base_level or 0.0) for region in regions)
        coastal_regions = sum(1 for region in regions if "coast" in region.terrain_tags or region.trade_gateway_role == "sea_gateway")
        trade_port_value = sum(
            max(0.0, float(region.trade_foreign_flow or 0.0) + float(region.trade_throughput or 0.0) * 0.08)
            for region in regions
            if "coast" in region.terrain_tags or region.trade_gateway_role == "sea_gateway"
        )
        standing_target = (
            manpower_capacity * (0.34 + levy_tech * 0.18)
            + max(0.0, float(faction.treasury or 0.0)) * 0.24
            + garrison_total * 2.6
        )
        standing_forces = min(manpower_pool, max(0.0, standing_target))
        logistics_capacity = max(
            0.0,
            logistics_total
            + road_tech * max(1.0, len(regions)) * 0.75
            + float((faction.derived_capacity or {}).get(CAPACITY_MOBILITY, 0.0) or 0.0) * 0.12,
        )
        naval_power = max(
            0.0,
            naval_base_total * 2.2
            + coastal_regions * 0.45
            + trade_port_value * 0.16
            + road_tech * coastal_regions * 0.18,
        )
        military_tradition = _clamp(
            float(faction.military_tradition or 0.0)
            + (0.004 if any(war.active and faction_name in {war.aggressor, war.defender} for war in world.wars.values()) else 0.0)
            + min(0.018, faction.military_reform_pressure * 0.02),
            0.0,
            1.0,
        )
        quality = (
            0.64
            + levy_tech * 0.32
            + copper_tech * 0.2
            + military_tradition * 0.24
            + min(0.16, logistics_capacity / max(8.0, len(regions) * 4.0))
            - shortage_drag
        )
        readiness = (
            (standing_forces / max(1.0, manpower_capacity)) * 0.82
            + min(0.3, logistics_capacity / max(10.0, len(regions) * 5.0))
            + min(0.16, naval_power / 10.0)
            - shortage_drag * 0.5
        )
        force_projection = standing_forces * max(0.35, quality) * (0.5 + min(0.85, logistics_capacity / max(4.0, len(regions) * 2.6)))
        force_projection += naval_power * 0.9

        previous_quality = float(faction.army_quality or 0.0)
        faction.manpower_capacity = round(manpower_capacity, 3)
        faction.manpower_pool = round(max(0.0, manpower_pool), 3)
        faction.standing_forces = round(max(0.0, standing_forces), 3)
        faction.logistics_capacity = round(logistics_capacity, 3)
        faction.naval_power = round(naval_power, 3)
        faction.military_tradition = round(military_tradition, 3)
        faction.army_quality = round(_clamp(quality, 0.28, 1.45), 3)
        faction.military_readiness = round(_clamp(readiness, 0.0, 1.25), 3)
        faction.force_projection = round(max(0.0, force_projection), 3)
        faction.military_upkeep = round(max(0.0, standing_forces * 0.028 + fort_total * 0.06 + naval_power * 0.035), 3)
        faction.military_reform_pressure = round(max(0.0, faction.military_reform_pressure * 0.88 + shortage_drag * 0.16), 3)
        if can_recover or initialized_pool:
            faction.last_military_recovery_turn = world.turn

        if emit_events and previous_quality > 0 and faction.army_quality - previous_quality >= 0.08:
            world.events.append(Event(
                turn=world.turn,
                type="military_reform",
                faction=faction_name,
                details={
                    "army_quality": faction.army_quality,
                    "military_tradition": faction.military_tradition,
                    "manpower_capacity": faction.manpower_capacity,
                    "standing_forces": faction.standing_forces,
                },
                tags=["military", "reform"],
                significance=round(faction.army_quality - previous_quality, 3),
            ))


def get_attack_military_profile(world: WorldState, attacker_name: str, target_region, staging_regions=None) -> dict[str, float | bool]:
    refresh_military_state(world, emit_events=False)
    attacker = world.factions[attacker_name]
    staging_regions = list(staging_regions or [])
    staging_logistics = max((get_region_logistics_value(region) for region in staging_regions), default=0.0)
    maritime = is_maritime_operation(world, attacker_name, target_region)
    logistics_modifier = _clamp(
        0.78
        + min(0.38, float(attacker.logistics_capacity or 0.0) / max(6.0, len(_owned_regions(world, attacker_name)) * 3.2))
        + min(0.18, staging_logistics * 0.05)
        - min(0.22, float(target_region.trade_warfare_pressure or 0.0) * 0.12),
        0.55,
        1.28,
    )
    manpower_commitment = min(
        float(attacker.standing_forces or 0.0),
        max(1.0, float(attacker.manpower_pool or 0.0) * 0.34),
    )
    naval_bonus = 0.0
    if maritime:
        naval_bonus = min(5.0, float(attacker.naval_power or 0.0) * 0.55)
        logistics_modifier += min(0.12, float(attacker.naval_power or 0.0) * 0.02)
    attack_bonus = (
        manpower_commitment * 0.32
        + float(attacker.army_quality or 0.0) * 3.0
        + float(attacker.military_readiness or 0.0) * 2.2
        + max(0.0, logistics_modifier - 0.78) * 4.0
        + naval_bonus
    )
    if float(attacker.manpower_pool or 0.0) < max(1.0, float(attacker.manpower_capacity or 0.0) * 0.18):
        attack_bonus -= 2.2
    return {
        "military_attack_bonus": round(max(-4.0, attack_bonus), 3),
        "attacker_army_quality": round(float(attacker.army_quality or 0.0), 3),
        "attacker_readiness": round(float(attacker.military_readiness or 0.0), 3),
        "attacker_manpower": round(float(attacker.manpower_pool or 0.0), 3),
        "attacker_standing_forces": round(float(attacker.standing_forces or 0.0), 3),
        "attacker_logistics": round(float(attacker.logistics_capacity or 0.0), 3),
        "attacker_naval_power": round(float(attacker.naval_power or 0.0), 3),
        "logistics_modifier": round(logistics_modifier, 3),
        "manpower_commitment": round(manpower_commitment, 3),
        "supply_risk": round(_clamp(1.0 - logistics_modifier, 0.0, 0.6), 3),
        "naval_operation": maritime,
        "naval_attack_bonus": round(naval_bonus, 3),
    }


def get_defense_military_profile(world: WorldState, defender_name: str, region) -> dict[str, float]:
    refresh_military_state(world, emit_events=False)
    defender = world.factions[defender_name]
    fort_bonus = get_region_fortification_defense_bonus(region, world)
    local_garrison = float(region.garrison_strength or 0.0)
    reserve_commitment = min(
        float(defender.standing_forces or 0.0) * 0.24,
        max(0.0, float(defender.manpower_pool or 0.0) * 0.22),
    )
    defense_bonus = (
        fort_bonus
        + local_garrison * 1.6
        + reserve_commitment * 0.22
        + float(defender.army_quality or 0.0) * 2.4
        + float(defender.military_readiness or 0.0) * 1.7
    )
    return {
        "military_defense_bonus": round(max(0.0, defense_bonus), 3),
        "defender_army_quality": round(float(defender.army_quality or 0.0), 3),
        "defender_readiness": round(float(defender.military_readiness or 0.0), 3),
        "defender_manpower": round(float(defender.manpower_pool or 0.0), 3),
        "defender_standing_forces": round(float(defender.standing_forces or 0.0), 3),
        "defender_logistics": round(float(defender.logistics_capacity or 0.0), 3),
        "defender_fortification": round(float(region.fortification_level or 0.0), 3),
        "defender_garrison": round(float(region.garrison_strength or 0.0), 3),
        "fortification_defense_bonus": fort_bonus,
        "reserve_commitment": round(reserve_commitment, 3),
    }


def apply_battle_military_losses(
    world: WorldState,
    attacker_name: str,
    defender_name: str,
    region_name: str,
    *,
    succeeded: bool,
    score_components: dict,
) -> dict[str, float]:
    attacker = world.factions[attacker_name]
    defender = world.factions[defender_name]
    target_region = world.regions[region_name]
    supply_risk = float(score_components.get("supply_risk", 0.0) or 0.0)
    attacker_commitment = float(score_components.get("manpower_commitment", 0.0) or 0.0)
    defender_commitment = float(score_components.get("reserve_commitment", 0.0) or 0.0) + float(target_region.garrison_strength or 0.0) * 2.0
    attacker_loss = max(0.08, attacker_commitment * (0.07 + supply_risk * 0.08 + (0.03 if not succeeded else 0.0)))
    defender_loss = max(0.06, defender_commitment * (0.09 + (0.05 if succeeded else 0.02)))
    attacker.manpower_pool = round(max(0.0, float(attacker.manpower_pool or 0.0) - attacker_loss), 3)
    defender.manpower_pool = round(max(0.0, float(defender.manpower_pool or 0.0) - defender_loss), 3)
    attacker.standing_forces = round(max(0.0, float(attacker.standing_forces or 0.0) - attacker_loss * 0.62), 3)
    defender.standing_forces = round(max(0.0, float(defender.standing_forces or 0.0) - defender_loss * 0.58), 3)
    if succeeded:
        target_region.garrison_strength = round(max(0.0, float(target_region.garrison_strength or 0.0) - defender_loss * 0.22), 3)
        target_region.military_damage = round(min(1.0, float(target_region.military_damage or 0.0) + 0.08 + supply_risk * 0.04), 3)
    else:
        target_region.military_damage = round(min(1.0, float(target_region.military_damage or 0.0) + 0.035), 3)
    attacker.military_tradition = round(min(1.0, float(attacker.military_tradition or 0.0) + 0.012 + (0.008 if succeeded else 0.0)), 3)
    defender.military_tradition = round(min(1.0, float(defender.military_tradition or 0.0) + 0.014 + (0.008 if not succeeded else 0.0)), 3)
    attacker.military_reform_pressure = round(min(1.0, float(attacker.military_reform_pressure or 0.0) + attacker_loss / max(1.0, float(attacker.manpower_capacity or 1.0))), 3)
    defender.military_reform_pressure = round(min(1.0, float(defender.military_reform_pressure or 0.0) + defender_loss / max(1.0, float(defender.manpower_capacity or 1.0))), 3)
    result = {
        "attacker_manpower_loss": round(attacker_loss, 3),
        "defender_manpower_loss": round(defender_loss, 3),
        "attacker_manpower_after": round(float(attacker.manpower_pool or 0.0), 3),
        "defender_manpower_after": round(float(defender.manpower_pool or 0.0), 3),
        "region_military_damage": round(float(target_region.military_damage or 0.0), 3),
    }
    if attacker_loss + defender_loss >= 0.1:
        world.events.append(Event(
            turn=world.turn,
            type="military_battle_losses",
            faction=attacker_name,
            region=region_name,
            details={
                "defender": defender_name,
                "success": succeeded,
                **result,
            },
            tags=["military", "combat_losses"],
            significance=round(attacker_loss + defender_loss, 3),
        ))
    refresh_military_state(world, emit_events=False)
    return result


def get_military_project_score_options(world: WorldState, faction_name: str, region) -> list[dict[str, float | str]]:
    faction = world.factions[faction_name]
    border_edges = _frontier_edges(world, faction_name, region)
    at_war = any(war.active and faction_name in {war.aggressor, war.defender} for war in world.wars.values())
    core_status = get_region_core_status(region)
    strategic_port = "coast" in region.terrain_tags or region.trade_gateway_role == "sea_gateway" or region.resource_route_mode == "sea"
    construction_shortage = float((faction.resource_shortages or {}).get("construction_capacity", 0.0) or 0.0)
    mobility_shortage = float((faction.resource_shortages or {}).get(CAPACITY_MOBILITY, 0.0) or 0.0)
    score_pressure = border_edges * 1.4 + (1.2 if at_war else 0.0) + (0.8 if core_status == "frontier" else 0.35 if core_status == "core" else 0.0)
    options: list[dict[str, float | str]] = []
    if region.fortification_level < 1.8 and (border_edges > 0 or at_war or region.unrest >= 0.45):
        options.append({
            "project_type": PROJECT_BUILD_FORTIFICATIONS,
            "score": 2.7 + score_pressure + float(region.stone_quarry_level or 0.0) * 0.45 - construction_shortage * 0.55,
            "resource_focus": "fortification",
        })
    if region.garrison_strength < 1.8 and (border_edges > 0 or region.fortification_level > 0.2 or at_war):
        options.append({
            "project_type": PROJECT_RAISE_GARRISON,
            "score": 2.25 + score_pressure + float(faction.army_quality or 0.0) * 0.9,
            "resource_focus": "manpower",
        })
    if region.logistics_node_level < 1.8 and (
        region.road_level > 0.25
        or region.storehouse_level > 0.35
        or region.trade_route_role in {"corridor", "hub"}
        or border_edges > 0
    ):
        options.append({
            "project_type": PROJECT_BUILD_LOGISTICS_NODE,
            "score": 2.4 + float(region.road_level or 0.0) * 1.2 + float(region.storehouse_level or 0.0) * 0.8 + border_edges * 0.75 + mobility_shortage * 0.35,
            "resource_focus": "logistics",
        })
    if strategic_port and region.naval_base_level < 1.8:
        options.append({
            "project_type": PROJECT_BUILD_NAVAL_BASE,
            "score": 2.2 + float(region.trade_foreign_flow or 0.0) * 0.35 + float(region.trade_throughput or 0.0) * 0.035 + (1.3 if region.trade_gateway_role == "sea_gateway" else 0.0) + border_edges * 0.35,
            "resource_focus": "naval",
        })
    if faction.military_reform_pressure >= 0.18 or (at_war and faction.army_quality < 0.85):
        options.append({
            "project_type": PROJECT_MILITARY_REFORM,
            "score": 1.9 + faction.military_reform_pressure * 3.2 + (0.8 if at_war else 0.0) + get_region_logistics_value(region) * 0.25,
            "resource_focus": "reform",
        })
    return options


def apply_military_development_project(world: WorldState, faction_name: str, region, project_type: str) -> float:
    faction = world.factions[faction_name]
    project_amount = 0.0
    if project_type == PROJECT_BUILD_FORTIFICATIONS:
        region.fortification_level = round(min(1.8, float(region.fortification_level or 0.0) + 0.28), 2)
        region.garrison_strength = round(min(1.8, float(region.garrison_strength or 0.0) + 0.08), 2)
        region.military_damage = round(max(0.0, float(region.military_damage or 0.0) - 0.08), 3)
        project_amount = 0.28
    elif project_type == PROJECT_RAISE_GARRISON:
        region.garrison_strength = round(min(1.8, float(region.garrison_strength or 0.0) + 0.32), 2)
        faction.manpower_pool = round(max(0.0, float(faction.manpower_pool or 0.0) - 0.18), 3)
        project_amount = 0.32
    elif project_type == PROJECT_BUILD_LOGISTICS_NODE:
        region.logistics_node_level = round(min(1.8, float(region.logistics_node_level or 0.0) + 0.3), 2)
        region.storehouse_level = round(min(1.8, float(region.storehouse_level or 0.0) + 0.05), 2)
        project_amount = 0.3
    elif project_type == PROJECT_BUILD_NAVAL_BASE:
        region.naval_base_level = round(min(1.8, float(region.naval_base_level or 0.0) + 0.3), 2)
        region.logistics_node_level = round(min(1.8, float(region.logistics_node_level or 0.0) + 0.04), 2)
        project_amount = 0.3
    elif project_type == PROJECT_MILITARY_REFORM:
        faction.military_tradition = round(min(1.0, float(faction.military_tradition or 0.0) + 0.055), 3)
        faction.military_reform_pressure = round(max(0.0, float(faction.military_reform_pressure or 0.0) - 0.16), 3)
        project_amount = 0.24
        world.events.append(Event(
            turn=world.turn,
            type="military_reform",
            faction=faction_name,
            region=region.name,
            details={
                "region_display_name": region.display_name,
                "military_tradition": faction.military_tradition,
                "military_reform_pressure": faction.military_reform_pressure,
            },
            tags=["military", "reform"],
            significance=project_amount,
        ))
    region.last_military_project_turn = world.turn
    refresh_military_state(world, emit_events=False)
    return project_amount
