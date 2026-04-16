from __future__ import annotations

from copy import deepcopy

from src.config import (
    CORE_INCOME_FACTOR,
    FRONTIER_ATTACK_PROJECTION_PENALTY,
    FRONTIER_INCOME_FACTOR,
    FRONTIER_MAINTENANCE_SURCHARGE,
    HOMELAND_INCOME_FACTOR,
    REGION_MAINTENANCE_COST,
)
from src.models import Region, WorldState


HOMELAND_INTEGRATION_SCORE = 10.0
CORE_INTEGRATION_SCORE = 6.0
CONQUEST_INTEGRATION_SCORE = 1.0
PER_TURN_FRONTIER_GAIN = 1.0
PER_TURN_CORE_GAIN = 0.35


def get_region_core_status(region: Region) -> str:
    if region.owner is None:
        return "frontier"
    if region.homeland_faction_id == region.owner:
        return "homeland"
    if region.integration_score >= CORE_INTEGRATION_SCORE:
        return "core"
    return "frontier"


def get_region_core_defense_bonus(region: Region) -> int:
    status = get_region_core_status(region)
    if status == "homeland":
        return 2
    if status == "core":
        return 1
    return 0


def get_region_income_factor(region: Region) -> float:
    status = get_region_core_status(region)
    if status == "homeland":
        return HOMELAND_INCOME_FACTOR
    if status == "core":
        return CORE_INCOME_FACTOR
    return FRONTIER_INCOME_FACTOR


def get_region_effective_income(region: Region) -> int:
    return int(round(region.resources * get_region_income_factor(region)))


def get_region_maintenance_cost(region: Region) -> int:
    status = get_region_core_status(region)
    if status == "frontier":
        return REGION_MAINTENANCE_COST + FRONTIER_MAINTENANCE_SURCHARGE
    return REGION_MAINTENANCE_COST


def get_region_attack_projection_modifier(region: Region) -> int:
    if get_region_core_status(region) == "frontier":
        return -FRONTIER_ATTACK_PROJECTION_PENALTY
    return 0


def set_region_integration(
    region: Region,
    *,
    owner: str | None,
    score: float,
    ownership_turns: int,
    core_status: str | None = None,
) -> None:
    region.integrated_owner = owner
    region.integration_score = score
    region.ownership_turns = ownership_turns
    region.core_status = core_status or get_region_core_status(region)


def initialize_heartlands(world: WorldState) -> None:
    owned_counts: dict[str, int] = {}

    for region_name, region in sorted(world.regions.items()):
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.ownership_turns = 0
            continue

        owned_count = owned_counts.get(region.owner, 0)
        if owned_count == 0:
            region.homeland_faction_id = region.owner
            set_region_integration(
                region,
                owner=region.owner,
                score=HOMELAND_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="homeland",
            )
        else:
            set_region_integration(
                region,
                owner=region.owner,
                score=CORE_INTEGRATION_SCORE,
                ownership_turns=1,
                core_status="core",
            )
        owned_counts[region.owner] = owned_count + 1


def handle_region_owner_change(region: Region, new_owner: str | None) -> None:
    previous_owner = region.owner
    if previous_owner == new_owner:
        return

    region.owner = new_owner
    if previous_owner is not None and new_owner is not None:
        region.conquest_count += 1

    if new_owner is None:
        set_region_integration(
            region,
            owner=None,
            score=0.0,
            ownership_turns=0,
            core_status="frontier",
        )
        return

    base_score = HOMELAND_INTEGRATION_SCORE if region.homeland_faction_id == new_owner else CONQUEST_INTEGRATION_SCORE
    base_status = "homeland" if region.homeland_faction_id == new_owner else "frontier"
    set_region_integration(
        region,
        owner=new_owner,
        score=base_score,
        ownership_turns=1,
        core_status=base_status,
    )


def update_region_integration(world: WorldState) -> None:
    for region in world.regions.values():
        if region.owner is None:
            region.integrated_owner = None
            region.integration_score = 0.0
            region.core_status = "frontier"
            region.ownership_turns = 0
            continue

        if region.integrated_owner != region.owner:
            handle_region_owner_change(region, region.owner)
            continue

        if region.homeland_faction_id == region.owner:
            region.integration_score = max(region.integration_score, HOMELAND_INTEGRATION_SCORE)
            region.ownership_turns += 1
            region.core_status = "homeland"
            continue

        region.ownership_turns += 1
        if region.integration_score < CORE_INTEGRATION_SCORE:
            region.integration_score += PER_TURN_FRONTIER_GAIN
        else:
            region.integration_score += PER_TURN_CORE_GAIN
        region.core_status = get_region_core_status(region)


def build_region_snapshot(world: WorldState) -> dict[str, dict]:
    return {
        region_name: {
            "owner": region.owner,
            "resources": region.resources,
            "display_name": region.display_name,
            "founding_name": region.founding_name,
            "original_namer_faction_id": region.original_namer_faction_id,
            "terrain_tags": list(region.terrain_tags),
            "homeland_faction_id": region.homeland_faction_id,
            "integrated_owner": region.integrated_owner,
            "integration_score": round(region.integration_score, 2),
            "core_status": region.core_status,
        }
        for region_name, region in world.regions.items()
    }


def initialize_region_history(world: WorldState) -> None:
    world.region_history = [deepcopy(build_region_snapshot(world))]


def record_region_history(world: WorldState) -> None:
    world.region_history.append(deepcopy(build_region_snapshot(world)))
