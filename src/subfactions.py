"""Subfaction system: semi-autonomous settler groups that fill harsh/remote niches."""
from __future__ import annotations

from copy import deepcopy

from src.actions import (
    expand,
    get_expand_target_score_components,
    get_expandable_regions,
)
from src.climate import get_climate_profile
from src.config import (
    EXPANSION_COST,
    SUBFACTION_AUTONOMY_GROWTH_BASE,
    SUBFACTION_AUTONOMY_OVEREXTENSION_BONUS,
    SUBFACTION_AUTONOMY_PROMOTION_THRESHOLD,
    SUBFACTION_AUTONOMY_SETTLEMENT_BONUS,
    SUBFACTION_AUTONOMY_TURNS_REQUIRED,
    SUBFACTION_AUTONOMY_UNREST_BONUS,
    SUBFACTION_HARSH_CLIMATE_BIAS,
    SUBFACTION_MAX_PER_FACTION,
    SUBFACTION_PROMOTION_TREASURY_SHARE,
    SUBFACTION_REMOTE_BIAS,
    SUBFACTION_SETTLEMENT_REQUIRED,
    SUBFACTION_SPAWN_COOLDOWN,
    SUBFACTION_SEED_TREASURY,
    SUBFACTION_SPAWN_MIN_REGIONS,
    SUBFACTION_SPAWN_OVEREXTENSION_THRESHOLD,
    SUBFACTION_TREASURY_SHARE,
)
from src.heartland import handle_region_owner_change
from src.models import Event, Faction, FactionIdentity, LanguageProfile, Subfaction, WorldState
from src.region_naming import assign_region_founding_name


def _owned_region_count(faction_name: str, world: WorldState) -> int:
    return sum(1 for r in world.regions.values() if r.owner == faction_name)


def _pick_peripheral_home_region(faction_name: str, world: WorldState) -> str | None:
    """Return the least-integrated non-homeland owned region (the most peripheral base)."""
    candidates = [
        r for r in world.regions.values()
        if r.owner == faction_name
        and r.homeland_faction_id != faction_name  # not the original homeland
    ]
    if not candidates:
        return None
    # Pick the region with the lowest integration_score (most peripheral)
    return min(candidates, key=lambda r: (float(r.integration_score or 0.0), r.name)).name


def _climate_harshness(climate: str) -> float:
    profile = get_climate_profile(climate)
    heat = max(0.0, float(profile["heat"]) - 0.86) * 0.3
    dry = max(0.0, 0.45 - float(profile["humidity"])) * 0.3
    return min(1.25, float(profile["cold"]) * 0.75 + float(profile["aridity"]) * 0.55 + heat + dry)


def _score_subfaction_target(
    region_name: str,
    parent_faction_name: str,
    world: WorldState,
) -> float:
    """Score an unclaimed region as a subfaction expansion target.

    Inverts the parent's expansion bias: prefers harsh climate, remote, maritime.
    """
    region = world.regions.get(region_name)
    if region is None or region.owner is not None:
        return -1.0

    try:
        parent_components = get_expand_target_score_components(
            region_name, world, faction_name=parent_faction_name
        )
    except Exception:
        parent_components = {}

    climate_harshness = _climate_harshness(region.climate)
    resources = int(region.resources or 1)
    maritime = bool(parent_components.get("maritime_operation", False))
    route_depth = int(parent_components.get("route_depth", 0) or 0)

    score = (
        resources * 0.35
        + climate_harshness * SUBFACTION_HARSH_CLIMATE_BIAS
        + max(0, route_depth - 2) * SUBFACTION_REMOTE_BIAS
        + (1.2 if maritime else 0.0)
    )
    return score


def _pick_subfaction_target(
    subfaction: Subfaction,
    world: WorldState,
) -> str | None:
    """Find the best unclaimed harsh/remote region for this subfaction to target."""
    parent = subfaction.parent_faction
    all_expandable = get_expandable_regions(parent, world)
    if not all_expandable:
        return None

    best_score = 0.0
    best_region = None
    for region_name in all_expandable:
        score = _score_subfaction_target(region_name, parent, world)
        if score > best_score:
            best_score = score
            best_region = region_name

    return best_region


def _build_subfaction_name(parent_faction: str, world: WorldState) -> str:
    """Generate a unique subfaction name."""
    base = f"{parent_faction} Settlers"
    if base not in {sf.name for faction in world.factions.values() for sf in faction.subfactions}:
        return base
    for i in range(2, 20):
        candidate = f"{parent_faction} Settlers {i}"
        if candidate not in {sf.name for faction in world.factions.values() for sf in faction.subfactions}:
            return candidate
    return f"{parent_faction} Settlers {world.turn}"


