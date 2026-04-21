import random

from src.diplomacy import get_attack_diplomacy_modifier, get_relationship_status
from src.config import (
    ATTACK_COST,
    ATTACK_FAILURE_PENALTY,
    ATTACK_SUCCESS_MAX,
    ATTACK_SUCCESS_MIN,
    ATTACK_SUCCESS_STRENGTH_FACTOR,
    DIPLOMACY_ETHNIC_CLAIM_ATTACK_BONUS,
    EXPANSION_COST,
    MIN_TREASURY_CONCENTRATION,
    POPULATION_ATTACK_FAILURE_LOSS,
    POPULATION_ATTACK_SUCCESS_LOSS,
    POPULATION_EXPANSION_TRANSFER_MIN,
    POPULATION_EXPANSION_TRANSFER_RATIO,
    REGIME_CLAIMANT_ATTACK_SCORE_BONUS,
    REGIME_CLAIMANT_ATTACK_STRENGTH_BONUS,
    REGIME_SPLIT_ATTACK_SCORE_BONUS,
    REGIME_SPLIT_ATTACK_STRENGTH_BONUS,
    REBEL_PROTO_TREASURY_CONCENTRATION_FACTOR,
    REBEL_REABSORPTION_UNREST,
    TREASURY_CONCENTRATION_REGION_FACTOR,
)
from src.doctrine import get_faction_region_alignment
from src.region_state import (
    get_region_attack_projection_modifier,
    get_region_core_defense_bonus,
    get_region_core_status,
)
from src.resource_economy import (
    apply_region_resource_damage,
    get_region_taxable_value,
    update_faction_resource_economy,
)
from src.heartland import (
    apply_region_population_loss,
    factions_have_same_ethnicity_regime_tension,
    faction_has_ethnic_claim,
    get_region_dominant_ethnicity,
    get_rebel_reclaim_bonus,
    handle_region_owner_change,
    set_region_unrest,
    transfer_region_population,
)
from src.models import Event
from src.resources import (
    CAPACITY_FOOD_SECURITY,
    CAPACITY_METAL,
    CAPACITY_MOBILITY,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_STONE,
    RESOURCE_TIMBER,
    RESOURCE_WILD_FOOD,
    format_resource_map,
)
from src.region_naming import assign_region_founding_name, format_region_reference
from src.terrain import get_terrain_profile
from src.visibility import faction_knows_region


def get_expandable_regions(faction_name, world):
    """Returns a list of Regions the given faction is capable of expanding into."""

    expandable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner != faction_name or not faction_knows_region(world, faction_name, region.name):
            continue
        for neighbor_name in region.neighbors:
            if not faction_knows_region(world, faction_name, neighbor_name):
                continue
            neighbor = world.regions[neighbor_name]
            if neighbor.owner is None:
                expandable_regions.add(neighbor_name)

    return sorted(expandable_regions)


def get_attackable_regions(faction_name, world):
    """Returns adjacent enemy-owned regions the faction can attack."""

    attackable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner != faction_name or not faction_knows_region(world, faction_name, region.name):
            continue

        for neighbor_name in region.neighbors:
            if not faction_knows_region(world, faction_name, neighbor_name):
                continue
            neighbor = world.regions[neighbor_name]
            if (
                neighbor.owner is not None
                and neighbor.owner != faction_name
                and get_relationship_status(world, faction_name, neighbor.owner)
                not in {"alliance", "truce"}
            ):
                attackable_regions.add(neighbor_name)

    return sorted(attackable_regions)


def _get_region_resource_interest(region, faction_name, world) -> int:
    faction = world.factions.get(faction_name)
    if faction is None:
        return 0
    shortages = faction.resource_shortages
    bonus = 0
    if shortages.get(CAPACITY_FOOD_SECURITY, 0.0) > 0:
        bonus += int(
            round(
                region.resource_suitability.get(RESOURCE_GRAIN, 0.0) * 5
                + region.resource_wild_endowments.get("wild_food", 0.0) * 2
            )
        )
    if shortages.get(CAPACITY_MOBILITY, 0.0) > 0:
        bonus += int(round(region.resource_suitability.get(RESOURCE_HORSES, 0.0) * 4))
    if shortages.get(CAPACITY_METAL, 0.0) > 0:
        bonus += int(round(region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0) * 5))
    bonus += int(round(region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0) * 2))
    return bonus


def _get_region_strategic_value(region, world) -> float:
    return round(get_region_taxable_value(region, world), 2)


def _get_region_corridor_pressure(region) -> float:
    isolation = float(region.resource_isolation_factor or 0.0)
    bottleneck_gap = max(0.0, 0.82 - float(region.resource_route_bottleneck or 0.0))
    depth_pressure = min(0.35, (region.resource_route_depth or 0) * 0.05)
    return round(isolation + bottleneck_gap + depth_pressure, 3)


def _faction_has_established_resource_source(
    faction_name: str,
    resource_name: str,
    world,
    *,
    exclude_region_name: str | None = None,
) -> bool:
    for region in world.regions.values():
        if region.owner != faction_name:
            continue
        if exclude_region_name is not None and region.name == exclude_region_name:
            continue
        if region.resource_established.get(resource_name, 0.0) > 0.2:
            return True
    return False


