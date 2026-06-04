from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from typing import Any
from urllib.parse import urlsplit

from src.interactive_driver import (
    InteractiveActionError,
    InteractiveSessionError,
    build_interactive_state_payload,
    submit_player_action,
)
from src.player_view import build_observer_snapshot
from src.session import RunSession, advance_one_turn
from src.world_serialization import deserialize_world, serialize_world


MAX_JSON_BODY_BYTES = 256 * 1024 * 1024


def build_game_state_payload(
    session: RunSession,
    *,
    turn_result: Any | None = None,
) -> dict[str, Any]:
    """Build the JSON payload consumed by the local game UI."""
    return build_interactive_state_payload(session, turn_result=turn_result)


class GameServer(ThreadingHTTPServer):
    """Small stateful HTTP server for one local game session."""

    def __init__(self, server_address, session: RunSession):
        super().__init__(server_address, GameRequestHandler)
        self.session = session
        self.session_lock = threading.Lock()


def create_game_server(
    session: RunSession,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> GameServer:
    return GameServer((host, port), session)


def serve_game_session(
    session: RunSession,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    server = create_game_server(session, host=host, port=port)
    actual_host, actual_port = server.server_address
    print(f"Game server running at http://{actual_host}:{actual_port}/")
    print(f"Snapshots will be written to {session.run_dir}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping game server.")
    finally:
        server.server_close()


class GameRequestHandler(BaseHTTPRequestHandler):
    server: GameServer

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in {"/", "/index.html"}:
            self._send_html(GAME_CLIENT_HTML)
            return
        if path == "/api/health":
            self._send_json({"ok": True, "turn": self.server.session.world.turn})
            return
        if path == "/api/state":
            with self.server.session_lock:
                payload = build_game_state_payload(self.server.session)
            self._send_json(payload)
            return
        if path == "/api/world":
            with self.server.session_lock:
                payload = build_observer_snapshot(self.server.session.world)
                payload["ok"] = True
            self._send_json(payload)
            return
        if path == "/api/save":
            with self.server.session_lock:
                payload = serialize_world(self.server.session.world)
            self._send_json(payload)
            return
        self._send_error_json(HTTPStatus.NOT_FOUND, "Unknown endpoint.")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path

        try:
            body = self._read_json_body()
        except ValueError as error:
            self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
            return

        if path == "/api/load":
            try:
                new_world = deserialize_world(body)
            except (ValueError, KeyError, TypeError) as error:
                self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return
            with self.server.session_lock:
                self.server.session.world = new_world
                payload = build_observer_snapshot(self.server.session.world)
                payload["ok"] = True
            self._send_json(payload)
            return

        if path == "/api/advance":
            with self.server.session_lock:
                turn_result = advance_one_turn(self.server.session, verbose=False)
                payload = build_game_state_payload(self.server.session, turn_result=turn_result)
            self._send_json(payload)
            return

        if path != "/api/action":
            self._send_error_json(HTTPStatus.NOT_FOUND, "Unknown endpoint.")
            return

        action_id = str(body.get("action_id") or "").strip()

        with self.server.session_lock:
            session = self.server.session
            try:
                turn_result = submit_player_action(
                    session,
                    action_id,
                    verbose=False,
                )
            except InteractiveActionError as error:
                payload = build_game_state_payload(session)
                payload["ok"] = False
                payload["error"] = str(error)
                payload["legal_action_ids"] = error.legal_action_ids
                self._send_json(payload, status=HTTPStatus.BAD_REQUEST)
                return
            except InteractiveSessionError as error:
                self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return
            payload = build_game_state_payload(session, turn_result=turn_result)
        self._send_json(payload)

    def log_message(self, format, *args) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length.") from error

        if length <= 0:
            return {}
        if length > MAX_JSON_BODY_BYTES:
            raise ValueError("Request body is too large.")

        raw_body = self.rfile.read(length)
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Request body must be valid JSON.") from error
        if not isinstance(parsed, dict):
            raise ValueError("Request body must be a JSON object.")
        return parsed

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = content.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(
        self,
        payload: dict[str, Any],
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        raw_payload = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw_payload)))
        self.end_headers()
        self.wfile.write(raw_payload)

    def _send_error_json(self, status: HTTPStatus, message: str) -> None:
        self._send_json(
            {
                "ok": False,
                "error": message,
            },
            status=status,
        )