def _should_spawn_subfaction(faction_name: str, world: WorldState) -> bool:
    """Check if a faction meets the conditions to spawn a new subfaction."""
    faction = world.factions[faction_name]
    if faction.is_rebel or faction.proto_state:
        return False
    if len(faction.subfactions) >= SUBFACTION_MAX_PER_FACTION:
        return False
    if _owned_region_count(faction_name, world) < SUBFACTION_SPAWN_MIN_REGIONS:
        return False
    overextension = float(faction.administrative_overextension_penalty or 0.0)
    if overextension < SUBFACTION_SPAWN_OVEREXTENSION_THRESHOLD:
        return False
    # Needs at least one peripheral home region
    if _pick_peripheral_home_region(faction_name, world) is None:
        return False
    # Cooldown: don't spawn if faction recently spawned one
    last_spawn = int(getattr(faction, "_subfaction_last_spawn_turn", -999) or -999)
    if world.turn - last_spawn < SUBFACTION_SPAWN_COOLDOWN:
        return False
    # Update autonomy pressure
    faction.subfaction_autonomy_pressure = min(
        1.0,
        float(faction.subfaction_autonomy_pressure or 0.0)
        + overextension * 0.01
        + 0.02,
    )
    return faction.subfaction_autonomy_pressure >= 0.5


def spawn_subfaction(faction_name: str, world: WorldState) -> Subfaction | None:
    """Create and register a new subfaction for the given parent faction."""
    home_region_name = _pick_peripheral_home_region(faction_name, world)
    if home_region_name is None:
        return None

    faction = world.factions[faction_name]
    name = _build_subfaction_name(faction_name, world)
    sf = Subfaction(
        subfaction_id=f"{faction_name}:sf:{world.turn}",
        parent_faction=faction_name,
        name=name,
        social_form="settler_group",
        primary_ethnicity=faction.primary_ethnicity,
        autonomy=0.0,
        treasury_share=SUBFACTION_TREASURY_SHARE,
        home_region=home_region_name,
        agenda="settle_frontier",
        treasury=float(SUBFACTION_SEED_TREASURY),
    )
    faction.subfactions.append(sf)
    faction.subfaction_autonomy_pressure = 0.0
    faction._subfaction_last_spawn_turn = world.turn  # type: ignore[attr-defined]

    world.events.append(Event(
        turn=world.turn,
        type="subfaction_formed",
        faction=faction_name,
        region=home_region_name,
        details={
            "subfaction_id": sf.subfaction_id,
            "subfaction_name": name,
            "home_region": home_region_name,
            "overextension": round(float(faction.administrative_overextension_penalty or 0.0), 2),
        },
        tags=["subfaction", "formed"],
        significance=0.4,
    ))
    return sf


def _promote_subfaction(
    subfaction: Subfaction,
    parent_faction_name: str,
    world: WorldState,
) -> str | None:
    """Spawn an independent band faction from the subfaction and sever it from the parent."""
    parent = world.factions[parent_faction_name]

    # Determine which regions to transfer (those the subfaction settled)
    transfer_regions = [
        r_name for r_name in subfaction.settled_regions
        if r_name in world.regions and world.regions[r_name].owner == parent_faction_name
    ]
    if not transfer_regions and subfaction.home_region in world.regions:
        # Fall back to home region if settled_regions were lost
        transfer_regions = [subfaction.home_region]

    if not transfer_regions:
        return None

    # Build identity for new faction
    internal_id = f"{parent.internal_id}_sf_{world.turn}_{len(world.factions) + 1}"
    culture_name = (
        world.regions[transfer_regions[0]].display_name
        or world.regions[transfer_regions[0]].founding_name
        or transfer_regions[0]
    ).split("(")[0].strip() or subfaction.name.split()[0]
    language_profile = (
        deepcopy(parent.identity.language_profile)
        if parent.identity is not None
        else LanguageProfile(family_name=culture_name)
    )
    new_name = subfaction.name
    identity = FactionIdentity(
        internal_id=internal_id,
        culture_name=culture_name,
        polity_tier="band",
        government_form="leader",
        display_name=new_name,
        language_profile=language_profile,
        generation_method="subfaction_secession",
        inspirations=[parent_faction_name],
    )
    starting_treasury = max(1, int(round(parent.treasury * SUBFACTION_PROMOTION_TREASURY_SHARE)))
    new_faction = Faction(
        name=new_name,
        treasury=starting_treasury,
        identity=identity,
        starting_treasury=starting_treasury,
        primary_ethnicity=subfaction.primary_ethnicity,
        origin_faction=parent_faction_name,
        social_form="nomadic_band",
    )
    world.factions[new_name] = new_faction
    parent.treasury = max(0, parent.treasury - starting_treasury)

    # Transfer regions
    for r_name in transfer_regions:
        region = world.regions[r_name]
        handle_region_owner_change(region, new_name)
        assign_region_founding_name(world, r_name, new_name, is_homeland=(r_name == transfer_regions[0]))

    new_faction.known_regions = list(transfer_regions)
    new_faction.visible_regions = list(transfer_regions)
    new_faction.known_factions = [parent_faction_name, new_name]

    # Remove subfaction from parent list
    parent.subfactions = [sf for sf in parent.subfactions if sf.subfaction_id != subfaction.subfaction_id]

    world.events.append(Event(
        turn=world.turn,
        type="subfaction_secession",
        faction=parent_faction_name,
        details={
            "new_faction": new_name,
            "subfaction_id": subfaction.subfaction_id,
            "transferred_regions": transfer_regions,
            "starting_treasury": starting_treasury,
            "autonomy": round(subfaction.autonomy, 3),
            "settlement_count": subfaction.settlement_count,
        },
        impact={
            "regions_lost": len(transfer_regions),
            "new_faction": new_name,
        },
        tags=["subfaction", "secession", "band"],
        significance=0.7,
    ))
    return new_name