def _get_owned_path_length(
    faction_name: str,
    source_region_name: str,
    target_region_name: str,
    world,
) -> int | None:
    if source_region_name == target_region_name:
        return 0
    queue = [(source_region_name, 0)]
    seen = {source_region_name}
    while queue:
        region_name, distance = queue.pop(0)
        for neighbor_name in world.regions[region_name].neighbors:
            if neighbor_name in seen:
                continue
            seen.add(neighbor_name)
            neighbor = world.regions[neighbor_name]
            if neighbor_name == target_region_name and neighbor.owner == faction_name:
                return distance + 1
            if neighbor.owner != faction_name:
                continue
            queue.append((neighbor_name, distance + 1))
    return None


def _get_best_resource_source_region(
    faction_name: str,
    target_region_name: str,
    resource_name: str,
    world,
):
    best = None
    for region in world.regions.values():
        if region.owner != faction_name:
            continue
        if region.name == target_region_name:
            continue
        if region.resource_established.get(resource_name, 0.0) <= 0.2:
            continue
        path_length = _get_owned_path_length(
            faction_name,
            region.name,
            target_region_name,
            world,
        )
        if path_length is None:
            continue
        candidate = (
            path_length,
            -region.resource_established.get(resource_name, 0.0),
            region.name,
        )
        if best is None or candidate < best[0]:
            best = (candidate, region)
    return None if best is None else best[1]


def _get_investment_project_options(faction_name: str, region, world) -> list[dict[str, float | str]]:
    faction = world.factions[faction_name]
    shortages = faction.resource_shortages
    options: list[dict[str, float | str]] = []
    corridor_pressure = _get_region_corridor_pressure(region)
    route_bottleneck = float(region.resource_route_bottleneck or 0.0)

    grain_suitability = region.resource_suitability.get(RESOURCE_GRAIN, 0.0)
    grain_established = region.resource_established.get(RESOURCE_GRAIN, 0.0)
    grain_source = _get_best_resource_source_region(
        faction_name,
        region.name,
        RESOURCE_GRAIN,
        world,
    )
    if (
        grain_suitability >= 0.35
        and grain_established < max(0.28, grain_suitability - 0.08)
        and grain_source is not None
    ):
        source_path = _get_owned_path_length(faction_name, grain_source.name, region.name, world) or 0
        options.append({
            "project_type": "introduce_grain",
            "score": 5.0 + (grain_suitability * 4.0) + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 2.8) - (source_path * 0.35),
            "resource_focus": RESOURCE_GRAIN,
            "source_region": grain_source.name,
        })
    if grain_established > 0 and region.agriculture_level < 1.6:
        options.append({
            "project_type": "improve_agriculture",
            "score": 3.5 + (grain_established * 3.0) + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 1.8),
            "resource_focus": RESOURCE_GRAIN,
        })
    local_storage_gap = max(0.0, region.food_produced - region.food_storage_capacity)
    local_food_waste = region.food_overflow + region.food_spoilage
    local_deficit_pressure = region.food_deficit
    if (
        region.granary_level < 1.8
        and (
            grain_established > 0
            or region.agriculture_level > 0.2
            or region.food_produced > 0.6
        )
    ):
        options.append({
            "project_type": "build_granary",
            "score": (
                3.2
                + (grain_established * 2.6)
                + (region.agriculture_level * 1.8)
                + (shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 2.4)
                + (local_storage_gap * 1.8)
                + (local_food_waste * 1.5)
                + (local_deficit_pressure * 0.9)
                + (region.infrastructure_level * 0.4)
                + (0.35 if region.settlement_level in {"town", "city"} else 0.0)
            ),
            "resource_focus": RESOURCE_GRAIN,
        })

    horse_suitability = region.resource_suitability.get(RESOURCE_HORSES, 0.0)
    horse_established = region.resource_established.get(RESOURCE_HORSES, 0.0)
    horse_source = _get_best_resource_source_region(
        faction_name,
        region.name,
        RESOURCE_HORSES,
        world,
    )
    if (
        horse_suitability >= 0.55
        and horse_established < max(0.16, horse_suitability - 0.1)
        and horse_source is not None
    ):
        source_path = _get_owned_path_length(faction_name, horse_source.name, region.name, world) or 0
        options.append({
            "project_type": "introduce_horses",
            "score": 4.5 + (horse_suitability * 3.5) + (shortages.get(CAPACITY_MOBILITY, 0.0) * 2.5) - (source_path * 0.45),
            "resource_focus": RESOURCE_HORSES,
            "source_region": horse_source.name,
        })
    if horse_established > 0 and region.pastoral_level < 1.6:
        options.append({
            "project_type": "improve_pastoralism",
            "score": 3.0 + (horse_established * 2.5) + (shortages.get(CAPACITY_MOBILITY, 0.0) * 1.8),
            "resource_focus": RESOURCE_HORSES,
        })

    extractive_potential = (
        region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0)
        + region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0)
    )
    if extractive_potential > 0 and region.extractive_level < 1.8:
        options.append({
            "project_type": "improve_extraction",
            "score": 3.6 + (extractive_potential * 3.0) + (shortages.get(CAPACITY_METAL, 0.0) * 2.0),
            "resource_focus": (
                RESOURCE_COPPER
                if region.resource_fixed_endowments.get(RESOURCE_COPPER, 0.0)
                >= region.resource_fixed_endowments.get(RESOURCE_STONE, 0.0)
                else RESOURCE_STONE
            ),
        })

    if region.infrastructure_level < 1.8:
        infrastructure_shortage_bonus = (
            shortages.get(CAPACITY_FOOD_SECURITY, 0.0) * 0.25
            + shortages.get(CAPACITY_METAL, 0.0) * 0.45
            + shortages.get(CAPACITY_MOBILITY, 0.0) * 0.2
        )
        options.append({
            "project_type": "improve_infrastructure",
            "score": (
                1.9
                + (get_region_taxable_value(region, world) * 0.48)
                + (corridor_pressure * 4.4)
                + (max(0.0, 0.78 - route_bottleneck) * 3.0)
                + infrastructure_shortage_bonus
            ),
            "resource_focus": "mixed",
        })

    return options