GAME_CLIENT_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clashvergence Game Mode</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f1ea;
      --surface: #fffdfa;
      --surface-2: #ece7dd;
      --ink: #182026;
      --muted: #65727a;
      --line: #d0c8ba;
      --accent: #176b66;
      --accent-2: #8d3f39;
      --owned: #176b66;
      --visible: #c9822b;
      --known: #87919a;
      --unknown: #c9c3b8;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }

    button, select {
      font: inherit;
    }

    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 390px;
      grid-template-rows: auto minmax(0, 1fr);
    }

    header {
      grid-column: 1 / -1;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }

    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 720;
    }

    .subhead {
      margin-top: 3px;
      color: var(--muted);
      font-size: 13px;
    }

    .status {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      font-size: 13px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 9px;
      border: 1px solid var(--line);
      background: var(--surface-2);
      border-radius: 6px;
      white-space: nowrap;
    }

    main {
      min-width: 0;
      padding: 18px;
      display: grid;
      grid-template-rows: minmax(360px, 1fr) auto;
      gap: 14px;
    }

    .map-panel {
      min-height: 360px;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      overflow: hidden;
      position: relative;
    }

    .map-toolbar {
      position: absolute;
      left: 12px;
      top: 12px;
      z-index: 2;
      display: flex;
      gap: 8px;
    }

    .icon-button {
      min-width: 36px;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: rgba(255, 253, 250, 0.92);
      color: var(--ink);
      cursor: pointer;
    }

    svg {
      width: 100%;
      height: 100%;
      display: block;
    }

    .edge {
      stroke: #8c8173;
      stroke-width: 2;
      opacity: 0.55;
    }

    .region-node {
      stroke: #242a2f;
      stroke-width: 2;
      cursor: pointer;
      transition: stroke-width 120ms ease, transform 120ms ease;
    }

    .region-node.selected {
      stroke-width: 4;
      stroke: var(--accent-2);
    }

    .region-label {
      pointer-events: none;
      font-size: 18px;
      font-weight: 760;
      fill: #101519;
      text-anchor: middle;
      dominant-baseline: central;
    }

    .map-note {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .bottom-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 10px;
      min-width: 0;
    }

    .metric-label {
      color: var(--muted);
      font-size: 12px;
    }

    .metric-value {
      margin-top: 4px;
      font-weight: 720;
      font-size: 17px;
      overflow-wrap: anywhere;
    }

    aside {
      min-width: 0;
      border-left: 1px solid var(--line);
      background: var(--surface);
      padding: 16px;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 14px;
      overflow: auto;
    }

    section {
      min-width: 0;
    }

    h2 {
      margin: 0 0 8px;
      font-size: 15px;
      font-weight: 720;
    }

    .action-list {
      display: grid;
      gap: 8px;
    }

    .action-button {
      width: 100%;
      text-align: left;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #f7f4ee;
      color: var(--ink);
      padding: 9px 10px;
      cursor: pointer;
    }

    .action-button.selected {
      border-color: var(--accent);
      box-shadow: inset 0 0 0 1px var(--accent);
      background: #edf7f5;
    }

    .action-label {
      display: block;
      font-weight: 700;
    }

    .action-reason {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 3px;
      line-height: 1.35;
    }

    .primary {
      width: 100%;
      min-height: 40px;
      border: 0;
      border-radius: 7px;
      background: var(--accent);
      color: white;
      cursor: pointer;
      font-weight: 720;
    }

    .primary:disabled {
      cursor: wait;
      opacity: 0.65;
    }

    .detail-panel, .events {
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr);
      gap: 7px 10px;
      font-size: 13px;
      line-height: 1.35;
    }

    .detail-key {
      color: var(--muted);
    }

    .detail-value {
      overflow-wrap: anywhere;
    }

    .event-list {
      display: grid;
      gap: 8px;
      padding-bottom: 20px;
    }

    .event-item {
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 8px;
      background: #faf8f2;
      font-size: 13px;
      line-height: 1.35;
    }

    .error {
      color: #8d3f39;
      font-size: 13px;
      min-height: 18px;
    }

    @media (max-width: 960px) {
      .shell {
        grid-template-columns: 1fr;
        grid-template-rows: auto minmax(420px, 58vh) auto;
      }

      main {
        padding: 12px;
      }

      aside {
        border-left: 0;
        border-top: 1px solid var(--line);
      }

      .bottom-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1 id="faction-title">Clashvergence</h1>
        <div class="subhead" id="turn-label">Loading session...</div>
      </div>
      <div class="status">
        <span class="pill" id="visibility-pill">Visibility</span>
        <span class="pill" id="run-dir-pill">Run</span>
      </div>
    </header>

    <main>
      <section class="map-panel" aria-label="Known map">
        <div class="map-toolbar">
          <button class="icon-button" id="fit-map" title="Fit known map" type="button">Fit</button>
        </div>
        <svg id="map" viewBox="0 0 900 900" role="img" aria-label="Known regions"></svg>
      </section>
      <section class="bottom-strip">
        <div class="metric">
          <div class="metric-label">Treasury</div>
          <div class="metric-value" id="treasury">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">Regions</div>
          <div class="metric-value" id="regions">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">Population</div>
          <div class="metric-value" id="population">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">Doctrine</div>
          <div class="metric-value" id="doctrine">-</div>
        </div>
      </section>
    </main>

    <aside>
      <section>
        <h2>Orders</h2>
        <div class="action-list" id="actions"></div>
        <button class="primary" id="submit-action" type="button">Submit Action</button>
        <div class="error" id="error"></div>
      </section>

      <section class="detail-panel">
        <h2>Region</h2>
        <div class="detail-grid" id="region-detail"></div>
      </section>

      <section class="events">
        <h2>Visible Events</h2>
        <div class="event-list" id="events"></div>
      </section>
    </aside>
  </div>

  <script>
    const state = {
      payload: null,
      selectedActionId: null,
      selectedRegion: null,
    };

    const colors = {
      controlled: "#176b66",
      visible: "#c9822b",
      known: "#87919a",
    };

    const svg = document.getElementById("map");
    const actionsEl = document.getElementById("actions");
    const errorEl = document.getElementById("error");

    function escapeText(value) {
      return String(value ?? "");
    }

    async function loadState() {
      const response = await fetch("/api/state");
      const payload = await response.json();
      if (!payload.ok) {
        throw new Error(payload.error || "Could not load state.");
      }
      state.payload = payload;
      const actions = payload.state.available_actions || [];
      state.selectedActionId = actions[0]?.action_id || null;
      state.selectedRegion = payload.state.known_regions?.[0]?.name || null;
      render();
    }

    async function submitAction() {
      if (!state.selectedActionId) {
        errorEl.textContent = "Choose an action first.";
        return;
      }
      const button = document.getElementById("submit-action");
      button.disabled = true;
      errorEl.textContent = "Resolving turn...";
      try {
        const response = await fetch("/api/action", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({action_id: state.selectedActionId}),
        });
        const payload = await response.json();
        if (!payload.ok) {
          throw new Error(payload.error || "Action failed.");
        }
        state.payload = payload;
        const actions = payload.state.available_actions || [];
        state.selectedActionId = actions[0]?.action_id || null;
        if (!payload.state.known_regions.some((region) => region.name === state.selectedRegion)) {
          state.selectedRegion = payload.state.known_regions?.[0]?.name || null;
        }
        errorEl.textContent = `Advanced to turn ${payload.turn_result?.turn ?? payload.state.turn}.`;
        render();
      } catch (error) {
        errorEl.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    }

    function render() {
      const payload = state.payload;
      if (!payload) {
        return;
      }
      const view = payload.state;
      const faction = view.player_faction;
      document.getElementById("faction-title").textContent = faction.display_name;
      document.getElementById("turn-label").textContent = view.turn_label;
      document.getElementById("visibility-pill").textContent =
        `${view.visibility.visible_region_count} visible / ${view.visibility.total_region_count} total`;
      document.getElementById("run-dir-pill").textContent = payload.run_dir;
      document.getElementById("treasury").textContent = faction.treasury;
      document.getElementById("regions").textContent = faction.owned_region_count;
      document.getElementById("population").textContent = faction.population.toLocaleString();
      document.getElementById("doctrine").textContent = faction.doctrine_label;
      renderMap(view);
      renderActions(view);
      renderRegionDetail(view);
      renderEvents(view);
    }

    function renderMap(view) {
      const regionsByName = Object.fromEntries(view.known_regions.map((region) => [region.name, region]));
      const mapRegions = view.map?.regions || [];
      const edges = view.map?.edges || [];
      svg.setAttribute("viewBox", `0 0 ${view.map?.width || 900} ${view.map?.height || 900}`);
      svg.replaceChildren();

      for (const edge of edges) {
        const source = mapRegions.find((region) => region.name === edge.source);
        const target = mapRegions.find((region) => region.name === edge.target);
        if (!source || !target) {
          continue;
        }
        svg.appendChild(svgElement("line", {
          x1: source.x,
          y1: source.y,
          x2: target.x,
          y2: target.y,
          class: "edge",
        }));
      }

      for (const point of mapRegions) {
        const region = regionsByName[point.name];
        if (!region) {
          continue;
        }
        const group = svgElement("g", {});
        const selected = state.selectedRegion === region.name;
        const circle = svgElement("circle", {
          cx: point.x,
          cy: point.y,
          r: region.visibility === "controlled" ? 31 : 27,
          fill: colors[region.visibility] || colors.known,
          class: selected ? "region-node selected" : "region-node",
        });
        circle.addEventListener("click", () => {
          state.selectedRegion = region.name;
          render();
        });
        group.appendChild(circle);
        group.appendChild(svgElement("text", {
          x: point.x,
          y: point.y,
          class: "region-label",
        }, region.name));
        svg.appendChild(group);
      }
    }

    function renderActions(view) {
      actionsEl.replaceChildren();
      for (const action of view.available_actions || []) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = action.action_id === state.selectedActionId
          ? "action-button selected"
          : "action-button";
        button.addEventListener("click", () => {
          state.selectedActionId = action.action_id;
          renderActions(view);
        });
        const label = document.createElement("span");
        label.className = "action-label";
        label.textContent = action.label + (action.known_cost ? ` (${action.known_cost} treasury)` : "");
        const reason = document.createElement("span");
        reason.className = "action-reason";
        reason.textContent = action.visible_reason;
        button.append(label, reason);
        actionsEl.appendChild(button);
      }
    }

    function renderRegionDetail(view) {
      const detail = document.getElementById("region-detail");
      const region = view.known_regions.find((item) => item.name === state.selectedRegion);
      if (!region) {
        detail.innerHTML = "<div class='detail-value'>No known region selected.</div>";
        return;
      }
      const rows = [
        ["Name", `${region.display_name} (${region.name})`],
        ["Visibility", region.visibility],
        ["Owner", region.owner || "unknown"],
        ["Terrain", (region.terrain_tags || []).join(", ") || "unknown"],
        ["Climate", region.climate || "unknown"],
        ["Resources", region.resources ?? region.resource_estimate ?? "unknown"],
        ["Population", region.population ?? region.population_estimate ?? "unknown"],
        ["Unrest", region.unrest ?? region.unrest_estimate ?? "unknown"],
        ["Neighbors", (region.neighbors || []).join(", ") || "none known"],
      ];
      detail.replaceChildren(...rows.flatMap(([key, value]) => {
        const keyEl = document.createElement("div");
        keyEl.className = "detail-key";
        keyEl.textContent = key;
        const valueEl = document.createElement("div");
        valueEl.className = "detail-value";
        valueEl.textContent = escapeText(value);
        return [keyEl, valueEl];
      }));
    }

    function renderEvents(view) {
      const events = document.getElementById("events");
      const items = view.recent_visible_events || [];
      if (!items.length) {
        events.innerHTML = "<div class='map-note'>No visible events yet.</div>";
        return;
      }
      events.replaceChildren(...items.map((event) => {
        const item = document.createElement("div");
        item.className = "event-item";
        item.textContent = `${event.type} | faction ${event.faction || "unknown"} | region ${event.region || "unknown"} | turn ${event.turn}`;
        return item;
      }));
    }

    function svgElement(name, attrs, text = null) {
      const element = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [key, value] of Object.entries(attrs)) {
        element.setAttribute(key, value);
      }
      if (text !== null) {
        element.textContent = text;
      }
      return element;
    }

    document.getElementById("submit-action").addEventListener("click", submitAction);
    document.getElementById("fit-map").addEventListener("click", render);
    loadState().catch((error) => {
      errorEl.textContent = error.message;
    });
  </script>
</body>
</html>
"""
