from __future__ import annotations

import random

from src.models import Event, Faction, Region, ShockState, WorldState
from src.resources import (
    EXTRACTIVE_RESOURCES,
    FOOD_RESOURCES,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_LIVESTOCK,
    RESOURCE_STONE,
    RESOURCE_TIMBER,
    RESOURCE_WILD_FOOD,
)


SHOCK_CLIMATE_ANOMALY = "climate_anomaly"
SHOCK_FAMINE = "famine"
SHOCK_EPIDEMIC = "epidemic"
SHOCK_SOIL_EXHAUSTION = "soil_exhaustion"
SHOCK_ECOLOGICAL_DEGRADATION = "ecological_degradation"
SHOCK_RESOURCE_DEPLETION = "resource_depletion"
SHOCK_TRADE_COLLAPSE = "trade_collapse"
SHOCK_RECOVERY = "recovery"

SHOCK_EVENT_TYPES = {
    SHOCK_CLIMATE_ANOMALY: "shock_climate_anomaly",
    SHOCK_FAMINE: "shock_famine",
    SHOCK_EPIDEMIC: "shock_epidemic",
    SHOCK_SOIL_EXHAUSTION: "shock_soil_exhaustion",
    SHOCK_ECOLOGICAL_DEGRADATION: "shock_ecological_degradation",
    SHOCK_RESOURCE_DEPLETION: "shock_resource_depletion",
    SHOCK_TRADE_COLLAPSE: "shock_trade_collapse",
    SHOCK_RECOVERY: "shock_recovery",
}

SHOCK_LABELS = {
    SHOCK_CLIMATE_ANOMALY: "Climate Anomaly",
    SHOCK_FAMINE: "Famine",
    SHOCK_EPIDEMIC: "Epidemic",
    SHOCK_SOIL_EXHAUSTION: "Soil Exhaustion",
    SHOCK_ECOLOGICAL_DEGRADATION: "Ecological Degradation",
    SHOCK_RESOURCE_DEPLETION: "Resource Depletion",
    SHOCK_TRADE_COLLAPSE: "Trade Network Collapse",
    SHOCK_RECOVERY: "Shock Recovery",
}

SHOCK_DECAY_BY_KIND = {
    SHOCK_CLIMATE_ANOMALY: 0.08,
    SHOCK_FAMINE: 0.06,
    SHOCK_EPIDEMIC: 0.07,
    SHOCK_SOIL_EXHAUSTION: 0.025,
    SHOCK_ECOLOGICAL_DEGRADATION: 0.022,
    SHOCK_RESOURCE_DEPLETION: 0.018,
    SHOCK_TRADE_COLLAPSE: 0.075,
}

