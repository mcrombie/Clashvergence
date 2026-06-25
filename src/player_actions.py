from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.actions import (
    attack,
    develop,
    expand,
    explore,
    get_attack_target_score_components,
    get_attackable_regions,
    get_developable_regions,
    get_development_target_score_components,
    get_expand_target_score_components,
    get_expandable_regions,
    get_explore_target_score_components,
    get_explorable_regions,
)
from src.config import ATTACK_COST, EXPANSION_COST
from src.diplomacy import (
    demand_tribute,
    get_diplomacy_candidates,
    get_diplomacy_target_score_components,
    propose_alliance,
    send_envoy,
)
from src.models import StandingOrder
from src.region_naming import format_region_reference


@dataclass(frozen=True)
class ActionOption:
    """A legal player-facing action for one faction on the current turn."""

    action_id: str
    action_type: str
    target_region: str | None
    label: str
    visible_reason: str
    known_cost: float = 0.0
    score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_available_actions(world, faction_name: str, *, include_skip: bool = True) -> list[ActionOption]:
    """Return legal actions visible to the faction under current world state."""
    if faction_name not in world.factions:
        return []

    faction = world.factions[faction_name]
    options: list[ActionOption] = []

    if faction.treasury >= EXPANSION_COST:
        for region_name in get_expandable_regions(faction_name, world):
            options.append(_build_expand_option(world, faction_name, region_name))

    if faction.treasury >= ATTACK_COST:
        for region_name in get_attackable_regions(faction_name, world):
            options.append(_build_attack_option(world, faction_name, region_name))

    for region_name in get_explorable_regions(faction_name, world):
        options.append(_build_explore_option(world, faction_name, region_name))

    for region_name in get_developable_regions(faction_name, world):
        options.append(_build_develop_option(world, faction_name, region_name))

    options.sort(
        key=lambda option: (
            option.action_type == "skip",
            option.action_type,
            -(option.score or 0.0),
            option.target_region or "",
        )
    )

    if include_skip:
        options.append(
            ActionOption(
                action_id="skip",
                action_type="skip",
                target_region=None,
                label="Skip action",
                visible_reason="Take no direct faction action this turn.",
            )
        )

    return options


def get_action_option(
    world,
    faction_name: str,
    action_id: str,
) -> ActionOption | None:
    for option in get_available_actions(world, faction_name):
        if option.action_id == action_id:
            return option

    return None


def apply_action_option(world, faction_name: str, action: ActionOption | str) -> bool:
    """Apply a legal action option. Returns whether a world-changing action succeeded."""
    action_option = (
        get_action_option(world, faction_name, action)
        if isinstance(action, str)
        else action
    )
    if action_option is None:
        raise ValueError(f"Unknown or illegal action for {faction_name}: {action}")

    if action_option.action_type == "skip":
        return False

    if action_option.target_region is None:
        raise ValueError(f"Action {action_option.action_id} requires a target region.")

    if action_option.action_type == "expand":
        return expand(faction_name, action_option.target_region, world)
    if action_option.action_type == "attack":
        return attack(faction_name, action_option.target_region, world)
    if action_option.action_type == "explore":
        return explore(faction_name, action_option.target_region, world)
    if action_option.action_type == "develop":
        return develop(faction_name, action_option.target_region, world)
    if action_option.action_type == "propose_alliance":
        return propose_alliance(faction_name, action_option.target_region, world)
    if action_option.action_type == "send_envoy":
        return send_envoy(faction_name, action_option.target_region, world)
    if action_option.action_type == "demand_tribute":
        return demand_tribute(faction_name, action_option.target_region, world)

    raise ValueError(f"Unsupported action type: {action_option.action_type}")


def _build_expand_option(world, faction_name: str, region_name: str) -> ActionOption:
    region = world.regions[region_name]
    components = get_expand_target_score_components(
        region_name,
        world,
        faction_name=faction_name,
    )
    taxable_value = components.get("taxable_value", components.get("resources", 0))
    return ActionOption(
        action_id=f"expand:{region_name}",
        action_type="expand",
        target_region=region_name,
        label=f"Expand into {format_region_reference(region, include_code=True)}",
        visible_reason=(
            f"Unclaimed neighboring region; known taxable value {taxable_value}."
        ),
        known_cost=float(EXPANSION_COST),
        score=float(components.get("score", 0.0)),
        details={
            "taxable_value": taxable_value,
            "neighbors": components.get("neighbors", 0),
            "unclaimed_neighbors": components.get("unclaimed_neighbors", 0),
            "terrain_label": components.get("terrain_label"),
            "core_status": components.get("core_status"),
        },
    )


def _build_attack_option(world, faction_name: str, region_name: str) -> ActionOption:
    region = world.regions[region_name]
    components = get_attack_target_score_components(region_name, faction_name, world)
    defender = components.get("defender") or region.owner
    success_chance = float(components.get("success_chance", 0.0) or 0.0)
    return ActionOption(
        action_id=f"attack:{region_name}",
        action_type="attack",
        target_region=region_name,
        label=f"Attack {format_region_reference(region, include_code=True)}",
        visible_reason=(
            f"Bordering rival-held region; estimated success chance {success_chance:.0%}."
        ),
        known_cost=float(ATTACK_COST),
        score=float(components.get("score", 0.0)),
        details={
            "defender": defender,
            "success_chance": round(success_chance, 3),
            "attack_strength": components.get("attacker_strength", 0),
            "defense_strength": components.get("defender_strength", 0),
            "diplomacy_status": components.get("diplomacy_status"),
            "terrain_label": components.get("terrain_label"),
            "core_status": components.get("core_status"),
        },
    )


