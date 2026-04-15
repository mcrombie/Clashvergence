from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from src.event_analysis import (
    build_initial_opening_state,
    get_final_standings,
)
from src.map_visualization import (
    build_map_layout,
    build_multi_ring_coastline_polygon,
    build_multi_ring_region_geometry,
    get_faction_color,
    get_map_edges,
    is_multi_ring_map,
    natural_sort_key,
)
from src.maps import MAPS
from src.metrics import get_turn_metrics
from src.narrative import (
    get_phase_ranges,
    summarize_final_standings,
    summarize_phases,
    summarize_strategic_interpretation,
    summarize_victor_history,
)


SIMULATION_VIEWER_OUTPUT = Path("reports/simulation_view.html")


def _serialize_event(event):
    event_data = event.to_dict()
    event_data["turn_display"] = event.turn + 1
    event_data["title"] = _get_event_title(event)
    event_data["summary"] = _get_event_summary(event)
    return event_data


def _get_event_title(event):
    if event.type == "expand":
        return f"{event.faction} expanded into {event.region}"
    if event.type == "attack":
        defender = event.get("defender", "Unknown")
        if event.get("success", False):
            return f"{event.faction} captured {event.region} from {defender}"
        return f"{event.faction} failed to take {event.region} from {defender}"
    if event.type == "invest":
        return f"{event.faction} invested in {event.region}"
    return f"{event.faction} acted"


def _get_event_summary(event):
    if event.type == "expand":
        return (
            f"Claimed a region worth R{event.get('resources', 0)} "
            f"with {event.get('neighbors', 0)} links."
        )
    if event.type == "attack":
        chance = event.get("success_chance", 0)
        if event.get("success", False):
            return f"Successful attack at {chance:.0%} displayed odds."
        return f"Attack failed at {chance:.0%} displayed odds."
    if event.type == "invest":
        return f"Resources increased to R{event.get('new_resources', 0)}."
    return "No summary available."


def build_simulation_snapshots(world):
    initial_state = build_initial_opening_state(world)
    region_state = {
        region_name: {
            "owner": initial_state[region_name]["owner"],
            "resources": initial_state[region_name]["resources"],
            "neighbors": list(region.neighbors),
        }
        for region_name, region in world.regions.items()
    }

    snapshots = [{
        "turn": 0,
        "events": [],
        "metrics": None,
        "regions": {
            region_name: {
                "owner": region["owner"],
                "resources": region["resources"],
            }
            for region_name, region in region_state.items()
        },
        "changed_regions": [],
        "contested_regions": [],
        "standings": _build_snapshot_standings_from_regions(region_state, world),
    }]

    for turn_number in range(1, world.turn + 1):
        turn_events = [event for event in world.events if event.turn == turn_number - 1]
        changed_regions = []
        contested_regions = []

        for event in turn_events:
            if event.region is None:
                continue

            if event.type == "expand":
                region_state[event.region]["owner"] = event.faction
                changed_regions.append(event.region)
            elif event.type == "attack":
                contested_regions.append(event.region)
                if event.get("success", False):
                    region_state[event.region]["owner"] = event.faction
                    changed_regions.append(event.region)
            elif event.type == "invest":
                region_state[event.region]["resources"] = event.get(
                    "new_resources",
                    region_state[event.region]["resources"],
                )
                changed_regions.append(event.region)

        metrics = get_turn_metrics(world, turn_number)
        snapshots.append({
            "turn": turn_number,
            "events": [_serialize_event(event) for event in turn_events],
            "metrics": metrics,
            "regions": {
                region_name: {
                    "owner": region["owner"],
                    "resources": region["resources"],
                }
                for region_name, region in region_state.items()
            },
            "changed_regions": sorted(set(changed_regions), key=natural_sort_key),
            "contested_regions": sorted(set(contested_regions), key=natural_sort_key),
            "standings": _build_snapshot_standings(metrics, region_state, world),
        })

    return snapshots