def get_invest_target_score_components(region_name: str, faction_name: str, world) -> dict[str, float | str]:
    region = world.regions[region_name]
    options = _get_investment_project_options(faction_name, region, world)
    if not options:
        return {
            "score": 0.0,
            "project_type": "none",
            "resource_focus": "",
            "resource_profile": "None",
        }
    best_option = max(
        options,
        key=lambda item: (float(item["score"]), str(item["project_type"])),
    )
    return {
        "score": round(float(best_option["score"]), 3),
        "project_type": str(best_option["project_type"]),
        "resource_focus": str(best_option["resource_focus"]),
        "source_region": str(best_option.get("source_region", "")),
        "resource_profile": format_resource_map(region.resource_output or region.resource_fixed_endowments, limit=3),
    }


def get_development_target_score_components(region_name: str, faction_name: str, world) -> dict[str, float | str]:
    """Compatibility-forward name for region project scoring."""
    return get_invest_target_score_components(region_name, faction_name, world)


def get_owned_region_count(faction_name, world):
    """Returns the number of regions currently owned by the faction."""

    return sum(
        1
        for region in world.regions.values()
        if region.owner == faction_name
    )


def get_treasury_concentration_multiplier(region_count):
    """Returns the share of treasury a faction can focus on a single front."""

    if region_count <= 1:
        return 1.0

    multiplier = 1.0 / (
        1.0 + (TREASURY_CONCENTRATION_REGION_FACTOR * (region_count - 1))
    )
    return max(MIN_TREASURY_CONCENTRATION, round(multiplier, 3))


