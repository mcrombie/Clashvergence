from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import random

from src.player_actions import ActionOption, get_action_option, get_available_actions
from src.player_view import build_observer_snapshot, build_player_view_model
from src.session import (
    DEFAULT_RUNS_DIR,
    RunConfig,
    RunSession,
    TurnResult,
    advance_one_turn,
    create_session_from_world,
    load_session,
)
from src.world import create_world


@dataclass(frozen=True)
class InteractiveRunOptions:
    map_name: str = "multi_ring_symmetry"
    num_factions: int = 4
    seed: str | None = None
    mode: str = "game"
    player_faction: str | None = None
    run_dir: Path | None = None
    resume: bool = False
    map_generation_config: dict[str, Any] | None = None


class InteractiveSessionError(ValueError):
    """Raised when an interactive session cannot be created or resumed."""


class InteractiveActionError(ValueError):
    """Raised when a submitted player action is not currently legal."""

    def __init__(self, message: str, *, legal_action_ids: list[str] | None = None):
        super().__init__(message)
        self.legal_action_ids = legal_action_ids or []


def create_interactive_session(options: InteractiveRunOptions) -> RunSession:
    """Create or resume one human-playable turn-by-turn session."""
    if options.resume:
        return _resume_interactive_session(options)

    if options.seed is not None:
        random.seed(options.seed)

    world = create_world(
        map_name=options.map_name,
        num_factions=options.num_factions,
        map_generation_config=options.map_generation_config,
        seed=options.seed,
    )
    player_faction = resolve_player_faction(world, options.player_faction)
    config = RunConfig(
        map_name=options.map_name,
        num_factions=options.num_factions,
        seed=options.seed,
        mode=options.mode,
        player_faction=player_faction,
    )
    return create_session_from_world(
        config,
        world,
        run_dir=options.run_dir or build_default_interactive_run_dir(config),
    )


def resolve_player_faction(world: Any, requested_faction: str | None = None) -> str:
    """Resolve and validate the human-controlled faction for a world."""
    if requested_faction is None:
        try:
            return next(iter(world.factions))
        except StopIteration as error:
            raise InteractiveSessionError("World has no playable factions.") from error

    if requested_faction not in world.factions:
        valid_names = ", ".join(world.factions)
        raise InteractiveSessionError(
            f"Unknown player faction '{requested_faction}'. Valid factions: {valid_names}"
        )
    return requested_faction


def get_session_player_faction(session: RunSession) -> str:
    player_faction = session.config.player_faction
    if not player_faction:
        raise InteractiveSessionError("This session has no player faction.")
    if player_faction not in session.world.factions:
        raise InteractiveSessionError(
            f"Player faction '{player_faction}' is not in the session world."
        )
    return player_faction


def get_legal_player_actions(session: RunSession) -> list[ActionOption]:
    return get_available_actions(session.world, get_session_player_faction(session))


def get_legal_player_action_ids(session: RunSession) -> list[str]:
    return [option.action_id for option in get_legal_player_actions(session)]


def submit_player_action(
    session: RunSession,
    action_id: str,
    *,
    verbose: bool = False,
) -> TurnResult:
    """Validate and apply one human player action, then advance the world one turn."""
    player_faction = get_session_player_faction(session)
    normalized_action_id = str(action_id or "").strip()
    if not normalized_action_id:
        raise InteractiveActionError(
            "Missing action_id.",
            legal_action_ids=get_legal_player_action_ids(session),
        )

    action = get_action_option(session.world, player_faction, normalized_action_id)
    if action is None:
        raise InteractiveActionError(
            "Illegal or unavailable action.",
            legal_action_ids=get_legal_player_action_ids(session),
        )

    return advance_one_turn(session, player_action=action, verbose=verbose)


def build_interactive_state_payload(
    session: RunSession,
    *,
    turn_result: TurnResult | None = None,
) -> dict[str, Any]:
    """Build the shared JSON-ready state payload for interactive clients."""
    if session.config.player_faction:
        state = build_player_view_model(session.world, session.config.player_faction)
    else:
        state = build_observer_snapshot(session.world)

    payload = {
        "ok": True,
        "config": asdict(session.config),
        "run_dir": str(session.run_dir),
        "snapshot_count": session.snapshot_count,
        "state": state,
    }
    if turn_result is not None:
        payload["turn_result"] = {
            "turn": turn_result.turn,
            "event_count": turn_result.event_count,
            "player_action": turn_result.player_action,
        }
    return payload


def build_default_interactive_run_dir(
    config: RunConfig,
    *,
    runs_dir: Path = DEFAULT_RUNS_DIR,
) -> Path:
    seed_label = config.seed or "unseeded"
    player_label = config.player_faction or "player"
    safe_name = f"{config.mode}-{config.map_name}-{seed_label}-{player_label}".replace(" ", "_")
    return runs_dir / safe_name


def _resume_interactive_session(options: InteractiveRunOptions) -> RunSession:
    if options.run_dir is None:
        raise InteractiveSessionError("Resume requires a run directory.")

    session = load_session(options.run_dir)
    player_faction = get_session_player_faction(session)
    if options.player_faction and options.player_faction != player_faction:
        raise InteractiveSessionError(
            "Player faction does not match the resumed session "
            f"({player_faction})."
        )
    return session