def _build_snapshot_standings(metrics, region_state, world):
    if metrics is None:
        return _build_snapshot_standings_from_regions(region_state, world)

    standings = []
    for faction_name, faction_metrics in metrics["factions"].items():
        standings.append({
            "faction": faction_name,
            "treasury": faction_metrics["treasury"],
            "owned_regions": faction_metrics["regions"],
        })
    standings.sort(
        key=lambda item: (item["treasury"], item["owned_regions"]),
        reverse=True,
    )
    return standings


def _build_snapshot_standings_from_regions(region_state, world):
    owned_counts = Counter(
        region["owner"]
        for region in region_state.values()
        if region["owner"] in world.factions
    )
    standings = []
    for faction_name, faction in world.factions.items():
        standings.append({
            "faction": faction_name,
            "treasury": faction.starting_treasury,
            "owned_regions": owned_counts.get(faction_name, 0),
        })
    standings.sort(
        key=lambda item: (item["treasury"], item["owned_regions"]),
        reverse=True,
    )
    return standings


def _atlas_region_sort_key(region_name):
    if region_name.startswith("O"):
        bucket = 0
    elif region_name.startswith("M"):
        bucket = 1
    elif region_name.startswith("I"):
        bucket = 2
    elif region_name == "C":
        bucket = 4
    else:
        bucket = 3
    return (bucket, natural_sort_key(region_name))


def build_simulation_view_model(world):
    positions = build_map_layout(MAPS[world.map_name]["regions"], width=900, height=900)
    edges = get_map_edges(MAPS[world.map_name]["regions"])
    atlas_geometry = None
    atlas_coastline = []
    if is_multi_ring_map(MAPS[world.map_name]["regions"]):
        atlas_geometry = build_multi_ring_region_geometry(
            MAPS[world.map_name]["regions"],
            map_name=world.map_name,
            width=900,
            height=900,
        )
        atlas_coastline = [
            [round(point[0], 1), round(point[1], 1)]
            for point in build_multi_ring_coastline_polygon(width=900, height=900)
        ]
    snapshots = build_simulation_snapshots(world)
    final_standings = get_final_standings(world)
    phase_ranges = get_phase_ranges(world.turn)
    _phase_analyses, phase_summary_lines = summarize_phases(world)
    phase_summaries = [
        {
            "name": phase_name,
            "start_turn": start_turn,
            "end_turn": end_turn,
            "summary": summary_line,
        }
        for (phase_name, start_turn, end_turn), summary_line in zip(phase_ranges, phase_summary_lines)
    ]

    factions = [
        {
            "name": faction_name,
            "internal_id": world.factions[faction_name].internal_id,
            "strategy": world.factions[faction_name].strategy,
            "color": get_faction_color(
                faction_name,
                internal_id=world.factions[faction_name].internal_id,
            ),
        }
        for faction_name in sorted(world.factions, key=natural_sort_key)
    ]

    atlas_region_names = (
        sorted(atlas_geometry, key=_atlas_region_sort_key)
        if atlas_geometry is not None
        else []
    )

    return {
        "map_name": world.map_name,
        "map_description": MAPS[world.map_name]["description"],
        "turns": world.turn,
        "regions": [
            {
                "name": region_name,
                "x": round(positions[region_name][0], 1),
                "y": round(positions[region_name][1], 1),
                "neighbors": sorted(region_data["neighbors"], key=natural_sort_key),
            }
            for region_name, region_data in sorted(
                MAPS[world.map_name]["regions"].items(),
                key=lambda item: natural_sort_key(item[0]),
            )
        ],
        "atlas_regions": [
            {
                "name": region_name,
                "polygon": [
                    [round(point[0], 1), round(point[1], 1)]
                    for point in atlas_geometry[region_name]["polygon"]
                ],
                "label_x": round(atlas_geometry[region_name]["label"][0], 1),
                "label_y": round(atlas_geometry[region_name]["label"][1], 1),
            }
            for region_name in atlas_region_names
        ] if atlas_geometry is not None else [],
        "atlas_coastline": atlas_coastline,
        "edges": edges,
        "factions": factions,
        "snapshots": snapshots,
        "phase_summaries": phase_summaries,
        "narrative_summary": {
            "strategic": summarize_strategic_interpretation(world),
            "victor": summarize_victor_history(world),
            "final": summarize_final_standings(world),
        },
        "final_standings": final_standings,
    }


