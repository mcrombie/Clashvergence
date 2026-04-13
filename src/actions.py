from src.config import EXPANSION_COST, MAX_RESOURCES, INVEST_AMOUNT
from src.models import Event


def get_expandable_regions(faction_name, world):
    """Returns a list of Regions the given faction is capable of expanding into."""

    expandable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner == faction_name:
            for neighbor_name in region.neighbors:
                neighbor = world.regions[neighbor_name]
                if neighbor.owner is None:
                    expandable_regions.add(neighbor_name)

    return list(expandable_regions)


def get_expand_target_score_components(region_name, world):
    """Returns the scoring breakdown for an expansion target."""

    region = world.regions[region_name]
    unclaimed_neighbors = 0

    for neighbor_name in region.neighbors:
        neighbor = world.regions[neighbor_name]
        if neighbor.owner is None:
            unclaimed_neighbors += 1

    score = (region.resources * 2) + len(region.neighbors) + (unclaimed_neighbors * 2)

    return {
        "resources": region.resources,
        "neighbors": len(region.neighbors),
        "unclaimed_neighbors": unclaimed_neighbors,
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
    if score_components["resources"] <= 1 and score_components["unclaimed_neighbors"] == 0:
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
    score_components = get_expand_target_score_components(target_region_name, world)
    expand_tags = get_expand_event_tags(score_components)
    strategic_role = get_expand_strategic_role(score_components, expand_tags)
    income_gain = score_components["resources"]
    future_expansion_opened = score_components["unclaimed_neighbors"]
    importance_tier = get_importance_tier(score_components["score"])
    faction.treasury -= EXPANSION_COST
    world.regions[target_region_name].owner = faction_name
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
            "neighbors": score_components["neighbors"],
            "unclaimed_neighbors": score_components["unclaimed_neighbors"],
            "score": score_components["score"],
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


def get_investable_regions(faction_name, world):
    """Returns a list of Regions the Faction owns and is capable of investing in."""

    investable_regions: set[str] = set()

    for region in world.regions.values():
        if region.owner == faction_name and region.resources < MAX_RESOURCES:
            investable_regions.add(region.name)

    return list(investable_regions)


def invest(faction_name, target_region_name, world):
    """Returns whether the Faction successfully invested in the target Region."""

    if target_region_name not in world.regions:
        return False

    if target_region_name not in get_investable_regions(faction_name, world):
        return False

    region = world.regions[target_region_name]
    resources_before = region.resources

    if region.resources >= MAX_RESOURCES:
        return False

    region.resources += INVEST_AMOUNT

    if region.resources > MAX_RESOURCES:
        region.resources = MAX_RESOURCES

    world.events.append(Event(
        turn=world.turn,
        type="invest",
        faction=faction_name,
        region=target_region_name,
        details={
            "invest_amount": INVEST_AMOUNT,
        },
        context={
            "resources_before": resources_before,
        },
        impact={
            "new_resources": region.resources,
            "resource_change": region.resources - resources_before,
        },
        tags=["investment", "development"],
        significance=float(region.resources - resources_before),
    ))

    return True