def get_attack_target_score_components(region_name, faction_name, world):
    """Returns a simple attack score and combat stats for an enemy region."""

    region = world.regions[region_name]
    terrain_profile = get_terrain_profile(region)
    doctrine_alignment = get_faction_region_alignment(
        world.factions[faction_name],
        region.terrain_tags,
        region.climate,
    )
    region_core_status = get_region_core_status(region)
    core_defense_bonus = get_region_core_defense_bonus(region)
    defender_name = region.owner
    attacker_region_count = get_owned_region_count(faction_name, world)
    defender_region_count = get_owned_region_count(defender_name, world)
    attacker_treasury_multiplier = get_treasury_concentration_multiplier(attacker_region_count)
    defender_treasury_multiplier = get_treasury_concentration_multiplier(defender_region_count)
    attacker_faction = world.factions[faction_name]
    if attacker_faction.is_rebel and attacker_faction.proto_state:
        attacker_treasury_multiplier *= REBEL_PROTO_TREASURY_CONCENTRATION_FACTOR
    defender_faction_state = world.factions[defender_name]
    if defender_faction_state.is_rebel and defender_faction_state.proto_state:
        defender_treasury_multiplier *= REBEL_PROTO_TREASURY_CONCENTRATION_FACTOR
    attacker_deployable_treasury = int(
        round(attacker_faction.treasury * attacker_treasury_multiplier)
    )
    defender_deployable_treasury = int(
        round(defender_faction_state.treasury * defender_treasury_multiplier)
    )
    staging_regions = [
        world.regions[neighbor_name]
        for neighbor_name in region.neighbors
        if world.regions[neighbor_name].owner == faction_name
    ]
    staging_resources = max(
        (_get_region_strategic_value(staging_region, world) for staging_region in staging_regions),
        default=0.0,
    )
    staging_projection = max(
        (
            _get_region_strategic_value(staging_region, world)
            + get_region_attack_projection_modifier(
                staging_region,
                world=world,
                faction_name=faction_name,
            )
            for staging_region in staging_regions
        ),
        default=0,
    )
    attacker_strength = (
        attacker_deployable_treasury
        + staging_projection
        + doctrine_alignment["combat_modifier"]
    )
    rebel_reclaim_bonus = get_rebel_reclaim_bonus(
        faction_name,
        defender_name,
        world,
    )
    attacker_strength += rebel_reclaim_bonus
    ethnic_claim_bonus = 0
    claim_ethnicity = None
    if faction_has_ethnic_claim(world, region, faction_name):
        attacker_primary_ethnicity = world.factions[faction_name].primary_ethnicity
        defender_primary_ethnicity = defender_faction_state.primary_ethnicity
        if attacker_primary_ethnicity and attacker_primary_ethnicity != defender_primary_ethnicity:
            ethnic_claim_bonus = DIPLOMACY_ETHNIC_CLAIM_ATTACK_BONUS
            claim_ethnicity = attacker_primary_ethnicity
    attacker_strength += ethnic_claim_bonus
    regime_target_bonus = 0
    regime_target_score_bonus = 0
    regime_target_reason = None
    target_dominant_ethnicity = get_region_dominant_ethnicity(region)
    if (
        target_dominant_ethnicity is not None
        and target_dominant_ethnicity == attacker_faction.primary_ethnicity
        and factions_have_same_ethnicity_regime_tension(world, faction_name, defender_name)
    ):
        if (
            (attacker_faction.rebel_conflict_type == "civil_war" and attacker_faction.origin_faction == defender_name and not attacker_faction.proto_state)
            or (defender_faction_state.rebel_conflict_type == "civil_war" and defender_faction_state.origin_faction == faction_name and not defender_faction_state.proto_state)
        ):
            regime_target_bonus = REGIME_CLAIMANT_ATTACK_STRENGTH_BONUS
            regime_target_score_bonus = REGIME_CLAIMANT_ATTACK_SCORE_BONUS
            regime_target_reason = "civil_war_claim"
        elif attacker_faction.government_form != defender_faction_state.government_form:
            regime_target_bonus = REGIME_SPLIT_ATTACK_STRENGTH_BONUS
            regime_target_score_bonus = REGIME_SPLIT_ATTACK_SCORE_BONUS
            regime_target_reason = "regime_split"
        if region_core_status == "homeland":
            regime_target_bonus += 1
            regime_target_score_bonus += 3
        elif region_core_status == "core":
            regime_target_score_bonus += 2
    attacker_strength += regime_target_bonus
    diplomacy_attack_modifier, diplomacy_status = get_attack_diplomacy_modifier(
        world,
        faction_name,
        defender_name,
    )
    resource_need_bonus = _get_region_resource_interest(region, faction_name, world)
    target_value = _get_region_strategic_value(region, world)
    defender_strength = (
        defender_deployable_treasury
        + target_value
        + terrain_profile["defense_modifier"]
        + core_defense_bonus
    )
    success_chance = 0.5 + (
        (attacker_strength - defender_strength) * ATTACK_SUCCESS_STRENGTH_FACTOR
    )
    success_chance = max(ATTACK_SUCCESS_MIN, min(ATTACK_SUCCESS_MAX, success_chance))
    score = (
        int(success_chance * 100)
        + int(round(target_value * 3))
        + terrain_profile["economic_modifier"]
        + doctrine_alignment["economic_modifier"]
        + diplomacy_attack_modifier
        + regime_target_score_bonus
        + resource_need_bonus
    )

    return {
        "defender": defender_name,
        "target_resources": region.resources,
        "target_taxable_value": target_value,
        "attacker_region_count": attacker_region_count,
        "defender_region_count": defender_region_count,
        "attacker_treasury_multiplier": round(attacker_treasury_multiplier, 3),
        "defender_treasury_multiplier": round(defender_treasury_multiplier, 3),
        "attacker_deployable_treasury": attacker_deployable_treasury,
        "defender_deployable_treasury": defender_deployable_treasury,
        "staging_resources": staging_resources,
        "staging_projection": staging_projection,
        "attacker_strength": attacker_strength,
        "defender_strength": defender_strength,
        "terrain_tags": terrain_profile["terrain_tags"],
        "terrain_label": terrain_profile["terrain_label"],
        "defense_modifier": terrain_profile["defense_modifier"],
        "economic_modifier": terrain_profile["economic_modifier"],
        "doctrine_combat_modifier": doctrine_alignment["combat_modifier"],
        "doctrine_economic_modifier": doctrine_alignment["economic_modifier"],
        "rebel_reclaim_bonus": rebel_reclaim_bonus,
        "ethnic_claim_bonus": ethnic_claim_bonus,
        "claim_ethnicity": claim_ethnicity,
        "regime_target_bonus": regime_target_bonus,
        "regime_target_score_bonus": regime_target_score_bonus,
        "regime_target_reason": regime_target_reason,
        "diplomacy_status": diplomacy_status,
        "diplomacy_attack_modifier": diplomacy_attack_modifier,
        "resource_need_bonus": resource_need_bonus,
        "terrain_affinity": doctrine_alignment["average_affinity"],
        "core_status": region_core_status,
        "core_defense_bonus": core_defense_bonus,
        "success_chance": success_chance,
        "score": score,
    }