def render_simulation_html(world):
    view_model = build_simulation_view_model(world)
    json_payload = json.dumps(view_model)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(world.map_name)} Simulation Viewer</title>
  <style>
    :root {{
      --bg: #080909;
      --panel: rgba(255, 251, 245, 0.88);
      --panel-strong: #fffdf8;
      --ink: #1f2933;
      --muted: #5d6d7e;
      --line: rgba(63, 74, 89, 0.14);
      --accent: #204e4a;
      --accent-soft: #d7ebe8;
      --shadow: 0 22px 60px rgba(31, 41, 51, 0.12);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top, rgba(48, 89, 122, 0.18), transparent 34%),
        linear-gradient(180deg, #0b0d10 0%, #080909 52%, #050606 100%);
    }}
    .page {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px;
    }}
    .panel {{
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.45);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 22px;
    }}
    .eyebrow {{
      display: inline-flex;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(32, 78, 74, 0.1);
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 12px;
      font-weight: 700;
    }}
    h1 {{
      margin: 14px 0 8px;
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 1.02;
    }}
    .lede {{
      margin: 0;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.6;
      max-width: 70ch;
    }}
    .hero-meta {{
      margin-top: 18px;
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(260px, 0.75fr);
      gap: 20px;
      align-items: start;
    }}
    .hero-subpanel {{
      background: rgba(255,255,255,0.52);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 18px;
      padding: 16px 18px;
    }}
    .overview-copy {{
      margin: 0;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.7;
      max-width: 68ch;
    }}
    .settings-block {{
      justify-self: stretch;
      text-align: left;
      min-width: 220px;
    }}
    .settings-list {{
      margin: 10px 0 0;
      display: grid;
      gap: 8px;
    }}
    .setting-row {{
      display: grid;
      gap: 2px;
    }}
    .setting-label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .setting-value {{
      font-size: 0.98rem;
      font-weight: 600;
      color: var(--ink);
    }}
    .layout {{
      display: grid;
      gap: 22px;
    }}
    .section-title {{
      margin: 0 0 14px;
      font-size: 1.15rem;
    }}
    .playback-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.62fr);
      gap: 18px;
      align-items: start;
    }}
    .map-stage {{
      min-width: 0;
    }}
    .side-rail {{
      display: grid;
      gap: 14px;
      min-width: 0;
    }}
    .side-section {{
      background: rgba(255,255,255,0.46);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 20px;
      padding: 16px;
    }}
    .side-title {{
      margin: 0 0 10px;
      font-size: 0.95rem;
    }}
    .map-shell {{
      position: relative;
      overflow: hidden;
      background:
        radial-gradient(circle at center, rgba(255,255,255,0.92), rgba(255,255,255,0.42)),
        radial-gradient(circle at 50% 30%, rgba(211, 232, 227, 0.48), transparent 58%),
        linear-gradient(180deg, rgba(194, 219, 214, 0.35), rgba(255,255,255,0.05));
      border-radius: 22px;
      border: 1px solid rgba(63, 74, 89, 0.12);
      padding: 12px;
    }}
    .controls {{
      display: grid;
      gap: 14px;
      margin-bottom: 14px;
    }}
    .transport {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .view-toggle {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      font: inherit;
      color: #fff;
      background: linear-gradient(135deg, #204e4a, #356f69);
      cursor: pointer;
      box-shadow: 0 10px 20px rgba(32, 78, 74, 0.2);
    }}
    button.secondary {{
      color: var(--ink);
      background: #efe6d4;
      box-shadow: none;
    }}
    button.secondary.active {{
      color: #fff;
      background: linear-gradient(135deg, #204e4a, #356f69);
      box-shadow: 0 10px 20px rgba(32, 78, 74, 0.16);
    }}
    .turn-readout {{
      font-size: 0.95rem;
      color: var(--muted);
    }}
    input[type="range"] {{
      width: 100%;
      accent-color: #204e4a;
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .edge {{
      stroke: rgba(83, 88, 98, 0.28);
      stroke-width: 2;
    }}
    .atlas-water {{
      fill: rgba(24, 73, 122, 0.34);
    }}
    .atlas-landmass {{
      fill: rgba(219, 212, 188, 0.45);
      stroke: rgba(91, 81, 59, 0.36);
      stroke-width: 5;
      filter: drop-shadow(0 18px 24px rgba(58, 67, 79, 0.12));
    }}
    .atlas-relief {{
      fill: none;
      stroke: rgba(105, 120, 93, 0.14);
      stroke-width: 2;
      stroke-linejoin: round;
      stroke-linecap: round;
      stroke-dasharray: 8 8;
    }}
    .atlas-territory {{
      stroke: rgba(60, 51, 36, 0.82);
      stroke-width: 2.2;
      stroke-linejoin: round;
      transition: fill 180ms ease, stroke-width 180ms ease, transform 180ms ease;
    }}
    .atlas-territory.changed {{
      stroke-width: 4;
    }}
    .atlas-territory.contested {{
      stroke: #8a2f1f;
    }}
    .region-node {{
      stroke: rgba(37, 43, 52, 0.65);
      stroke-width: 1.6;
      transition: transform 180ms ease, fill 180ms ease, stroke-width 180ms ease;
    }}
    .region-node.changed {{
      stroke-width: 4;
      transform: scale(1.08);
    }}
    .region-node.contested {{
      stroke: #8a2f1f;
    }}
    .region-label {{
      font-size: 14px;
      font-weight: 700;
      fill: #111827;
      pointer-events: none;
    }}
    .region-resource {{
      font-size: 11px;
      letter-spacing: 0.05em;
      font-weight: 700;
      fill: #274c5e;
      pointer-events: none;
    }}
    .map-layer.hidden {{
      display: none;
    }}
    .legend {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 0.92rem;
      color: var(--muted);
    }}
    .swatch {{
      width: 13px;
      height: 13px;
      border-radius: 999px;
      border: 1px solid rgba(17, 24, 39, 0.45);
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .summary-stack {{
      display: grid;
      gap: 12px;
    }}
    .settings-label {{
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .panel-hidden {{
      display: none;
    }}
    .summary-card {{
      background: rgba(255,255,255,0.56);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 18px;
      padding: 16px;
    }}
    .summary-card strong {{
      display: block;
      font-size: 0.92rem;
      margin-bottom: 8px;
    }}
    .summary-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .summary-copy {{
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.55;
    }}
    .summary-list {{
      margin: 10px 0 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    .summary-list li + li {{
      margin-top: 8px;
    }}
    .list {{
      display: grid;
      gap: 10px;
    }}
    .event-item, .standing-item {{
      display: grid;
      gap: 6px;
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255,255,255,0.56);
      border: 1px solid rgba(63, 74, 89, 0.08);
    }}
    .standings-bar {{
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .standing-item.bar {{
      padding: 12px 14px;
      gap: 4px;
      border-radius: 16px;
      min-width: 0;
    }}
    .standing-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }}
    .event-meta, .subtle {{
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .pill {{
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 12px;
      background: rgba(0,0,0,0.05);
    }}
    .mini-stats {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    @media (max-width: 1100px) {{
      .playback-layout {{
        grid-template-columns: 1fr;
      }}
      .standings-bar,
      .hero-meta {{
        grid-template-columns: 1fr;
      }}
      .settings-block {{
        justify-self: start;
        text-align: left;
      }}
    }}
    @media (max-width: 720px) {{
      .page {{
        padding: 16px;
      }}
      .hero-meta {{
        grid-template-columns: 1fr;
      }}
      .standings-bar {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        line-height: 1.02;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="layout">
      <div class="panel">
        <span class="eyebrow">Simulation Viewer</span>
        <h1>Clashvergence</h1>
        <div class="hero-meta">
          <div class="hero-subpanel">
            <p class="settings-label">Overview</p>
            <p class="overview-copy">This simulation is meant to replicate the way human nations clash and converge across time and space, with geography, expansion pressure, and strategic tradeoffs shaping how power rises, collides, and settles.</p>
          </div>
          <div class="hero-subpanel settings-block">
            <p class="settings-label">Simulation Settings</p>
            <div class="settings-list">
              <div class="setting-row">
                <div class="setting-label">Map</div>
                <div class="setting-value">{html.escape(world.map_name.replace("_", " ").title())}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Turns</div>
                <div class="setting-value">{world.turn}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Regions</div>
                <div class="setting-value">{len(world.regions)}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Factions</div>
                <div class="setting-value">{len(world.factions)}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Events</div>
                <div class="setting-value">{len(world.events)}</div>
              </div>
            </div>
          </div>
        </div>

        <h2 class="section-title">Map Playback</h2>
        <div class="controls">
          <div class="transport">
            <button type="button" id="play-toggle">Play</button>
            <button type="button" class="secondary" id="prev-turn">Prev</button>
            <button type="button" class="secondary" id="next-turn">Next</button>
            <div class="turn-readout" id="turn-readout">Turn 0 of 0</div>
          </div>
          <div class="view-toggle" id="view-toggle"></div>
          <input id="turn-slider" type="range" min="0" max="0" value="0">
        </div>
        <div class="playback-layout">
          <div class="map-stage">
            <div class="map-shell">
              <svg id="simulation-map" viewBox="0 0 900 900" role="img" aria-label="Simulation map">
                <g id="atlas-background-layer" class="map-layer"></g>
                <g id="atlas-layer" class="map-layer"></g>
                <g id="atlas-label-layer" class="map-layer"></g>
                <g id="graph-layer" class="map-layer">
                  <g id="edge-layer"></g>
                  <g id="region-layer"></g>
                  <g id="label-layer"></g>
                </g>
              </svg>
            </div>
            <div class="legend" id="legend"></div>
          </div>
          <aside class="side-rail">
            <section class="side-section">
              <h3 class="side-title">Current Turn</h3>
              <div class="summary-stack">
                <article class="summary-card" id="turn-context"></article>
                <div class="list" id="turn-events"></div>
              </div>
            </section>
          </aside>
        </div>
        <div class="standings-bar" id="standings"></div>
      </div>

      <div class="panel panel-hidden" id="run-summary-panel">
        <h2 class="section-title">Run Summary</h2>
        <div class="summary-stack" id="run-summary"></div>
      </div>
    </section>
  </div>

  <script>
    const data = {json_payload};
    const unclaimedColor = {json.dumps(get_faction_color(None))};
    const state = {{
      currentTurn: 0,
      playing: false,
      timer: null,
      mapView: data.atlas_regions.length ? "atlas" : "graph",
    }};

    const slider = document.getElementById("turn-slider");
    const readout = document.getElementById("turn-readout");
    const playToggle = document.getElementById("play-toggle");
    const prevButton = document.getElementById("prev-turn");
    const nextButton = document.getElementById("next-turn");
    const viewToggle = document.getElementById("view-toggle");
    const atlasBackgroundLayer = document.getElementById("atlas-background-layer");
    const atlasLayer = document.getElementById("atlas-layer");
    const atlasLabelLayer = document.getElementById("atlas-label-layer");
    const graphLayer = document.getElementById("graph-layer");
    const regionLayer = document.getElementById("region-layer");
    const edgeLayer = document.getElementById("edge-layer");
    const labelLayer = document.getElementById("label-layer");
    const legend = document.getElementById("legend");
    const standings = document.getElementById("standings");
    const turnContext = document.getElementById("turn-context");
    const turnEvents = document.getElementById("turn-events");
    const runSummaryPanel = document.getElementById("run-summary-panel");
    const runSummary = document.getElementById("run-summary");

    const colorByFaction = Object.fromEntries(data.factions.map((faction) => [faction.name, faction.color]));

    function svgElement(name, attrs) {{
      const element = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [key, value] of Object.entries(attrs)) {{
        element.setAttribute(key, value);
      }}
      return element;
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }}

    function polygonPointsText(points) {{
      return points.map((point) => `${{point[0]}},${{point[1]}}`).join(" ");
    }}

    function buildStaticMap() {{
      if (data.atlas_regions.length) {{
        atlasBackgroundLayer.appendChild(svgElement("rect", {{
          x: 0,
          y: 0,
          width: 900,
          height: 900,
          class: "atlas-water",
        }}));

        atlasBackgroundLayer.appendChild(svgElement("polygon", {{
          points: polygonPointsText(data.atlas_coastline),
          class: "atlas-landmass",
        }}));

        for (const scale of [0.88, 0.76]) {{
          const reliefPoints = data.atlas_coastline.map((point) => {{
            const dx = point[0] - 450;
            const dy = point[1] - 450;
            return [450 + (dx * scale), 450 + (dy * scale)];
          }});
          atlasBackgroundLayer.appendChild(svgElement("polygon", {{
            points: polygonPointsText(reliefPoints),
            class: "atlas-relief",
          }}));
        }}

        for (const region of data.atlas_regions) {{
          atlasLayer.appendChild(svgElement("polygon", {{
            points: polygonPointsText(region.polygon),
            class: "atlas-territory",
            id: `atlas-region-${{region.name}}`,
          }}));

          atlasLabelLayer.appendChild(svgElement("text", {{
            x: region.label_x,
            y: region.label_y - 8,
            "text-anchor": "middle",
            class: "region-label",
            id: `atlas-label-${{region.name}}`,
          }}));

          atlasLabelLayer.appendChild(svgElement("text", {{
            x: region.label_x,
            y: region.label_y + 13,
            "text-anchor": "middle",
            class: "region-resource",
            id: `atlas-resource-${{region.name}}`,
          }}));
        }}
      }}

      for (const [first, second] of data.edges) {{
        const firstRegion = data.regions.find((region) => region.name === first);
        const secondRegion = data.regions.find((region) => region.name === second);
        edgeLayer.appendChild(svgElement("line", {{
          x1: firstRegion.x,
          y1: firstRegion.y,
          x2: secondRegion.x,
          y2: secondRegion.y,
          class: "edge",
        }}));
      }}

      for (const region of data.regions) {{
        regionLayer.appendChild(svgElement("circle", {{
          cx: region.x,
          cy: region.y,
          r: 25,
          class: "region-node",
          id: `region-node-${{region.name}}`,
        }}));

        labelLayer.appendChild(svgElement("text", {{
          x: region.x,
          y: region.y - 8,
          "text-anchor": "middle",
          class: "region-label",
          id: `region-label-${{region.name}}`,
        }}));

        labelLayer.appendChild(svgElement("text", {{
          x: region.x,
          y: region.y + 13,
          "text-anchor": "middle",
          class: "region-resource",
          id: `region-resource-${{region.name}}`,
        }}));
      }}
    }}

    function renderViewToggle() {{
      if (!data.atlas_regions.length) {{
        graphLayer.classList.remove("hidden");
        atlasLayer.classList.add("hidden");
        atlasLabelLayer.classList.add("hidden");
        return;
      }}

      viewToggle.innerHTML = `
        <button type="button" class="secondary" data-view="atlas">Atlas View</button>
        <button type="button" class="secondary" data-view="graph">Graph View</button>
      `;

      for (const button of viewToggle.querySelectorAll("[data-view]")) {{
        button.classList.toggle("active", button.dataset.view === state.mapView);
        button.addEventListener("click", () => {{
          state.mapView = button.dataset.view;
          syncMapView();
        }});
      }}

      syncMapView();
    }}

    function syncMapView() {{
      const showAtlas = state.mapView === "atlas" && data.atlas_regions.length;
      atlasBackgroundLayer.classList.toggle("hidden", !showAtlas);
      atlasLayer.classList.toggle("hidden", !showAtlas);
      atlasLabelLayer.classList.toggle("hidden", !showAtlas);
      graphLayer.classList.toggle("hidden", showAtlas);

      for (const button of viewToggle.querySelectorAll("[data-view]")) {{
        button.classList.toggle("active", button.dataset.view === state.mapView);
      }}
    }}

    function renderLegend() {{
      const items = [
        ...data.factions.map((faction) => `<span class="legend-item"><span class="swatch" style="background:${{faction.color}}"></span>${{escapeHtml(faction.name)}} <span class="subtle">${{escapeHtml(faction.strategy)}}</span></span>`),
        `<span class="legend-item"><span class="swatch" style="background:${{unclaimedColor}}"></span>Unclaimed</span>`,
      ];
      legend.innerHTML = items.join("");
    }}

    function renderRunSummary() {{
      const strategic = data.narrative_summary.strategic || [];
      const victor = data.narrative_summary.victor || [];
      const finalLines = data.narrative_summary.final || [];

      runSummary.innerHTML = `
        <article class="summary-card">
          <strong>Phase Arc</strong>
          <ul class="summary-list">
            ${{data.phase_summaries.map((phase) => `<li><strong>${{escapeHtml(phase.name)}}:</strong> ${{escapeHtml(phase.summary)}}</li>`).join("")}}
          </ul>
        </article>
        <article class="summary-card">
          <strong>Strategic Read</strong>
          <p class="summary-copy">${{escapeHtml(strategic[0] || "No strategic interpretation available.")}}</p>
        </article>
        <article class="summary-card">
          <strong>Winner's Story</strong>
          <p class="summary-copy">${{escapeHtml(victor[0] || "No victor summary available.")}}</p>
        </article>
        <article class="summary-card">
          <strong>Final Order</strong>
          <ul class="summary-list">
            ${{finalLines.map((line) => `<li>${{escapeHtml(line)}}</li>`).join("")}}
          </ul>
        </article>
      `;
    }}

    function syncRunSummaryVisibility(turn) {{
      runSummaryPanel.classList.toggle("panel-hidden", turn < data.turns);
    }}

    function renderTurnContext(turn, snapshot) {{
      const eventCount = snapshot.events.length;
      const contestedCount = snapshot.contested_regions.length;
      const changedCount = snapshot.changed_regions.length;
      const leader = snapshot.standings[0];
      const leaderText = leader
        ? `${{leader.faction}} leads on $${{leader.treasury}} with ${{leader.owned_regions}} region${{leader.owned_regions === 1 ? "" : "s"}}.`
        : "No leader yet.";
      const contextText = turn === 0
        ? "Initial setup before any faction has acted."
        : leaderText;

      turnContext.innerHTML = `
        <strong>${{turn === 0 ? "Initial State" : `Turn ${{turn}} Snapshot`}}</strong>
        <p class="summary-copy">${{escapeHtml(contextText)}}</p>
        <div class="mini-stats">
          <span>${{eventCount}} event${{eventCount === 1 ? "" : "s"}} on this turn</span>
          <span>${{changedCount}} region${{changedCount === 1 ? "" : "s"}} changed</span>
          <span>${{contestedCount}} contested region${{contestedCount === 1 ? "" : "s"}}</span>
        </div>
      `;
    }}

    function renderStandings(snapshot) {{
      standings.innerHTML = snapshot.standings.map((entry, index) => `
        <article class="standing-item bar">
          <div class="standing-row">
            <strong>#${{index + 1}} ${{escapeHtml(entry.faction)}}</strong>
            <span class="pill" style="background:${{colorByFaction[entry.faction]}}22;">${{escapeHtml(data.factions.find((faction) => faction.name === entry.faction).strategy)}}</span>
          </div>
          <div class="subtle">Treasury $${{entry.treasury}} - Regions ${{entry.owned_regions}}</div>
        </article>
      `).join("");
    }}

    function renderTurnEvents(snapshot) {{
      if (!snapshot.events.length) {{
        turnEvents.innerHTML = `<article class="event-item"><strong>Initial State</strong><div class="event-meta">No turn events yet.</div></article>`;
        return;
      }}

      turnEvents.innerHTML = snapshot.events.map((event) => `
        <article class="event-item">
          <strong>${{escapeHtml(event.title)}}</strong>
          <div>${{escapeHtml(event.summary)}}</div>
          <div class="event-meta">Type: ${{escapeHtml(event.type)}}${{event.region ? ` - Region ${{escapeHtml(event.region)}}` : ""}}</div>
        </article>
      `).join("");
    }}

    function updateMap(snapshot) {{
      const changed = new Set(snapshot.changed_regions);
      const contested = new Set(snapshot.contested_regions);

      for (const region of data.regions) {{
        const regionSnapshot = snapshot.regions[region.name];
        const fill = colorByFaction[regionSnapshot.owner] || unclaimedColor;
        const node = document.getElementById(`region-node-${{region.name}}`);
        const label = document.getElementById(`region-label-${{region.name}}`);
        const resource = document.getElementById(`region-resource-${{region.name}}`);

        node.setAttribute("fill", fill);
        node.classList.toggle("changed", changed.has(region.name));
        node.classList.toggle("contested", contested.has(region.name));
        label.textContent = region.name;
        resource.textContent = `R${{regionSnapshot.resources}}`;
      }}

      for (const region of data.atlas_regions) {{
        const regionSnapshot = snapshot.regions[region.name];
        const fill = colorByFaction[regionSnapshot.owner] || unclaimedColor;
        const polygon = document.getElementById(`atlas-region-${{region.name}}`);
        const label = document.getElementById(`atlas-label-${{region.name}}`);
        const resource = document.getElementById(`atlas-resource-${{region.name}}`);

        if (!polygon || !label || !resource) {{
          continue;
        }}

        polygon.setAttribute("fill", fill);
        polygon.classList.toggle("changed", changed.has(region.name));
        polygon.classList.toggle("contested", contested.has(region.name));
        label.textContent = region.name;
        resource.textContent = `R${{regionSnapshot.resources}}`;
      }}
    }}

    function renderTurn(turn) {{
      state.currentTurn = turn;
      const snapshot = data.snapshots[turn];
      slider.value = String(turn);
      readout.textContent = `Turn ${{turn}} of ${{data.turns}}`;
      syncRunSummaryVisibility(turn);
      updateMap(snapshot);
      renderStandings(snapshot);
      renderTurnContext(turn, snapshot);
      renderTurnEvents(snapshot);
    }}

    function stopPlayback() {{
      state.playing = false;
      playToggle.textContent = "Play";
      if (state.timer) {{
        window.clearInterval(state.timer);
        state.timer = null;
      }}
    }}

    function startPlayback() {{
      stopPlayback();
      state.playing = true;
      playToggle.textContent = "Pause";
      state.timer = window.setInterval(() => {{
        if (state.currentTurn >= data.turns) {{
          stopPlayback();
          return;
        }}
        renderTurn(state.currentTurn + 1);
      }}, 1100);
    }}

    slider.max = String(data.turns);
    slider.addEventListener("input", () => {{
      stopPlayback();
      renderTurn(Number(slider.value));
    }});

    playToggle.addEventListener("click", () => {{
      if (state.playing) {{
        stopPlayback();
      }} else {{
        startPlayback();
      }}
    }});

    prevButton.addEventListener("click", () => {{
      stopPlayback();
      renderTurn(Math.max(0, state.currentTurn - 1));
    }});

    nextButton.addEventListener("click", () => {{
      stopPlayback();
      renderTurn(Math.min(data.turns, state.currentTurn + 1));
    }});

    buildStaticMap();
    renderLegend();
    renderViewToggle();
    renderRunSummary();
    renderTurn(0);
  </script>
</body>
</html>"""


def write_simulation_html(world, output_path=SIMULATION_VIEWER_OUTPUT):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_simulation_html(world), encoding="utf-8")
    return output_path