BASE_DURATIONS = {
    SHOCK_CLIMATE_ANOMALY: 3,
    SHOCK_FAMINE: 4,
    SHOCK_EPIDEMIC: 4,
    SHOCK_SOIL_EXHAUSTION: 8,
    SHOCK_ECOLOGICAL_DEGRADATION: 10,
    SHOCK_RESOURCE_DEPLETION: 12,
    SHOCK_TRADE_COLLAPSE: 4,
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_region_shock_state(region: Region) -> None:
    region.soil_health = round(_clamp(float(region.soil_health or 0.0), 0.0, 1.0), 3)
    region.ecological_integrity = round(_clamp(float(region.ecological_integrity or 0.0), 0.0, 1.0), 3)
    region.disease_burden = round(_clamp(float(region.disease_burden or 0.0), 0.0, 1.0), 3)
    region.climate_anomaly = round(_clamp(float(region.climate_anomaly or 0.0), 0.0, 1.0), 3)
    region.resource_depletion = round(_clamp(float(region.resource_depletion or 0.0), 0.0, 1.0), 3)
    region.food_stress_turns = max(0, int(region.food_stress_turns or 0))
    region.trade_stress_turns = max(0, int(region.trade_stress_turns or 0))
    region.active_shock_kinds = list(dict.fromkeys(region.active_shock_kinds or []))
    region.shock_exposure = round(_clamp(float(region.shock_exposure or 0.0), 0.0, 1.0), 3)
    region.shock_resilience = round(_clamp(float(region.shock_resilience or 0.0), 0.0, 1.0), 3)


def _normalize_faction_shock_state(faction: Faction) -> None:
    faction.shock_exposure = round(_clamp(float(faction.shock_exposure or 0.0), 0.0, 1.0), 3)
    faction.shock_resilience = round(_clamp(float(faction.shock_resilience or 0.0), 0.0, 1.0), 3)
    faction.famine_pressure = round(_clamp(float(faction.famine_pressure or 0.0), 0.0, 1.0), 3)
    faction.epidemic_pressure = round(_clamp(float(faction.epidemic_pressure or 0.0), 0.0, 1.0), 3)
    faction.trade_collapse_exposure = round(_clamp(float(faction.trade_collapse_exposure or 0.0), 0.0, 1.0), 3)


def _active_region_shocks(world: WorldState, region_name: str, kind: str | None = None) -> list[ShockState]:
    return [
        shock
        for shock in world.active_shocks
        if region_name in shock.affected_regions
        and (kind is None or shock.kind == kind)
    ]


def get_region_active_shock_intensity(
    world: WorldState | None,
    region: Region,
    kind: str | None = None,
) -> float:
    if world is None:
        return 0.0
    return round(
        _clamp(
            sum(max(0.0, shock.intensity) for shock in _active_region_shocks(world, region.name, kind)),
            0.0,
            1.0,
        ),
        3,
    )


def _region_has_active_shock(world: WorldState, region_name: str, kind: str) -> bool:
    return any(_active_region_shocks(world, region_name, kind))


def _shock_id(world: WorldState, kind: str, origin_region: str | None) -> str:
    serial = len(world.shock_history) + len(world.active_shocks) + 1
    origin = origin_region or "realm"
    return f"{kind}:{origin}:{world.turn}:{serial}"


def _neighbor_regions(world: WorldState, region: Region) -> list[Region]:
    neighbors = []
    for neighbor_name in region.neighbors:
        neighbor = world.regions.get(neighbor_name)
        if neighbor is not None:
            neighbors.append(neighbor)
    return neighbors


def _shock_affected_regions(world: WorldState, region: Region, kind: str, intensity: float) -> list[str]:
    affected = {region.name}
    if kind in {SHOCK_CLIMATE_ANOMALY, SHOCK_EPIDEMIC, SHOCK_TRADE_COLLAPSE}:
        spread_limit = 1 if intensity < 0.65 else 2
        frontier = [region]
        for _ in range(spread_limit):
            next_frontier: list[Region] = []
            for frontier_region in frontier:
                for neighbor in _neighbor_regions(world, frontier_region):
                    if neighbor.owner is None:
                        continue
                    affected.add(neighbor.name)
                    next_frontier.append(neighbor)
            frontier = next_frontier
    if kind == SHOCK_TRADE_COLLAPSE:
        for other_region in world.regions.values():
            if other_region.owner == region.owner and (
                other_region.resource_route_anchor == region.name
                or other_region.trade_route_parent == region.name
                or other_region.trade_gateway_role != "none"
            ):
                affected.add(other_region.name)
    return sorted(affected)


def _emit_shock_event(
    world: WorldState,
    shock: ShockState,
    *,
    recovered: bool = False,
) -> None:
    event_type = SHOCK_EVENT_TYPES[SHOCK_RECOVERY if recovered else shock.kind]
    primary_region = shock.origin_region
    faction_name = shock.faction
    if faction_name is None and primary_region in world.regions:
        faction_name = world.regions[primary_region].owner
    if faction_name is None:
        faction_name = "environment"
    shock_label = SHOCK_LABELS.get(shock.kind, shock.kind.replace("_", " ").title())
    world.events.append(Event(
        turn=world.turn,
        type=event_type,
        faction=faction_name,
        region=primary_region,
        details={
            "shock_id": shock.id,
            "shock_kind": shock.kind,
            "shock_label": f"Recovery from {shock_label}" if recovered else shock_label,
            "recovered": recovered,
            "intensity": round(shock.intensity, 3),
            "phase": shock.phase,
            "duration": shock.duration_turns,
            "affected_region_count": len(shock.affected_regions),
            "affected_regions": list(shock.affected_regions[:8]),
        },
        context=dict(shock.drivers),
        impact=dict(shock.effects),
        tags=["shock", shock.kind, *(["recovery"] if recovered else [])],
        significance=round(max(0.0, shock.intensity) * max(1, len(shock.affected_regions)), 3),
    ))


def start_shock(
    world: WorldState,
    kind: str,
    origin_region: str,
    *,
    intensity: float,
    duration_turns: int | None = None,
    drivers: dict[str, float] | None = None,
    effects: dict[str, float] | None = None,
    emit_event: bool = True,
) -> ShockState | None:
    region = world.regions.get(origin_region)
    if region is None or region.owner is None:
        return None
    intensity = round(_clamp(intensity, 0.05, 1.0), 3)
    existing = _active_region_shocks(world, origin_region, kind)
    if existing:
        shock = existing[0]
        shock.intensity = round(max(shock.intensity, intensity), 3)
        shock.duration_turns = max(shock.duration_turns, duration_turns or BASE_DURATIONS.get(kind, 4))
        shock.drivers.update(drivers or {})
        shock.effects.update(effects or {})
        return shock

    affected_regions = _shock_affected_regions(world, region, kind, intensity)
    shock = ShockState(
        id=_shock_id(world, kind, origin_region),
        kind=kind,
        origin_region=origin_region,
        affected_regions=affected_regions,
        faction=region.owner,
        started_turn=world.turn,
        duration_turns=duration_turns or BASE_DURATIONS.get(kind, 4),
        intensity=intensity,
        phase="onset",
        drivers=drivers or {},
        effects=effects or {},
    )
    world.active_shocks.append(shock)
    if emit_event:
        _emit_shock_event(world, shock)
    return shock


def _age_active_shocks(world: WorldState) -> None:
    remaining: list[ShockState] = []
    for shock in world.active_shocks:
        shock.duration_turns -= 1
        age = world.turn - shock.started_turn
        if shock.duration_turns <= 1:
            shock.phase = "recovery"
        elif age >= 1:
            shock.phase = "peak"
        shock.intensity = round(
            max(0.0, shock.intensity - SHOCK_DECAY_BY_KIND.get(shock.kind, 0.05)),
            3,
        )
        if shock.duration_turns <= 0 or shock.intensity < 0.05:
            world.shock_history.append(shock)
            _emit_shock_event(world, shock, recovered=True)
        else:
            remaining.append(shock)
    world.active_shocks = remaining


def get_region_shock_resilience(region: Region, world: WorldState | None = None) -> float:
    storage_ratio = _clamp(float(region.food_stored or 0.0) / max(0.1, float(region.food_consumption or 0.0) * 2.0), 0.0, 1.0)
    infrastructure = _clamp(
        (
            float(region.granary_level or 0.0)
            + float(region.storehouse_level or 0.0)
            + float(region.infrastructure_level or 0.0)
            + float(region.road_level or 0.0)
            + float(region.market_level or 0.0)
        ) / 6.0,
        0.0,
        1.0,
    )
    ecological_base = (float(region.soil_health or 0.0) + float(region.ecological_integrity or 0.0)) / 2.0
    trade_buffer = 1.0 - _clamp(float(region.trade_import_reliance or 0.0), 0.0, 1.0)
    unrest_buffer = 1.0 - _clamp(float(region.unrest or 0.0) / 10.0, 0.0, 1.0)
    tech_buffer = _clamp(
        (
            float(region.technology_adoption.get("irrigation_methods", 0.0))
            + float(region.technology_adoption.get("pastoral_breeding", 0.0))
            + float(region.technology_adoption.get("road_administration", 0.0))
            + float(region.technology_adoption.get("market_accounting", 0.0))
            + float(region.technology_adoption.get("temple_recordkeeping", 0.0))
        ) / 5.0,
        0.0,
        1.0,
    )
    resilience = (
        0.18
        + (storage_ratio * 0.18)
        + (infrastructure * 0.2)
        + (ecological_base * 0.16)
        + (trade_buffer * 0.1)
        + (unrest_buffer * 0.1)
        + (tech_buffer * 0.08)
    )
    if world is not None and region.owner in world.factions:
        faction = world.factions[region.owner]
        resilience += min(0.08, float(faction.administrative_efficiency or 1.0) * 0.035)
    return round(_clamp(resilience, 0.05, 0.95), 3)


def _food_deficit_ratio(region: Region) -> float:
    return _clamp(float(region.food_deficit or 0.0) / max(0.2, float(region.food_consumption or 0.0)), 0.0, 1.0)


def _update_region_long_memory(world: WorldState) -> None:
    for region in world.regions.values():
        _normalize_region_shock_state(region)
        if region.owner is None:
            region.active_shock_kinds = []
            region.shock_exposure = 0.0
            region.shock_resilience = 0.0
            continue

        grain_pressure = max(0.0, float(region.resource_output.get(RESOURCE_GRAIN, 0.0)))
        livestock_pressure = max(0.0, float(region.resource_output.get(RESOURCE_LIVESTOCK, 0.0)))
        timber_pressure = max(0.0, float(region.resource_output.get(RESOURCE_TIMBER, 0.0)))
        extractive_pressure = (
            max(0.0, float(region.resource_output.get(RESOURCE_COPPER, 0.0)))
            + max(0.0, float(region.resource_output.get(RESOURCE_STONE, 0.0)))
        )
        population_pressure = _clamp(float(region.population or 0) / 360.0, 0.0, 1.2)

        soil_loss = min(
            0.018,
            (grain_pressure * 0.0028)
            + (float(region.agriculture_level or 0.0) * 0.003)
            + (population_pressure * 0.002),
        )
        soil_recovery = 0.006 + min(0.006, float(region.irrigation_level or 0.0) * 0.002)
        if grain_pressure < 0.8:
            soil_recovery += 0.004
        region.soil_health = round(_clamp(region.soil_health - soil_loss + soil_recovery, 0.0, 1.0), 3)

        ecological_loss = min(
            0.02,
            (timber_pressure * 0.0035)
            + (extractive_pressure * 0.0022)
            + (livestock_pressure * 0.0016)
            + (population_pressure * 0.0025)
            + (sum(region.resource_damage.values()) / max(1, len(region.resource_damage)) * 0.008),
        )
        ecological_recovery = 0.005 if timber_pressure < 0.7 and extractive_pressure < 0.7 else 0.002
        region.ecological_integrity = round(
            _clamp(region.ecological_integrity - ecological_loss + ecological_recovery, 0.0, 1.0),
            3,
        )

        if extractive_pressure > 1.6 or float(region.extractive_level or 0.0) > 1.8:
            region.resource_depletion = round(
                _clamp(region.resource_depletion + min(0.018, extractive_pressure * 0.003), 0.0, 1.0),
                3,
            )
        else:
            region.resource_depletion = round(_clamp(region.resource_depletion - 0.004, 0.0, 1.0), 3)

        region.disease_burden = round(_clamp(region.disease_burden * 0.86, 0.0, 1.0), 3)
        region.climate_anomaly = round(_clamp(region.climate_anomaly * 0.82, 0.0, 1.0), 3)


def _generate_slow_ecology_shocks(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None:
            continue
        resilience = get_region_shock_resilience(region, world)
        if region.soil_health < 0.58 and not _region_has_active_shock(world, region.name, SHOCK_SOIL_EXHAUSTION):
            start_shock(
                world,
                SHOCK_SOIL_EXHAUSTION,
                region.name,
                intensity=_clamp((0.72 - region.soil_health) * 1.25, 0.12, 0.8),
                drivers={"soil_health": region.soil_health, "resilience": resilience},
                effects={"grain_output_factor": round(1.0 - ((0.72 - region.soil_health) * 0.35), 3)},
            )
        if region.ecological_integrity < 0.55 and not _region_has_active_shock(world, region.name, SHOCK_ECOLOGICAL_DEGRADATION):
            start_shock(
                world,
                SHOCK_ECOLOGICAL_DEGRADATION,
                region.name,
                intensity=_clamp((0.68 - region.ecological_integrity) * 1.3, 0.12, 0.85),
                drivers={"ecological_integrity": region.ecological_integrity, "resilience": resilience},
                effects={"wild_output_factor": round(1.0 - ((0.68 - region.ecological_integrity) * 0.32), 3)},
            )
        if region.resource_depletion > 0.34 and not _region_has_active_shock(world, region.name, SHOCK_RESOURCE_DEPLETION):
            start_shock(
                world,
                SHOCK_RESOURCE_DEPLETION,
                region.name,
                intensity=_clamp(region.resource_depletion, 0.15, 0.9),
                drivers={"resource_depletion": region.resource_depletion, "resilience": resilience},
                effects={"extractive_output_factor": round(1.0 - (region.resource_depletion * 0.28), 3)},
            )


def _maybe_generate_climate_anomalies(world: WorldState) -> None:
    if not world.regions:
        return
    cadence_pressure = 0.0
    if world.turn > 0 and world.turn % 11 == 0:
        cadence_pressure += 0.1
    if world.turn > 0 and world.turn % 17 == 0:
        cadence_pressure += 0.08
    for region in world.regions.values():
        if region.owner is None or _region_has_active_shock(world, region.name, SHOCK_CLIMATE_ANOMALY):
            continue
        vulnerability = (
            (1.0 - get_region_shock_resilience(region, world)) * 0.12
            + max(0.0, 0.72 - region.soil_health) * 0.08
            + max(0.0, 0.7 - region.ecological_integrity) * 0.07
            + cadence_pressure
        )
        if random.random() >= _clamp(vulnerability, 0.0, 0.28):
            continue
        intensity = _clamp(0.22 + vulnerability + random.random() * 0.22, 0.16, 0.82)
        region.climate_anomaly = round(max(region.climate_anomaly, intensity), 3)
        start_shock(
            world,
            SHOCK_CLIMATE_ANOMALY,
            region.name,
            intensity=intensity,
            drivers={
                "vulnerability": round(vulnerability, 3),
                "soil_health": region.soil_health,
                "ecological_integrity": region.ecological_integrity,
            },
            effects={
                "food_output_factor": round(1.0 - intensity * 0.34, 3),
                "spoilage_add": round(intensity * 0.018, 3),
            },
        )


def refresh_long_cycle_shocks(world: WorldState) -> None:
    _age_active_shocks(world)
    _update_region_long_memory(world)
    _generate_slow_ecology_shocks(world)
    _maybe_generate_climate_anomalies(world)
    update_shock_rollups(world)


def resolve_food_and_disease_shocks(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None:
            continue
        deficit_ratio = _food_deficit_ratio(region)
        if deficit_ratio >= 0.25:
            region.food_stress_turns += 1
        else:
            region.food_stress_turns = max(0, region.food_stress_turns - 1)

        resilience = get_region_shock_resilience(region, world)
        famine_pressure = (
            deficit_ratio * 0.68
            + min(0.28, region.food_stress_turns * 0.08)
            + get_region_active_shock_intensity(world, region, SHOCK_CLIMATE_ANOMALY) * 0.22
            + (1.0 - resilience) * 0.18
        )
        if famine_pressure >= 0.52:
            intensity = _clamp(famine_pressure - (resilience * 0.24), 0.12, 0.95)
            start_shock(
                world,
                SHOCK_FAMINE,
                region.name,
                intensity=intensity,
                drivers={
                    "food_deficit_ratio": round(deficit_ratio, 3),
                    "food_stress_turns": region.food_stress_turns,
                    "resilience": resilience,
                },
                effects={
                    "population_loss_ratio": round(intensity * 0.018, 3),
                    "unrest_pressure": round(intensity * 0.42, 3),
                    "migration_pressure": round(intensity * 0.28, 3),
                },
            )

        epidemic_pressure = (
            _clamp(float(region.population or 0) / 480.0, 0.0, 0.42)
            + {"wild": 0.0, "rural": 0.04, "town": 0.1, "city": 0.17}.get(region.settlement_level, 0.0)
            + _clamp(float(region.trade_throughput or 0.0) / 16.0, 0.0, 0.18)
            + _clamp(float(region.refugee_inflow or 0) / 140.0, 0.0, 0.18)
            + get_region_active_shock_intensity(world, region, SHOCK_FAMINE) * 0.2
            - resilience * 0.22
        )
        epidemic_chance = _clamp((epidemic_pressure - 0.34) * 0.75, 0.0, 0.42)
        if epidemic_pressure >= 0.56 and random.random() < epidemic_chance:
            intensity = _clamp(epidemic_pressure, 0.12, 0.9)
            region.disease_burden = round(max(region.disease_burden, intensity), 3)
            start_shock(
                world,
                SHOCK_EPIDEMIC,
                region.name,
                intensity=intensity,
                drivers={
                    "epidemic_pressure": round(epidemic_pressure, 3),
                    "population": region.population,
                    "trade_throughput": round(float(region.trade_throughput or 0.0), 3),
                    "refugee_inflow": int(region.refugee_inflow or 0),
                },
                effects={
                    "population_loss_ratio": round(intensity * 0.014, 3),
                    "workforce_factor": round(1.0 - intensity * 0.26, 3),
                    "trade_factor": round(1.0 - intensity * 0.22, 3),
                },
            )

    update_shock_rollups(world)


def resolve_trade_network_shocks(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None:
            continue
        trade_pressure = (
            _clamp(float(region.trade_disruption_risk or 0.0), 0.0, 1.0) * 0.42
            + _clamp(float(region.trade_import_reliance or 0.0), 0.0, 1.0) * 0.2
            + _clamp(float(region.trade_warfare_pressure or 0.0), 0.0, 1.0) * 0.18
            + _clamp(float(region.trade_blockade_strength or 0.0), 0.0, 1.0) * 0.22
            + get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC) * 0.16
            + (0.12 if region.trade_route_role in {"hub", "corridor"} else 0.0)
        )
        if trade_pressure >= 0.42:
            region.trade_stress_turns += 1
        else:
            region.trade_stress_turns = max(0, region.trade_stress_turns - 1)
        if trade_pressure + min(0.22, region.trade_stress_turns * 0.05) < 0.58:
            continue
        start_shock(
            world,
            SHOCK_TRADE_COLLAPSE,
            region.name,
            intensity=_clamp(trade_pressure, 0.16, 0.92),
            drivers={
                "trade_pressure": round(trade_pressure, 3),
                "trade_stress_turns": region.trade_stress_turns,
                "trade_disruption_risk": round(float(region.trade_disruption_risk or 0.0), 3),
                "trade_import_reliance": round(float(region.trade_import_reliance or 0.0), 3),
            },
            effects={
                "trade_factor": round(1.0 - min(0.6, trade_pressure * 0.52), 3),
                "import_loss_factor": round(min(0.72, trade_pressure * 0.5), 3),
            },
        )
    update_shock_rollups(world)


def apply_shock_population_losses(world: WorldState) -> None:
    from src.population import apply_region_population_loss

    for region in world.regions.values():
        if region.population <= 0 or region.owner is None:
            continue
        famine = get_region_active_shock_intensity(world, region, SHOCK_FAMINE)
        epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
        crisis = max(famine * 0.012, epidemic * 0.016)
        if crisis <= 0.0:
            continue
        loss = apply_region_population_loss(region, crisis, minimum_loss=1)
        if loss > 0:
            world.events.append(Event(
                turn=world.turn,
                type="shock_population_loss",
                faction=region.owner,
                region=region.name,
                details={
                    "population_loss": loss,
                    "famine_intensity": round(famine, 3),
                    "epidemic_intensity": round(epidemic, 3),
                },
                tags=["shock", "population", "mortality"],
                significance=round(loss / max(1, region.population + loss), 3),
            ))


def update_shock_rollups(world: WorldState) -> None:
    active_by_region = {
        region_name: _active_region_shocks(world, region_name)
        for region_name in world.regions
    }
    for region_name, region in world.regions.items():
        _normalize_region_shock_state(region)
        shocks = active_by_region[region_name]
        region.active_shock_kinds = sorted({shock.kind for shock in shocks})
        region.shock_exposure = round(_clamp(sum(shock.intensity for shock in shocks), 0.0, 1.0), 3)
        region.shock_resilience = get_region_shock_resilience(region, world) if region.owner is not None else 0.0

    for faction_name, faction in world.factions.items():
        owned_regions = [region for region in world.regions.values() if region.owner == faction_name]
        if not owned_regions:
            faction.shock_exposure = 0.0
            faction.shock_resilience = 0.0
            faction.famine_pressure = 0.0
            faction.epidemic_pressure = 0.0
            faction.trade_collapse_exposure = 0.0
            continue
        total_population = sum(max(1, region.population) for region in owned_regions)

        def weighted_metric(getter) -> float:
            return sum(getter(region) * max(1, region.population) for region in owned_regions) / max(1, total_population)

        faction.shock_exposure = round(_clamp(weighted_metric(lambda region: region.shock_exposure), 0.0, 1.0), 3)
        faction.shock_resilience = round(_clamp(weighted_metric(lambda region: region.shock_resilience), 0.0, 1.0), 3)
        faction.famine_pressure = round(_clamp(weighted_metric(lambda region: get_region_active_shock_intensity(world, region, SHOCK_FAMINE)), 0.0, 1.0), 3)
        faction.epidemic_pressure = round(_clamp(weighted_metric(lambda region: get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)), 0.0, 1.0), 3)
        faction.trade_collapse_exposure = round(_clamp(weighted_metric(lambda region: get_region_active_shock_intensity(world, region, SHOCK_TRADE_COLLAPSE)), 0.0, 1.0), 3)
        _normalize_faction_shock_state(faction)


def get_region_resource_shock_factor(
    region: Region,
    world: WorldState | None,
    resource_name: str,
) -> float:
    climate = get_region_active_shock_intensity(world, region, SHOCK_CLIMATE_ANOMALY)
    famine = get_region_active_shock_intensity(world, region, SHOCK_FAMINE)
    epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
    soil = get_region_active_shock_intensity(world, region, SHOCK_SOIL_EXHAUSTION)
    ecology = get_region_active_shock_intensity(world, region, SHOCK_ECOLOGICAL_DEGRADATION)
    depletion = max(
        get_region_active_shock_intensity(world, region, SHOCK_RESOURCE_DEPLETION),
        float(region.resource_depletion or 0.0),
    )
    factor = 1.0
    if resource_name in FOOD_RESOURCES:
        factor *= 1.0 - min(0.36, climate * 0.34)
        factor *= 1.0 - min(0.22, famine * 0.16)
    if resource_name == RESOURCE_GRAIN:
        factor *= _clamp(0.58 + float(region.soil_health or 0.0) * 0.42, 0.58, 1.0)
        factor *= 1.0 - min(0.32, soil * 0.32)
    if resource_name in {RESOURCE_WILD_FOOD, RESOURCE_TIMBER}:
        factor *= _clamp(0.56 + float(region.ecological_integrity or 0.0) * 0.44, 0.56, 1.0)
        factor *= 1.0 - min(0.34, ecology * 0.3)
    if resource_name in EXTRACTIVE_RESOURCES:
        factor *= 1.0 - min(0.42, depletion * 0.36)
    factor *= 1.0 - min(0.28, epidemic * 0.24)
    return round(_clamp(factor, 0.25, 1.08), 3)


def get_region_workforce_shock_factor(region: Region, world: WorldState | None) -> float:
    epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
    famine = get_region_active_shock_intensity(world, region, SHOCK_FAMINE)
    return round(_clamp(1.0 - min(0.32, epidemic * 0.28) - min(0.18, famine * 0.12), 0.45, 1.0), 3)


def get_region_food_spoilage_shock_modifier(region: Region, world: WorldState | None) -> float:
    climate = get_region_active_shock_intensity(world, region, SHOCK_CLIMATE_ANOMALY)
    epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
    return round(min(0.055, climate * 0.018 + epidemic * 0.012), 3)


def get_region_trade_shock_factor(region: Region, world: WorldState | None) -> float:
    trade = get_region_active_shock_intensity(world, region, SHOCK_TRADE_COLLAPSE)
    epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
    famine = get_region_active_shock_intensity(world, region, SHOCK_FAMINE)
    return round(
        _clamp(
            1.0 - min(0.56, trade * 0.52) - min(0.18, epidemic * 0.18) - min(0.12, famine * 0.08),
            0.24,
            1.0,
        ),
        3,
    )


def get_region_trade_disruption_shock(region: Region, world: WorldState | None) -> float:
    trade = get_region_active_shock_intensity(world, region, SHOCK_TRADE_COLLAPSE)
    epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
    return round(min(0.42, trade * 0.34 + epidemic * 0.08), 3)


def get_region_migration_shock_pressure(region: Region, world: WorldState | None) -> float:
    famine = get_region_active_shock_intensity(world, region, SHOCK_FAMINE)
    epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
    climate = get_region_active_shock_intensity(world, region, SHOCK_CLIMATE_ANOMALY)
    ecology = get_region_active_shock_intensity(world, region, SHOCK_ECOLOGICAL_DEGRADATION)
    return round(min(0.42, famine * 0.24 + epidemic * 0.16 + climate * 0.1 + ecology * 0.08), 3)


def get_region_migration_shock_attraction_penalty(region: Region, world: WorldState | None) -> float:
    return round(min(0.38, region.shock_exposure * 0.32 + float(region.disease_burden or 0.0) * 0.12), 3)


def get_region_unrest_shock_pressure(region: Region, world: WorldState | None) -> float:
    famine = get_region_active_shock_intensity(world, region, SHOCK_FAMINE)
    epidemic = get_region_active_shock_intensity(world, region, SHOCK_EPIDEMIC)
    trade = get_region_active_shock_intensity(world, region, SHOCK_TRADE_COLLAPSE)
    slow = max(
        get_region_active_shock_intensity(world, region, SHOCK_SOIL_EXHAUSTION),
        get_region_active_shock_intensity(world, region, SHOCK_ECOLOGICAL_DEGRADATION),
        get_region_active_shock_intensity(world, region, SHOCK_RESOURCE_DEPLETION),
    )
    return round(min(1.25, famine * 0.48 + epidemic * 0.28 + trade * 0.32 + slow * 0.18), 3)


def get_region_shock_summary(region: Region) -> str:
    if not region.active_shock_kinds:
        return "None"
    labels = [SHOCK_LABELS.get(kind, kind.replace("_", " ").title()) for kind in region.active_shock_kinds]
    return ", ".join(labels)