def get_expand_target_score_components(region_name, world, faction_name=None):
    """Returns the scoring breakdown for an expansion target."""

    region = world.regions[region_name]
    terrain_profile = get_terrain_profile(region)
    doctrine_alignment = None
    if faction_name is not None and faction_name in world.factions:
        doctrine_alignment = get_faction_region_alignment(
            world.factions[faction_name],
            region.terrain_tags,
            region.climate,
        )
    region_core_status = get_region_core_status(region)
    unclaimed_neighbors = 0

    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None:
            unclaimed_neighbors += 1

    resource_need_bonus = (
        _get_region_resource_interest(region, faction_name, world)
        if faction_name is not None
        else 0
    )
    target_value = _get_region_strategic_value(region, world)
    score = (
        (target_value * 2)
        + len(region.neighbors)
        + (unclaimed_neighbors * 2)
        + terrain_profile["expansion_modifier"]
        + terrain_profile["economic_modifier"]
        + (doctrine_alignment["expansion_modifier"] if doctrine_alignment is not None else 0)
        + (doctrine_alignment["economic_modifier"] if doctrine_alignment is not None else 0)
        + resource_need_bonus
    )

    return {
        "resources": region.resources,
        "taxable_value": target_value,
        "neighbors": len(region.neighbors),
        "unclaimed_neighbors": unclaimed_neighbors,
        "terrain_tags": terrain_profile["terrain_tags"],
        "terrain_label": terrain_profile["terrain_label"],
        "terrain_expansion_modifier": terrain_profile["expansion_modifier"],
        "terrain_economic_modifier": terrain_profile["economic_modifier"],
        "doctrine_expansion_modifier": (
            doctrine_alignment["expansion_modifier"]
            if doctrine_alignment is not None
            else 0
        ),
        "doctrine_economic_modifier": (
            doctrine_alignment["economic_modifier"]
            if doctrine_alignment is not None
            else 0
        ),
        "terrain_affinity": (
            doctrine_alignment["average_affinity"]
            if doctrine_alignment is not None
            else 0.0
        ),
        "core_status": region_core_status,
        "resource_need_bonus": resource_need_bonus,
        "score": score,
    }


def get_expand_event_tags(score_components):
    """Returns interpretation tags for an expansion event."""
    tags = ["expansion", "territory_gain"]

    if score_components["score"] >= 13:
        tags.append("high_value")
    if score_components["unclaimed_neighbors"] >= 2:
        tags.append("frontier")
    if (
        score_components["neighbors"] >= 6
        or (
            score_components["neighbors"] >= 5
            and score_components["unclaimed_neighbors"] >= 3
        )
    ):
        tags.append("pivotal")
    if score_components["unclaimed_neighbors"] == 0:
        tags.append("consolidating")
    if score_components.get("taxable_value", score_components["resources"]) <= 1 and score_components["unclaimed_neighbors"] == 0:
        tags.append("risky")

    return tags


def get_owned_region_counts(world):
    """Returns current owned region counts by faction."""
    counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1

    return counts


def get_faction_rankings(world):
    """Returns faction names sorted by a simple treasury/territory ranking."""
    owned_region_counts = get_owned_region_counts(world)

    return sorted(
        world.factions,
        key=lambda faction_name: (
            world.factions[faction_name].treasury,
            owned_region_counts[faction_name],
        ),
        reverse=True,
    )


def get_faction_rank(world, faction_name):
    """Returns one-based rank for a faction with shared ranks for ties."""
    owned_region_counts = get_owned_region_counts(world)
    faction_score = (
        world.factions[faction_name].treasury,
        owned_region_counts[faction_name],
    )

    better_factions = 0
    for other_faction_name in world.factions:
        other_score = (
            world.factions[other_faction_name].treasury,
            owned_region_counts[other_faction_name],
        )
        if other_score > faction_score:
            better_factions += 1

    return better_factions + 1


def get_faction_score(world, faction_name):
    """Returns the ranking tuple used for simple standings comparisons."""
    owned_region_counts = get_owned_region_counts(world)
    return (
        world.factions[faction_name].treasury,
        owned_region_counts[faction_name],
    )


def has_unique_lead(world, faction_name):
    """Returns whether the faction holds a unique lead by the current simple ranking."""
    faction_score = get_faction_score(world, faction_name)
    return sum(
        1
        for other_faction_name in world.factions
        if get_faction_score(world, other_faction_name) == faction_score
    ) == 1 and get_faction_rank(world, faction_name) == 1


def get_expand_strategic_role(score_components, expand_tags):
    """Returns a simple interpreted strategic role for an expansion."""
    if "pivotal" in expand_tags:
        return "junction"
    if "frontier" in expand_tags:
        return "frontier"
    if "consolidating" in expand_tags:
        return "consolidation"
    if "risky" in expand_tags:
        return "gamble"
    return "territorial_gain"


def get_importance_tier(score):
    """Returns a simple importance tier for an expansion score."""
    if score >= 18:
        return "major"
    if score >= 13:
        return "high"
    if score >= 9:
        return "moderate"
    return "minor"


