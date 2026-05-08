from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from src.player_actions import ActionOption
from src.player_view import build_observer_snapshot, build_player_view_model
from src.simulation import run_turn
from src.world_serialization import deserialize_world, serialize_world
from src.world import create_world


DEFAULT_RUNS_DIR = Path("reports") / "runs"
WORLD_STATE_FILENAME = "world_state.json"


@dataclass(frozen=True)
class RunConfig:
    map_name: str = "multi_ring_symmetry"
    num_factions: int = 4
    seed: str | None = None
    mode: str = "simulation"
    player_faction: str | None = None


@dataclass
class TurnResult:
    turn: int
    snapshot: dict[str, Any]
    event_count: int
    player_action: dict[str, Any] | None = None


@dataclass
class RunSession:
    config: RunConfig
    world: Any
    run_dir: Path
    snapshot_count: int = 0


def create_session(
    config: RunConfig,
    *,
    run_dir: Path | None = None,
    map_generation_config: dict[str, Any] | None = None,
) -> RunSession:
    world = create_world(
        map_name=config.map_name,
        num_factions=config.num_factions,
        map_generation_config=map_generation_config,
        seed=config.seed,
    )
    return create_session_from_world(config, world, run_dir=run_dir)


def create_session_from_world(
    config: RunConfig,
    world: Any,
    *,
    run_dir: Path | None = None,
) -> RunSession:
    session = RunSession(
        config=config,
        world=world,
        run_dir=run_dir or _default_run_dir(config),
    )
    session.run_dir.mkdir(parents=True, exist_ok=True)
    _reset_session_outputs(session.run_dir)
    _write_json(session.run_dir / "config.json", asdict(config))
    write_snapshot(session)
    return session


def load_session(run_dir: Path) -> RunSession:
    config_path = run_dir / "config.json"
    world_path = run_dir / WORLD_STATE_FILENAME
    if not config_path.exists():
        raise FileNotFoundError(f"Missing session config: {config_path}")
    if not world_path.exists():
        raise FileNotFoundError(f"Missing world save: {world_path}")

    config_payload = _read_json(config_path)
    world_payload = _read_json(world_path)
    config = RunConfig(**{
        field_name: config_payload.get(field_name)
        for field_name in RunConfig.__dataclass_fields__
        if field_name in config_payload
    })
    return RunSession(
        config=config,
        world=deserialize_world(world_payload),
        run_dir=run_dir,
        snapshot_count=_resolve_snapshot_count(run_dir),
    )


def advance_one_turn(
    session: RunSession,
    *,
    player_action: ActionOption | None = None,
    verbose: bool = False,
) -> TurnResult:
    action_provider = None
    if player_action is not None and session.config.player_faction is not None:
        action_provider = lambda faction_name, _world: (
            player_action
            if faction_name == session.config.player_faction
            else None
        )

    event_count_before = len(session.world.events)
    run_turn(
        session.world,
        randomize_order=False,
        verbose=verbose,
        action_provider=action_provider,
    )
    snapshot = write_snapshot(session)
    return TurnResult(
        turn=session.world.turn,
        snapshot=snapshot,
        event_count=len(session.world.events) - event_count_before,
        player_action=player_action.to_dict() if player_action is not None else None,
    )


def write_snapshot(session: RunSession) -> dict[str, Any]:
    if session.config.player_faction:
        snapshot = build_player_view_model(session.world, session.config.player_faction)
    else:
        snapshot = build_observer_snapshot(session.world)

    session.snapshot_count += 1
    snapshot_record = {
        "snapshot_index": session.snapshot_count,
        "mode": session.config.mode,
        "snapshot": snapshot,
    }
    _append_jsonl(session.run_dir / "snapshots.jsonl", snapshot_record)
    _write_json(session.run_dir / "current_snapshot.json", snapshot_record)
    _append_new_events(session)
    save_world_state(session)
    return snapshot


def save_world_state(session: RunSession) -> None:
    _write_json(
        session.run_dir / WORLD_STATE_FILENAME,
        serialize_world(session.world),
    )


def _append_new_events(session: RunSession) -> None:
    event_path = session.run_dir / "events.jsonl"
    existing_count = _jsonl_line_count(event_path)
    for event in session.world.events[existing_count:]:
        _append_jsonl(event_path, event.to_dict())


def _default_run_dir(config: RunConfig) -> Path:
    seed_label = config.seed or "unseeded"
    player_label = config.player_faction or "observer"
    safe_name = f"{config.map_name}-{seed_label}-{player_label}".replace(" ", "_")
    return DEFAULT_RUNS_DIR / safe_name


def _reset_session_outputs(run_dir: Path) -> None:
    for filename in (
        "snapshots.jsonl",
        "events.jsonl",
        "current_snapshot.json",
        WORLD_STATE_FILENAME,
    ):
        path = run_dir / filename
        if path.exists():
            path.unlink()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        file.write("\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=True, sort_keys=True)
        file.write("\n")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _jsonl_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as file:
        return sum(1 for line in file if line.strip())


def _resolve_snapshot_count(run_dir: Path) -> int:
    current_snapshot_path = run_dir / "current_snapshot.json"
    if current_snapshot_path.exists():
        try:
            payload = _read_json(current_snapshot_path)
            return int(payload.get("snapshot_index", 0) or 0)
        except (ValueError, TypeError):
            pass
    return _jsonl_line_count(run_dir / "snapshots.jsonl")
