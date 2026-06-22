import http.client
import json
import shutil
import threading
from pathlib import Path

from src.game_server import create_game_server
from src.interactive_driver import (
    InteractiveActionError,
    InteractiveRunOptions,
    create_interactive_session,
    get_legal_player_action_ids,
    submit_player_action,
)
from src.player_actions import apply_action_option, get_available_actions
from src.player_view import build_player_view_model
from src.session import (
    RunConfig,
    advance_one_turn,
    create_session,
    create_session_from_world,
    load_session,
)
from src.world_serialization import serialize_world
from src.world import create_world


def test_player_actions_are_visible_and_legal():
    world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="game-actions")
    faction_name = next(iter(world.factions))

    options = get_available_actions(world, faction_name)
    action_ids = {option.action_id for option in options}

    assert "skip" in action_ids
    assert all(option.action_type in {"expand", "attack", "develop", "skip"} for option in options)

    develop_option = next(option for option in options if option.action_type == "develop")
    assert develop_option.target_region in world.regions
    assert apply_action_option(world, faction_name, develop_option) is True


def test_player_view_hides_unknown_regions_but_keeps_player_actions():
    world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="game-view")
    faction_name = next(iter(world.factions))
    view = build_player_view_model(world, faction_name)

    visible_region_names = {region["name"] for region in view["known_regions"]}
    unknown_region_names = set(world.regions) - visible_region_names

    assert view["player_faction"]["name"] == faction_name
    assert unknown_region_names
    assert all(region_name not in visible_region_names for region_name in unknown_region_names)
    assert view["available_actions"]
    assert "notes" in view

    map_region_names = {region["name"] for region in view["map"]["regions"]}
    map_edge_region_names = {
        edge_region_name
        for edge in view["map"]["edges"]
        for edge_region_name in (edge["source"], edge["target"])
    }
    assert map_region_names == visible_region_names
    assert map_edge_region_names <= visible_region_names