def get_momentum_effect(rank_change, expand_tags, importance_tier, future_expansion_opened):
    """Returns a readable label for the expansion's momentum effect."""
    if rank_change is not None and rank_change > 0:
        return "surging"
    if (
        importance_tier == "major"
        and "frontier" in expand_tags
        and future_expansion_opened >= 4
    ):
        return "accelerating"
    if importance_tier == "high" and "consolidating" in expand_tags:
        return "stabilizing"
    if "risky" in expand_tags:
        return "fragile"
    return None


def get_summary_reason(score_components, strategic_role, importance_tier):
    """Returns a one-line reason for why the target mattered."""
    if strategic_role == "junction":
        return "it offered strong connectivity and multiple follow-up routes"
    if strategic_role == "frontier":
        return "it opened new directions for future expansion"
    if strategic_role == "consolidation":
        return "it secured nearby territory and tightened the faction's position"
    if importance_tier in {"major", "high"}:
        return "it combined strong income with strong positional value"
    return "it provided a straightforward territorial gain"


def _choose_expansion_population_source(faction_name, target_region_name, world):
    candidate_regions = [
        world.regions[neighbor_name]
        for neighbor_name in world.regions[target_region_name].neighbors
        if world.regions[neighbor_name].owner == faction_name
    ]
    if not candidate_regions:
        return None
    return max(
        candidate_regions,
        key=lambda region: (
            region.population,
            _get_region_strategic_value(region, world),
            region.name,
        ),
    )


def expand(faction_name, target_region_name, world):
    """Returns whether the Faction successfully expanded into the target Region."""

    if target_region_name not in world.regions:
        return False

    faction = world.factions[faction_name]

    if faction.treasury < EXPANSION_COST:
        return False

    if target_region_name not in get_expandable_regions(faction_name, world):
        return False

    treasury_before = faction.treasury
    rank_before = get_faction_rank(world, faction_name)
    owner_before = world.regions[target_region_name].owner
    score_components = get_expand_target_score_components(
        target_region_name,
        world,
        faction_name=faction_name,
    )
    expand_tags = get_expand_event_tags(score_components)
    strategic_role = get_expand_strategic_role(score_components, expand_tags)
    income_gain = score_components["taxable_value"]
    future_expansion_opened = score_components["unclaimed_neighbors"]
    importance_tier = get_importance_tier(score_components["score"])
    population_source = _choose_expansion_population_source(faction_name, target_region_name, world)
    source_region_name = population_source.name if population_source is not None else None
    source_population_before = population_source.population if population_source is not None else 0
    source_ethnicity_before = (
        get_region_dominant_ethnicity(population_source)
        if population_source is not None
        else None
    )
    target_population_before = world.regions[target_region_name].population
    faction.treasury -= EXPANSION_COST
    handle_region_owner_change(world.regions[target_region_name], faction_name)
    transferred_population = 0
    if population_source is not None and population_source.population > 0:
        transferred_population = max(
            POPULATION_EXPANSION_TRANSFER_MIN,
            int(round(population_source.population * POPULATION_EXPANSION_TRANSFER_RATIO)),
        )
        transferred_population = min(transferred_population, population_source.population)
        transferred_population = transfer_region_population(
            population_source,
            world.regions[target_region_name],
            transferred_population,
        )
    region_display_name = assign_region_founding_name(
        world,
        target_region_name,
        faction_name,
        is_homeland=False,
    )
    rank_after = get_faction_rank(world, faction_name)
    rank_change = rank_before - rank_after
    unique_lead_after = has_unique_lead(world, faction_name)
    is_turning_point = (
        (rank_change is not None and rank_change > 0)
        or (
            importance_tier == "major"
            and "pivotal" in expand_tags
            and future_expansion_opened >= 4
            and unique_lead_after
        )
    )
    momentum_effect = get_momentum_effect(
        rank_change,
        expand_tags,
        importance_tier,
        future_expansion_opened,
    )
    summary_reason = get_summary_reason(
        score_components,
        strategic_role,
        importance_tier,
    )
    narrative_tags = [tag for tag in expand_tags if tag not in {"expansion", "territory_gain"}]

    world.events.append(Event(
        turn=world.turn,
        type="expand",
        faction=faction_name,
        region=target_region_name,
        details={
            "cost": EXPANSION_COST,
            "resources": score_components["resources"],
            "taxable_value": score_components["taxable_value"],
            "neighbors": score_components["neighbors"],
            "unclaimed_neighbors": score_components["unclaimed_neighbors"],
            "score": score_components["score"],
            "terrain_tags": score_components["terrain_tags"],
            "terrain_label": score_components["terrain_label"],
            "terrain_expansion_modifier": score_components["terrain_expansion_modifier"],
            "terrain_economic_modifier": score_components["terrain_economic_modifier"],
            "doctrine_expansion_modifier": score_components["doctrine_expansion_modifier"],
            "doctrine_economic_modifier": score_components["doctrine_economic_modifier"],
            "terrain_affinity": score_components["terrain_affinity"],
            "core_status": score_components["core_status"],
            "region_display_name": region_display_name,
            "population_source_region": source_region_name,
            "population_source_before": source_population_before,
            "population_source_after": population_source.population if population_source is not None else 0,
            "population_source_ethnicity": source_ethnicity_before,
            "population_before": target_population_before,
            "population_after": world.regions[target_region_name].population,
            "population_transfer": transferred_population,
            "dominant_ethnicity_after": get_region_dominant_ethnicity(world.regions[target_region_name]),
            "region_reference": format_region_reference(
                world.regions[target_region_name],
                include_code=True,
            ),
        },
        context={
            "treasury_before": treasury_before,
            "treasury_after": faction.treasury,
            "owner_before": owner_before,
            "rank_before": rank_before,
        },
        impact={
            "owner_after": faction_name,
            "treasury_change": -EXPANSION_COST,
            "regions_gained": 1,
            "income_gain": income_gain,
            "population_change": world.regions[target_region_name].population - target_population_before,
            "rank_after": rank_after,
            "rank_change": rank_change,
            "future_expansion_opened": future_expansion_opened,
            "importance_tier": importance_tier,
            "is_turning_point": is_turning_point,
            "momentum_effect": momentum_effect,
            "strategic_role": strategic_role,
            "summary_reason": summary_reason,
            "narrative_tags": narrative_tags,
        },
        tags=expand_tags,
        significance=float(score_components["score"]),
    ))

    return True