def _build_explore_option(world, faction_name: str, region_name: str) -> ActionOption:
    region = world.regions[region_name]
    components = get_explore_target_score_components(region_name, faction_name, world)
    reveal_count = int(components.get("revealed_region_count", 0) or 0)
    unowned_count = int(components.get("revealed_unowned_count", 0) or 0)
    return ActionOption(
        action_id=f"explore:{region_name}",
        action_type="explore",
        target_region=region_name,
        label=f"Explore from {format_region_reference(region, include_code=True)}",
        visible_reason=(
            f"Scout beyond known territory; expected to reveal {reveal_count} region"
            f"{'' if reveal_count == 1 else 's'}, including {unowned_count} unclaimed."
        ),
        known_cost=0.0,
        score=float(components.get("score", 0.0)),
        details={
            "revealed_region_count": reveal_count,
            "revealed_unowned_count": unowned_count,
            "revealed_faction_count": components.get("revealed_faction_count", 0),
            "maritime_reveal_count": components.get("maritime_reveal_count", 0),
            "frontier_component_size": components.get("frontier_component_size", 0),
        },
    )


def get_active_projects(world, faction_name: str) -> list[dict]:
    """Return the faction's in-progress ActionProjects as dicts."""
    faction = world.factions.get(faction_name)
    if faction is None:
        return []
    from dataclasses import asdict as _asdict
    return [_asdict(project) for project in faction.active_projects.values()]


def get_standing_orders(world, faction_name: str) -> dict[str, dict]:
    """Return the faction's current standing orders keyed by track."""
    faction = world.factions.get(faction_name)
    if faction is None:
        return {}
    from dataclasses import asdict as _asdict
    return {track: _asdict(order) for track, order in faction.standing_orders.items()}


_VALID_MODES = {
    "admin": ("develop_priority", "develop_food", "develop_trade"),
    "military": ("expand_frontier", "consolidate", "patrol"),
}


def set_standing_order(
    world,
    faction_name: str,
    track: str,
    mode: str,
    target_region: str | None = None,
) -> bool:
    """Set (or clear) a standing order for the given track. Returns True on success."""
    faction = world.factions.get(faction_name)
    if faction is None:
        return False
    valid_modes = _VALID_MODES.get(track)
    if valid_modes is None or mode not in valid_modes:
        return False
    if target_region is not None and target_region not in world.regions:
        return False
    faction.standing_orders[track] = StandingOrder(
        track=track,
        mode=mode,
        target_region=target_region,
    )
    return True


def clear_standing_order(world, faction_name: str, track: str) -> bool:
    """Remove the standing order for a track."""
    faction = world.factions.get(faction_name)
    if faction is None:
        return False
    faction.standing_orders.pop(track, None)
    return True


def get_diplomacy_actions(world, faction_name: str) -> list[ActionOption]:
    """Return available diplomacy-track actions for player selection."""
    faction = world.factions.get(faction_name)
    if faction is None or faction.action_capacity < 3:
        return []
    if "diplomacy" in faction.active_projects:
        return []

    options: list[ActionOption] = []
    for target_name in get_diplomacy_candidates(faction_name, world):
        for action_type in ("propose_alliance", "demand_tribute", "send_envoy"):
            components = get_diplomacy_target_score_components(
                faction_name, target_name, action_type, world
            )
            score = float(components.get("score", -1.0))
            if score < 0.0:
                continue
            label_map = {
                "propose_alliance": f"Propose alliance to {target_name}",
                "demand_tribute": f"Demand tribute from {target_name}",
                "send_envoy": f"Send envoy to {target_name}",
            }
            reason_map = {
                "propose_alliance": f"2-turn project; boosts relationship score by {14:.0f} pts on completion.",
                "demand_tribute": f"Instant demand; requires power ratio {float(components.get('power_ratio', 0.0)):.1f}x.",
                "send_envoy": f"3-turn project; improves relations and border-region integration.",
            }
            options.append(ActionOption(
                action_id=f"{action_type}:{target_name}",
                action_type=action_type,
                target_region=target_name,
                label=label_map[action_type],
                visible_reason=reason_map[action_type],
                known_cost=0.0,
                score=round(score, 3),
                details={k: v for k, v in components.items() if k != "score"},
            ))

    options.sort(key=lambda o: (-o.score, o.action_type, o.target_region or ""))
    return options


def _build_develop_option(world, faction_name: str, region_name: str) -> ActionOption:
    region = world.regions[region_name]
    components = get_development_target_score_components(region_name, faction_name, world)
    project_type = str(components.get("project_type", "development"))
    resource_focus = components.get("resource_focus")
    reason = f"Best local project: {project_type.replace('_', ' ')}."
    if resource_focus:
        reason += f" Focus: {resource_focus}."
    return ActionOption(
        action_id=f"develop:{region_name}",
        action_type="develop",
        target_region=region_name,
        label=f"Develop {format_region_reference(region, include_code=True)}",
        visible_reason=reason,
        known_cost=0.0,
        score=float(components.get("score", 0.0)),
        details={
            "project_type": project_type,
            "resource_focus": resource_focus,
            "taxable_value": components.get("taxable_value", 0),
            "terrain_label": components.get("terrain_label"),
        },
    )