def test_session_advances_one_turn_and_writes_incremental_snapshots():
    scratch_path = Path("tests/.tmp_game_session")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    try:
        faction_name = next(
            iter(
                create_world(
                    map_name="thirteen_region_ring",
                    num_factions=4,
                    seed="game-session",
                ).factions
            )
        )
        config = RunConfig(
            map_name="thirteen_region_ring",
            num_factions=4,
            seed="game-session",
            mode="game",
            player_faction=faction_name,
        )
        session = create_session(config, run_dir=scratch_path)
        player_action = next(
            option
            for option in get_available_actions(session.world, faction_name)
            if option.action_type == "skip"
        )

        result = advance_one_turn(session, player_action=player_action)

        assert result.turn == 1
        assert (scratch_path / "snapshots.jsonl").exists()
        assert (scratch_path / "current_snapshot.json").exists()
        snapshot_lines = [
            json.loads(line)
            for line in (scratch_path / "snapshots.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert len(snapshot_lines) == 2
        assert snapshot_lines[-1]["snapshot"]["player_faction"]["name"] == faction_name
    finally:
        if scratch_path.exists():
            shutil.rmtree(scratch_path)


def test_session_save_load_and_continue():
    scratch_path = Path("tests/.tmp_game_resume")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    try:
        faction_name = next(
            iter(
                create_world(
                    map_name="thirteen_region_ring",
                    num_factions=4,
                    seed="game-resume",
                ).factions
            )
        )
        session = create_session(
            RunConfig(
                map_name="thirteen_region_ring",
                num_factions=4,
                seed="game-resume",
                mode="game",
                player_faction=faction_name,
            ),
            run_dir=scratch_path,
        )
        skip_action = next(
            option
            for option in get_available_actions(session.world, faction_name)
            if option.action_type == "skip"
        )
        advance_one_turn(session, player_action=skip_action)

        loaded_session = load_session(scratch_path)

        assert loaded_session.config == session.config
        assert loaded_session.world.turn == session.world.turn
        assert loaded_session.world.map_name == session.world.map_name
        assert loaded_session.world.factions[faction_name].display_name == session.world.factions[faction_name].display_name
        assert loaded_session.snapshot_count == 2
        assert (scratch_path / "world_state.json").exists()

        resumed_skip_action = next(
            option
            for option in get_available_actions(loaded_session.world, faction_name)
            if option.action_type == "skip"
        )
        result = advance_one_turn(loaded_session, player_action=resumed_skip_action)

        assert result.turn == 2
        snapshot_lines = [
            json.loads(line)
            for line in (scratch_path / "snapshots.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert len(snapshot_lines) == 3
        assert snapshot_lines[-1]["snapshot"]["turn"] == 2
    finally:
        if scratch_path.exists():
            shutil.rmtree(scratch_path)


def test_interactive_driver_creates_submits_and_resumes_session():
    scratch_path = Path("tests/.tmp_interactive_driver")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    try:
        session = create_interactive_session(
            InteractiveRunOptions(
                map_name="thirteen_region_ring",
                num_factions=4,
                seed="interactive-driver",
                mode="game",
                run_dir=scratch_path,
            )
        )

        assert session.config.player_faction in session.world.factions
        assert "skip" in get_legal_player_action_ids(session)

        result = submit_player_action(session, "skip")

        assert result.turn == 1
        assert result.player_action["action_id"] == "skip"
        assert (scratch_path / "world_state.json").exists()

        resumed = create_interactive_session(
            InteractiveRunOptions(run_dir=scratch_path, resume=True)
        )

        assert resumed.world.turn == 1
        assert resumed.snapshot_count == 2
        assert resumed.config == session.config
    finally:
        if scratch_path.exists():
            shutil.rmtree(scratch_path)


def test_interactive_driver_rejects_illegal_action_without_advancing():
    scratch_path = Path("tests/.tmp_interactive_illegal")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    try:
        session = create_interactive_session(
            InteractiveRunOptions(
                map_name="thirteen_region_ring",
                num_factions=4,
                seed="interactive-illegal",
                mode="game",
                run_dir=scratch_path,
            )
        )

        try:
            submit_player_action(session, "attack:hidden-region")
        except InteractiveActionError as error:
            assert "skip" in error.legal_action_ids
        else:
            raise AssertionError("Expected illegal action to raise InteractiveActionError.")

        assert session.world.turn == 0
        assert session.snapshot_count == 1
    finally:
        if scratch_path.exists():
            shutil.rmtree(scratch_path)


def test_game_server_state_and_action_endpoints():
    scratch_path = Path("tests/.tmp_game_server")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    server = None
    thread = None
    try:
        world = create_world(
            map_name="thirteen_region_ring",
            num_factions=4,
            seed="game-server",
        )
        faction_name = next(iter(world.factions))
        session = create_session_from_world(
            RunConfig(
                map_name="thirteen_region_ring",
                num_factions=4,
                seed="game-server",
                mode="game-server",
                player_faction=faction_name,
            ),
            world,
            run_dir=scratch_path,
        )
        server = create_game_server(session, host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address

        connection = http.client.HTTPConnection(host, port, timeout=120)
        connection.request("GET", "/api/state")
        response = connection.getresponse()
        state_payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert state_payload["ok"] is True
        assert state_payload["state"]["player_faction"]["name"] == faction_name
        assert state_payload["state"]["map"]["regions"]

        connection.request(
            "POST",
            "/api/action",
            body=json.dumps({"action_id": "attack:hidden-region"}),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        invalid_payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 400
        assert invalid_payload["ok"] is False
        assert "skip" in invalid_payload["legal_action_ids"]
        assert invalid_payload["state"]["turn"] == 0

        action_id = next(
            action["action_id"]
            for action in state_payload["state"]["available_actions"]
            if action["action_type"] == "skip"
        )
        connection.request(
            "POST",
            "/api/action",
            body=json.dumps({"action_id": action_id}),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        turn_payload = json.loads(response.read().decode("utf-8"))
        connection.close()

        assert response.status == 200
        assert turn_payload["ok"] is True
        assert turn_payload["turn_result"]["turn"] == 1
        assert turn_payload["turn_result"]["player_action"]["action_id"] == "skip"
        assert turn_payload["state"]["turn"] == 1
        assert (scratch_path / "current_snapshot.json").exists()
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=10)
        if scratch_path.exists():
            shutil.rmtree(scratch_path)


def test_game_server_observer_advance_endpoint_uses_ai_turn():
    scratch_path = Path("tests/.tmp_observer_server")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    server = None
    thread = None
    try:
        world = create_world(
            map_name="thirteen_region_ring",
            num_factions=4,
            seed="observer-server",
        )
        session = create_session_from_world(
            RunConfig(
                map_name="thirteen_region_ring",
                num_factions=4,
                seed="observer-server",
                mode="observer-server",
                player_faction=None,
            ),
            world,
            run_dir=scratch_path,
        )
        server = create_game_server(session, host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address

        connection = http.client.HTTPConnection(host, port, timeout=120)
        connection.request("GET", "/api/state")
        response = connection.getresponse()
        state_payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert state_payload["ok"] is True
        assert state_payload["config"]["player_faction"] is None
        assert "summary" in state_payload["state"]
        assert "available_actions" not in state_payload["state"]

        connection.request(
            "POST",
            "/api/advance",
            body=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        turn_payload = json.loads(response.read().decode("utf-8"))
        connection.close()

        assert response.status == 200
        assert turn_payload["ok"] is True
        assert turn_payload["turn_result"]["turn"] == 1
        assert turn_payload["turn_result"]["player_action"] is None
        assert turn_payload["state"]["turn"] == 1
        assert (scratch_path / "current_snapshot.json").exists()
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=10)
        if scratch_path.exists():
            shutil.rmtree(scratch_path)


def test_game_server_perspective_endpoint_switches_world_builder_view():
    scratch_path = Path("tests/.tmp_perspective_server")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    server = None
    thread = None
    try:
        world = create_world(
            map_name="thirteen_region_ring",
            num_factions=4,
            seed="perspective-server",
        )
        faction_name = next(iter(world.factions))
        session = create_session_from_world(
            RunConfig(
                map_name="thirteen_region_ring",
                num_factions=4,
                seed="perspective-server",
                mode="observer-server",
                player_faction=None,
            ),
            world,
            run_dir=scratch_path,
        )
        server = create_game_server(session, host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address

        connection = http.client.HTTPConnection(host, port, timeout=120)
        connection.request(
            "POST",
            "/api/perspective",
            body=json.dumps({"faction": faction_name}),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        switch_payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert switch_payload["ok"] is True
        assert switch_payload["config"]["player_faction"] == faction_name
        assert switch_payload["state"]["player_faction"]["name"] == faction_name

        connection.request("GET", "/api/world")
        response = connection.getresponse()
        player_world = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert player_world["ok"] is True
        assert player_world["view_mode"] == "player"
        assert player_world["player_faction"]["name"] == faction_name
        assert player_world["available_actions"]
        assert len(player_world["regions"]) < len(world.regions)

        connection.request(
            "POST",
            "/api/perspective",
            body=json.dumps({"faction": None}),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        observer_payload = json.loads(response.read().decode("utf-8"))
        connection.close()

        assert response.status == 200
        assert observer_payload["ok"] is True
        assert observer_payload["config"]["player_faction"] is None
        assert "summary" in observer_payload["state"]
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=10)
        if scratch_path.exists():
            shutil.rmtree(scratch_path)


def test_game_server_load_accepts_large_world_builder_save_payload():
    scratch_path = Path("tests/.tmp_game_server_large_load")
    if scratch_path.exists():
        shutil.rmtree(scratch_path)

    server = None
    thread = None
    try:
        world = create_world(
            map_name="thirteen_region_ring",
            num_factions=4,
            seed="game-server-large-load",
        )
        faction_name = next(iter(world.factions))
        session = create_session_from_world(
            RunConfig(
                map_name="thirteen_region_ring",
                num_factions=4,
                seed="game-server-large-load",
                mode="game-server",
                player_faction=faction_name,
            ),
            world,
            run_dir=scratch_path,
        )
        server = create_game_server(session, host="127.0.0.1", port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address

        payload = serialize_world(world)
        payload["metrics"] = [{"large_note": "x" * 1_100_000}]
        raw_payload = json.dumps(payload)
        assert len(raw_payload.encode("utf-8")) > 1_000_000

        connection = http.client.HTTPConnection(host, port, timeout=120)
        connection.request(
            "POST",
            "/api/load",
            body=raw_payload,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        load_payload = json.loads(response.read().decode("utf-8"))
        connection.close()

        assert response.status == 200
        assert load_payload["ok"] is True
        assert load_payload["turn"] == world.turn
        assert len(load_payload["regions"]) == len(world.regions)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=10)
        if scratch_path.exists():
            shutil.rmtree(scratch_path)