def attack(faction_name, target_region_name, world):
    """Attempts a simple attack on an adjacent enemy-held region."""

    if target_region_name not in world.regions:
        return False

    if target_region_name not in get_attackable_regions(faction_name, world):
        return False

    attacker = world.factions[faction_name]
    target_region = world.regions[target_region_name]
    defender_name = target_region.owner

    if defender_name is None or defender_name == faction_name:
        return False

    if attacker.treasury < ATTACK_COST:
        return False

    score_components = get_attack_target_score_components(target_region_name, faction_name, world)
    treasury_before = attacker.treasury
    population_before = target_region.population
    attacker.treasury -= ATTACK_COST
    success_roll = random.random()
    succeeded = success_roll < score_components["success_chance"]
    treasury_change = -ATTACK_COST
    actual_failure_penalty = 0
    population_loss = 0
    defender_faction = world.factions.get(defender_name)
    is_reintegration_attempt = (
        defender_faction is not None
        and defender_faction.is_rebel
        and defender_faction.origin_faction == faction_name
    )
    is_proto_reintegration_attempt = (
        is_reintegration_attempt
        and defender_faction is not None
        and defender_faction.proto_state
    )

    if succeeded:
        population_loss = apply_region_population_loss(
            target_region,
            POPULATION_ATTACK_SUCCESS_LOSS,
        )
        apply_region_resource_damage(
            target_region,
            {
                RESOURCE_GRAIN: 0.06,
                RESOURCE_HORSES: 0.04,
                RESOURCE_WILD_FOOD: 0.03,
                RESOURCE_TIMBER: 0.04,
            },
        )
        handle_region_owner_change(target_region, faction_name)
        if is_proto_reintegration_attempt:
            set_region_unrest(
                target_region,
                min(target_region.unrest, REBEL_REABSORPTION_UNREST),
            )
        if not target_region.founding_name:
            assign_region_founding_name(
                world,
                target_region_name,
                faction_name,
                is_homeland=False,
            )
    else:
        population_loss = apply_region_population_loss(
            target_region,
            POPULATION_ATTACK_FAILURE_LOSS,
        )
        apply_region_resource_damage(
            target_region,
            {
                RESOURCE_GRAIN: 0.03,
                RESOURCE_HORSES: 0.02,
                RESOURCE_WILD_FOOD: 0.015,
                RESOURCE_TIMBER: 0.02,
            },
        )
        actual_failure_penalty = min(ATTACK_FAILURE_PENALTY, attacker.treasury)
        treasury_change -= actual_failure_penalty
        attacker.treasury -= actual_failure_penalty

    world.events.append(Event(
        turn=world.turn,
        type="attack",
        faction=faction_name,
        region=target_region_name,
        details={
            "defender": defender_name,
            "success": succeeded,
            "attack_cost": ATTACK_COST,
            "failure_penalty": actual_failure_penalty,
            "target_taxable_value": score_components["target_taxable_value"],
            "success_chance": round(score_components["success_chance"], 3),
            "attack_strength": score_components["attacker_strength"],
            "defense_strength": score_components["defender_strength"],
            "terrain_tags": score_components["terrain_tags"],
            "terrain_label": score_components["terrain_label"],
            "terrain_defense_modifier": score_components["defense_modifier"],
            "terrain_economic_modifier": score_components["economic_modifier"],
            "doctrine_combat_modifier": score_components["doctrine_combat_modifier"],
            "doctrine_economic_modifier": score_components["doctrine_economic_modifier"],
            "rebel_reclaim_bonus": score_components["rebel_reclaim_bonus"],
            "terrain_affinity": score_components["terrain_affinity"],
            "core_status": score_components["core_status"],
            "core_defense_bonus": score_components["core_defense_bonus"],
            "ethnic_claim_attack": score_components["ethnic_claim_bonus"] > 0,
            "claim_ethnicity": score_components.get("claim_ethnicity"),
            "regime_target_attack": score_components["regime_target_bonus"] > 0,
            "regime_target_reason": score_components.get("regime_target_reason"),
            "region_display_name": target_region.display_name,
            "region_reference": format_region_reference(target_region, include_code=True),
            "population_before": population_before,
            "population_after": target_region.population,
            "population_loss": population_loss,
        },
        context={
            "treasury_before": treasury_before,
            "owner_before": defender_name,
        },
        impact={
            "owner_after": faction_name if succeeded else defender_name,
            "treasury_after": attacker.treasury,
            "treasury_change": treasury_change,
            "success": succeeded,
            "population_change": target_region.population - population_before,
            "population_after": target_region.population,
            "reintegrated_rebel": succeeded and is_proto_reintegration_attempt,
            "reclaimed_successor": succeeded and is_reintegration_attempt and not is_proto_reintegration_attempt,
        },
        tags=[
            "combat",
            "attack",
            "success" if succeeded else "failure",
            *(["reintegration"] if is_reintegration_attempt else []),
        ],
        significance=score_components["success_chance"],
    ))

    return succeeded