def _advance_subfaction(
    subfaction: Subfaction,
    parent_faction_name: str,
    world: WorldState,
) -> None:
    """Run one turn of subfaction logic: update autonomy, maybe expand, maybe promote."""
    parent = world.factions.get(parent_faction_name)
    if parent is None:
        return

    home_region = world.regions.get(subfaction.home_region)
    overextension = float(parent.administrative_overextension_penalty or 0.0)
    home_unrest = float(home_region.unrest or 0.0) if home_region else 0.0

    # Autonomy growth
    autonomy_delta = (
        SUBFACTION_AUTONOMY_GROWTH_BASE
        + overextension * SUBFACTION_AUTONOMY_OVEREXTENSION_BONUS
        + home_unrest * SUBFACTION_AUTONOMY_UNREST_BONUS
        + subfaction.settlement_count * SUBFACTION_AUTONOMY_SETTLEMENT_BONUS
    )
    subfaction.autonomy = min(1.0, subfaction.autonomy + autonomy_delta)

    # Track turns at high autonomy
    if subfaction.autonomy >= SUBFACTION_AUTONOMY_PROMOTION_THRESHOLD:
        subfaction.turns_autonomous += 1
    else:
        subfaction.turns_autonomous = max(0, subfaction.turns_autonomous - 1)

    # Promotion check
    if (
        subfaction.turns_autonomous >= SUBFACTION_AUTONOMY_TURNS_REQUIRED
        and subfaction.settlement_count >= SUBFACTION_SETTLEMENT_REQUIRED
    ):
        _promote_subfaction(subfaction, parent_faction_name, world)
        return

    # Expansion attempt (once per 3 turns based on cooldown)
    subfaction.cooldown_turns = max(0, subfaction.cooldown_turns - 1)
    if subfaction.cooldown_turns > 0:
        return

    # Subfaction pays from its own treasury seed, not the parent's pool
    if subfaction.treasury < EXPANSION_COST:
        return

    # Pick or validate target
    if subfaction.target_region is not None:
        region = world.regions.get(subfaction.target_region)
        if region is None or region.owner is not None:
            subfaction.target_region = None

    if subfaction.target_region is None:
        subfaction.target_region = _pick_subfaction_target(subfaction, world)

    if subfaction.target_region is None:
        return

    # Subfaction pays EXPANSION_COST from its own treasury; parent acts as conduit.
    # expand() deducts from parent.treasury, so we top up parent enough to pass its gate,
    # then restore parent to its original balance after expand() deducts.
    top_up = max(0, EXPANSION_COST - parent.treasury)
    parent.treasury += top_up
    subfaction.treasury -= EXPANSION_COST
    if expand(parent_faction_name, subfaction.target_region, world):
        # expand() deducted EXPANSION_COST — restore parent to its pre-expansion balance
        parent.treasury += EXPANSION_COST - top_up
        subfaction.settled_regions.append(subfaction.target_region)
        subfaction.settlement_count += 1
        subfaction.cooldown_turns = 3
        subfaction.target_region = None
        world.events.append(Event(
            turn=world.turn,
            type="subfaction_expansion",
            faction=parent_faction_name,
            region=subfaction.settled_regions[-1],
            details={
                "subfaction_id": subfaction.subfaction_id,
                "subfaction_name": subfaction.name,
                "settlement_count": subfaction.settlement_count,
                "autonomy": round(subfaction.autonomy, 3),
            },
            tags=["subfaction", "expansion"],
            significance=0.3,
        ))
    else:
        # expand() returned False before deducting — rollback top-up and subfaction payment
        parent.treasury -= top_up
        subfaction.treasury += EXPANSION_COST
        subfaction.target_region = None


def _check_spawn(world: WorldState) -> None:
    """Possibly spawn new subfactions for eligible factions."""
    for faction_name, faction in list(world.factions.items()):
        if _should_spawn_subfaction(faction_name, world):
            spawn_subfaction(faction_name, world)


def run_subfaction_phase(world: WorldState) -> None:
    """Advance all subfactions and potentially spawn new ones. Called each turn."""
    _check_spawn(world)

    for faction_name, faction in list(world.factions.items()):
        for subfaction in list(faction.subfactions):
            _advance_subfaction(subfaction, faction_name, world)