def get_investable_regions(faction_name, world):
    """Returns a list of Regions the Faction owns and is capable of investing in."""

    investable_regions: set[str] = set()

    for region in world.regions.values():
        if (
            region.owner == faction_name
            and faction_knows_region(world, faction_name, region.name)
            and _get_investment_project_options(faction_name, region, world)
        ):
            investable_regions.add(region.name)

    return sorted(investable_regions)


def get_developable_regions(faction_name, world):
    """Compatibility-forward name for owned regions with development projects."""
    return get_investable_regions(faction_name, world)


def invest(faction_name, target_region_name, world):
    """Returns whether the Faction successfully invested in the target Region."""

    if target_region_name not in world.regions:
        return False

    if target_region_name not in get_investable_regions(faction_name, world):
        return False

    region = world.regions[target_region_name]
    taxable_before = get_region_taxable_value(region, world)
    resources_before = region.resources
    score_components = get_invest_target_score_components(
        target_region_name,
        faction_name,
        world,
    )
    project_type = score_components["project_type"]
    source_region_name = score_components.get("source_region") or None
    if project_type == "none":
        return False

    project_amount = 0.0
    if project_type == "introduce_grain":
        region.resource_established[RESOURCE_GRAIN] = min(
            region.resource_suitability.get(RESOURCE_GRAIN, 0.0),
            region.resource_established.get(RESOURCE_GRAIN, 0.0) + 0.24,
        )
        project_amount = 0.24
    elif project_type == "introduce_horses":
        region.resource_established[RESOURCE_HORSES] = min(
            region.resource_suitability.get(RESOURCE_HORSES, 0.0),
            region.resource_established.get(RESOURCE_HORSES, 0.0) + 0.16,
        )
        project_amount = 0.16
    elif project_type == "improve_agriculture":
        region.agriculture_level = round(min(1.8, region.agriculture_level + 0.28), 2)
        project_amount = 0.28
    elif project_type == "build_granary":
        region.granary_level = round(min(1.8, region.granary_level + 0.32), 2)
        project_amount = 0.32
    elif project_type == "improve_pastoralism":
        region.pastoral_level = round(min(1.8, region.pastoral_level + 0.24), 2)
        project_amount = 0.24
    elif project_type == "improve_extraction":
        region.extractive_level = round(min(1.8, region.extractive_level + 0.28), 2)
        project_amount = 0.28
    else:
        region.infrastructure_level = round(min(1.8, region.infrastructure_level + 0.22), 2)
        project_amount = 0.22

    region.last_resource_project_turn = world.turn
    if source_region_name is not None and source_region_name in world.regions:
        source_region = world.regions[source_region_name]
        source_region.last_resource_project_turn = world.turn
        apply_region_resource_damage(
            source_region,
            {
                score_components["resource_focus"]: 0.05
                if project_type == "introduce_grain"
                else 0.04
            },
        )

    update_faction_resource_economy(world)
    taxable_after = get_region_taxable_value(region, world)

    world.events.append(Event(
        turn=world.turn,
        type="invest",
        faction=faction_name,
        region=target_region_name,
        details={
            "invest_amount": project_amount,
            "project_type": project_type,
            "resource_focus": score_components["resource_focus"],
            "source_region": source_region_name,
            "region_display_name": region.display_name,
            "region_reference": format_region_reference(region, include_code=True),
        },
        context={
            "resources_before": resources_before,
            "taxable_before": taxable_before,
        },
        impact={
            "new_resources": region.resources,
            "resource_change": region.resources - resources_before,
            "new_taxable_value": taxable_after,
            "taxable_change": round(taxable_after - taxable_before, 2),
        },
        tags=["investment", "development", str(project_type)],
        significance=max(0.1, float(round(taxable_after - taxable_before, 2))),
    ))

    return True


def develop(faction_name, target_region_name, world):
    """Forward-facing alias for regional development projects."""
    return invest(faction_name, target_region_name, world)
