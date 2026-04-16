from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from src.event_analysis import (
    build_initial_opening_state,
    get_final_standings,
)
from src.climate import format_climate_label
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
from src.region_naming import format_region_reference, get_region_display_name
from src.terrain import format_terrain_label


SIMULATION_VIEWER_OUTPUT = Path("reports/simulation_view.html")


def _serialize_event(event, world):
    event_data = event.to_dict()
    event_data["turn_display"] = event.turn + 1
    if event.region is not None and event.region in world.regions:
        region = world.regions[event.region]
        event_data["region_display_name"] = get_region_display_name(region)
        event_data["region_reference"] = format_region_reference(region, include_code=True)
        event_data["terrain_label"] = format_terrain_label(region.terrain_tags)
        event_data["terrain_tags"] = list(region.terrain_tags)
        event_data["climate"] = region.climate
        event_data["climate_label"] = format_climate_label(region.climate)
    else:
        event_data["region_display_name"] = event.region
        event_data["region_reference"] = event.region
        event_data["terrain_label"] = None
        event_data["terrain_tags"] = []
        event_data["climate"] = None
        event_data["climate_label"] = None
    event_data["title"] = _get_event_title(event, world)
    event_data["summary"] = _get_event_summary(event, world)
    return event_data


def _get_event_title(event, world):
    region_reference = event.region
    if event.region is not None and event.region in world.regions:
        region_reference = format_region_reference(world.regions[event.region], include_code=True)
    if event.type == "expand":
        return f"{event.faction} expanded into {region_reference}"
    if event.type == "attack":
        defender = event.get("defender", "Unknown")
        if event.get("success", False):
            return f"{event.faction} captured {region_reference} from {defender}"
        return f"{event.faction} failed to take {region_reference} from {defender}"
    if event.type == "invest":
        return f"{event.faction} invested in {region_reference}"
    if event.type == "unrest_disturbance":
        return f"Unrest disturbed {region_reference} under {event.faction}"
    if event.type == "unrest_crisis":
        return f"Unrest crisis hit {region_reference} under {event.faction}"
    if event.type == "unrest_secession":
        rebel_faction = event.get("rebel_faction")
        if rebel_faction:
            return f"{region_reference} broke away from {event.faction} as {rebel_faction}"
        return f"{region_reference} broke away from {event.faction}"
    if event.type == "rebel_independence":
        origin_faction = event.get("origin_faction")
        if origin_faction:
            return f"{event.faction} declared full independence from {origin_faction}"
        return f"{event.faction} consolidated into an independent successor state"
    return f"{event.faction} acted"


def _get_event_summary(event, world):
    terrain_text = ""
    if event.region is not None and event.region in world.regions:
        terrain_text = f" Terrain: {format_terrain_label(world.regions[event.region].terrain_tags)}."

    if event.type == "expand":
        return (
            f"Claimed a region worth R{event.get('resources', 0)} "
            f"with {event.get('neighbors', 0)} links.{terrain_text}"
        )
    if event.type == "attack":
        chance = event.get("success_chance", 0)
        if event.get("success", False):
            return f"Successful attack at {chance:.0%} displayed odds.{terrain_text}"
        return f"Attack failed at {chance:.0%} displayed odds.{terrain_text}"
    if event.type == "invest":
        return f"Resources increased to R{event.get('new_resources', 0)}.{terrain_text}"
    if event.type == "unrest_disturbance":
        return (
            f"Moderate unrest disrupted local order and forced a treasury hit of "
            f"{abs(event.get('treasury_change', 0))}.{terrain_text}"
        )
    if event.type == "unrest_crisis":
        return (
            f"Critical unrest triggered a deeper disruption and treasury hit of "
            f"{abs(event.get('treasury_change', 0))}.{terrain_text}"
        )
    if event.type == "unrest_secession":
        rebel_faction = event.get("rebel_faction")
        return (
            (
                f"Sustained crisis raised {rebel_faction} out of {event.faction}'s collapsing rule."
                if rebel_faction
                else f"Sustained crisis forced the region out of {event.faction}'s control."
            )
            + terrain_text
        )
    if event.type == "rebel_independence":
        government_type = event.get("government_type", "State")
        return (
            f"After surviving its fragile rebellion, the polity hardened into a full {government_type.lower()}."
            + terrain_text
        )
    return "No summary available."


def build_simulation_snapshots(world):
    initial_state = build_initial_opening_state(world)
    initial_region_history = world.region_history[0] if world.region_history else {}
    region_state = {
        region_name: {
            "owner": initial_state[region_name]["owner"],
            "resources": initial_state[region_name]["resources"],
            "neighbors": list(region.neighbors),
            "display_name": region.display_name if initial_state[region_name]["owner"] is not None else region.name,
            "founding_name": region.founding_name if initial_state[region_name]["owner"] is not None else "",
            "original_namer_faction_id": (
                region.original_namer_faction_id
                if initial_state[region_name]["owner"] is not None
                else None
            ),
            "terrain_tags": list(region.terrain_tags),
            "terrain_label": format_terrain_label(region.terrain_tags),
            "climate": region.climate,
            "climate_label": format_climate_label(region.climate),
            "homeland_faction_id": initial_region_history.get(region_name, {}).get("homeland_faction_id"),
            "integrated_owner": initial_region_history.get(region_name, {}).get("integrated_owner"),
            "integration_score": initial_region_history.get(region_name, {}).get("integration_score", 0.0),
            "core_status": initial_region_history.get(region_name, {}).get("core_status", "frontier"),
            "unrest": initial_region_history.get(region_name, {}).get("unrest", 0.0),
            "unrest_event_level": initial_region_history.get(region_name, {}).get("unrest_event_level", "none"),
            "unrest_event_turns_remaining": initial_region_history.get(region_name, {}).get("unrest_event_turns_remaining", 0),
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
                "display_name": region["display_name"],
                "founding_name": region["founding_name"],
                "original_namer_faction_id": region["original_namer_faction_id"],
                "terrain_tags": region["terrain_tags"],
                "terrain_label": region["terrain_label"],
                "climate": region["climate"],
                "climate_label": region["climate_label"],
                "homeland_faction_id": region["homeland_faction_id"],
                "integrated_owner": region["integrated_owner"],
                "integration_score": region["integration_score"],
                "core_status": region["core_status"],
                "unrest": region["unrest"],
                "unrest_event_level": region["unrest_event_level"],
                "unrest_event_turns_remaining": region["unrest_event_turns_remaining"],
            }
            for region_name, region in region_state.items()
        },
        "changed_regions": [],
        "contested_regions": [],
        "standings": _build_snapshot_standings_from_regions(region_state, world),
    }]

    for turn_number in range(1, world.turn + 1):
        turn_events = [event for event in world.events if event.turn == turn_number - 1]
        history_snapshot = world.region_history[turn_number] if len(world.region_history) > turn_number else {}
        changed_regions = []
        contested_regions = []

        for event in turn_events:
            if event.region is None:
                continue

            if event.type == "expand":
                region_state[event.region]["owner"] = event.faction
                region_state[event.region]["display_name"] = event.get(
                    "region_display_name",
                    region_state[event.region]["display_name"],
                )
                region_state[event.region]["founding_name"] = event.get(
                    "region_display_name",
                    region_state[event.region]["founding_name"],
                )
                region_state[event.region]["original_namer_faction_id"] = (
                    world.regions[event.region].original_namer_faction_id
                )
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

        for region_name, history_region in history_snapshot.items():
            region_state[region_name]["owner"] = history_region["owner"]
            region_state[region_name]["resources"] = history_region["resources"]
            region_state[region_name]["display_name"] = history_region["display_name"] or region_state[region_name]["display_name"]
            region_state[region_name]["founding_name"] = history_region["founding_name"]
            region_state[region_name]["original_namer_faction_id"] = history_region["original_namer_faction_id"]
            region_state[region_name]["homeland_faction_id"] = history_region["homeland_faction_id"]
            region_state[region_name]["integrated_owner"] = history_region["integrated_owner"]
            region_state[region_name]["integration_score"] = history_region["integration_score"]
            region_state[region_name]["core_status"] = history_region["core_status"]
            region_state[region_name]["unrest"] = history_region.get("unrest", 0.0)
            region_state[region_name]["unrest_event_level"] = history_region.get("unrest_event_level", "none")
            region_state[region_name]["unrest_event_turns_remaining"] = history_region.get("unrest_event_turns_remaining", 0)
            region_state[region_name]["climate"] = history_region.get("climate", region_state[region_name]["climate"])
            region_state[region_name]["climate_label"] = format_climate_label(region_state[region_name]["climate"])

        metrics = get_turn_metrics(world, turn_number)
        snapshots.append({
            "turn": turn_number,
            "events": [_serialize_event(event, world) for event in turn_events],
            "metrics": metrics,
            "regions": {
                region_name: {
                    "owner": region["owner"],
                    "resources": region["resources"],
                    "display_name": region["display_name"],
                    "founding_name": region["founding_name"],
                    "original_namer_faction_id": region["original_namer_faction_id"],
                    "terrain_tags": region["terrain_tags"],
                    "terrain_label": region["terrain_label"],
                    "climate": region["climate"],
                    "climate_label": region["climate_label"],
                    "homeland_faction_id": region["homeland_faction_id"],
                    "integrated_owner": region["integrated_owner"],
                    "integration_score": region["integration_score"],
                    "core_status": region["core_status"],
                    "unrest": region["unrest"],
                    "unrest_event_level": region["unrest_event_level"],
                    "unrest_event_turns_remaining": region["unrest_event_turns_remaining"],
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
            "strategy": world.factions[faction_name].doctrine_label,
            "doctrine_label": world.factions[faction_name].doctrine_label,
            "doctrine_summary": world.factions[faction_name].doctrine_summary,
            "terrain_identity": world.factions[faction_name].doctrine_profile.terrain_identity,
            "homeland_identity": world.factions[faction_name].doctrine_profile.homeland_identity,
            "climate_identity": world.factions[faction_name].doctrine_profile.climate_identity,
            "is_rebel": world.factions[faction_name].is_rebel,
            "origin_faction": world.factions[faction_name].origin_faction,
            "proto_state": world.factions[faction_name].proto_state,
            "government_type": world.factions[faction_name].government_type,
            "rebel_age": world.factions[faction_name].rebel_age,
            "independence_score": world.factions[faction_name].independence_score,
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
                "display_name": get_region_display_name(world.regions[region_name]),
                "terrain_tags": list(world.regions[region_name].terrain_tags),
                "terrain_label": format_terrain_label(world.regions[region_name].terrain_tags),
                "climate": world.regions[region_name].climate,
                "climate_label": format_climate_label(world.regions[region_name].climate),
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
                "display_name": get_region_display_name(world.regions[region_name]),
                "terrain_tags": list(world.regions[region_name].terrain_tags),
                "terrain_label": format_terrain_label(world.regions[region_name].terrain_tags),
                "climate": world.regions[region_name].climate,
                "climate_label": format_climate_label(world.regions[region_name].climate),
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
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
      flex-wrap: wrap;
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
    .toggle-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
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
    .timeline-controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
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
    .atlas-symbol {{
      fill: none;
      stroke: rgba(66, 59, 46, 0.44);
      stroke-width: 1.35;
      stroke-linecap: round;
      stroke-linejoin: round;
      opacity: 0.72;
      pointer-events: none;
    }}
    .atlas-symbol.soft-fill {{
      fill: rgba(250, 244, 232, 0.1);
    }}
    .atlas-symbol.water {{
      stroke: rgba(54, 105, 150, 0.58);
    }}
    .atlas-symbol.vegetation {{
      stroke: rgba(55, 98, 60, 0.58);
    }}
    .atlas-symbol.earth {{
      stroke: rgba(104, 81, 56, 0.58);
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
    .terrain-overlay {{
      font-size: 9.5px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 700;
      fill: #4b5f4b;
      pointer-events: none;
      opacity: 0.88;
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
    .terrain-legend {{
      margin-top: 10px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .timeline-shell {{
      background: rgba(255,255,255,0.46);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 20px;
      padding: 14px;
    }}
    .timeline-caption {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 0.94rem;
      line-height: 1.6;
    }}
    .timeline-key {{
      margin-top: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .timeline-key-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .timeline-line-chip {{
      width: 18px;
      height: 3px;
      border-radius: 999px;
      display: inline-block;
    }}
    .timeline-axis {{
      stroke: rgba(63, 74, 89, 0.22);
      stroke-width: 1.4;
    }}
    .timeline-grid {{
      stroke: rgba(63, 74, 89, 0.12);
      stroke-width: 1;
      stroke-dasharray: 4 6;
    }}
    .timeline-label {{
      fill: var(--muted);
      font-size: 12px;
      font-family: Georgia, "Times New Roman", serif;
    }}
    .timeline-line {{
      fill: none;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .timeline-dot {{
      stroke: rgba(255,255,255,0.9);
      stroke-width: 2;
    }}
    .timeline-shift {{
      fill: #fff7d6;
      stroke: #9a7a2f;
      stroke-width: 1.5;
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
    .terrain-chip {{
      width: 14px;
      height: 14px;
      border-radius: 5px;
      border: 1px solid rgba(17, 24, 39, 0.16);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.28);
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
    .event-header {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .event-icon {{
      width: 28px;
      height: 28px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      font-size: 0.95rem;
      line-height: 1;
      border: 1px solid rgba(31, 41, 51, 0.12);
      background: rgba(255,255,255,0.9);
      color: var(--ink);
    }}
    .event-icon-expand {{
      background: rgba(61, 122, 72, 0.14);
      color: #2f6a39;
    }}
    .event-icon-invest {{
      background: rgba(189, 140, 58, 0.18);
      color: #8a5a12;
    }}
    .event-icon-attack {{
      background: rgba(143, 74, 66, 0.16);
      color: #7e2f24;
    }}
    .event-icon-unrest {{
      background: rgba(173, 95, 33, 0.16);
      color: #8c4b12;
    }}
    .event-icon-secession {{
      background: rgba(110, 42, 74, 0.18);
      color: #6e2a4a;
    }}
    .faction-inline {{
      font-weight: 700;
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
    .detail-grid {{
      display: grid;
      gap: 10px;
    }}
    .detail-row {{
      display: grid;
      gap: 3px;
    }}
    .detail-label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .detail-value {{
      font-size: 0.98rem;
      color: var(--ink);
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
          <div class="toggle-row">
            <div class="view-toggle" id="view-toggle"></div>
            <div class="view-toggle" id="terrain-toggle"></div>
          </div>
          <input id="turn-slider" type="range" min="0" max="0" value="0">
        </div>
        <div class="playback-layout">
          <div class="map-stage">
            <div class="map-shell">
              <svg id="simulation-map" viewBox="0 0 900 900" role="img" aria-label="Simulation map">
                <g id="atlas-background-layer" class="map-layer"></g>
                <g id="atlas-layer" class="map-layer"></g>
                <g id="atlas-symbol-layer" class="map-layer"></g>
                <g id="atlas-label-layer" class="map-layer"></g>
                <g id="atlas-terrain-layer" class="map-layer hidden"></g>
                <g id="graph-layer" class="map-layer">
                  <g id="edge-layer"></g>
                  <g id="region-layer"></g>
                  <g id="label-layer"></g>
                  <g id="terrain-layer" class="map-layer hidden"></g>
                </g>
              </svg>
            </div>
            <div class="legend" id="legend"></div>
            <div class="terrain-legend" id="terrain-legend"></div>
          </div>
          <aside class="side-rail">
            <section class="side-section">
              <h3 class="side-title">Current Turn</h3>
              <div class="summary-stack">
                <article class="summary-card" id="turn-context"></article>
                <div class="list" id="turn-events"></div>
              </div>
            </section>
            <section class="side-section">
              <h3 class="side-title">Doctrine Evolution</h3>
              <div class="summary-stack" id="doctrine-panel"></div>
            </section>
            <section class="side-section">
              <h3 class="side-title">Region Detail</h3>
              <article class="summary-card" id="region-detail"></article>
            </section>
          </aside>
        </div>
        <div class="standings-bar" id="standings"></div>
      </div>

      <div class="panel panel-hidden" id="run-summary-panel">
        <h2 class="section-title">Run Summary</h2>
        <div class="summary-stack" id="run-summary"></div>
      </div>

      <div class="panel">
        <div class="section-header">
          <h2 class="section-title">Doctrine Timeline</h2>
          <div class="timeline-controls" id="doctrine-timeline-controls"></div>
        </div>
        <div class="timeline-shell">
          <svg viewBox="0 0 920 320" role="img" aria-label="Doctrine posture timeline" id="doctrine-timeline"></svg>
          <div class="timeline-key" id="doctrine-timeline-key"></div>
          <p class="timeline-caption" id="doctrine-timeline-caption"></p>
        </div>
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
      showTerrainOverlay: false,
      colorMode: "ownership",
      focusRegionName: null,
    }};

    const slider = document.getElementById("turn-slider");
    const readout = document.getElementById("turn-readout");
    const playToggle = document.getElementById("play-toggle");
    const prevButton = document.getElementById("prev-turn");
    const nextButton = document.getElementById("next-turn");
    const viewToggle = document.getElementById("view-toggle");
    const terrainToggle = document.getElementById("terrain-toggle");
    const atlasBackgroundLayer = document.getElementById("atlas-background-layer");
    const atlasLayer = document.getElementById("atlas-layer");
    const atlasSymbolLayer = document.getElementById("atlas-symbol-layer");
    const atlasLabelLayer = document.getElementById("atlas-label-layer");
    const atlasTerrainLayer = document.getElementById("atlas-terrain-layer");
    const graphLayer = document.getElementById("graph-layer");
    const regionLayer = document.getElementById("region-layer");
    const edgeLayer = document.getElementById("edge-layer");
    const labelLayer = document.getElementById("label-layer");
    const terrainLayer = document.getElementById("terrain-layer");
    const legend = document.getElementById("legend");
    const terrainLegend = document.getElementById("terrain-legend");
    const standings = document.getElementById("standings");
    const turnContext = document.getElementById("turn-context");
    const turnEvents = document.getElementById("turn-events");
    const doctrinePanel = document.getElementById("doctrine-panel");
    const regionDetail = document.getElementById("region-detail");
    const runSummaryPanel = document.getElementById("run-summary-panel");
    const runSummary = document.getElementById("run-summary");
    const doctrineTimelineControls = document.getElementById("doctrine-timeline-controls");
    const doctrineTimeline = document.getElementById("doctrine-timeline");
    const doctrineTimelineKey = document.getElementById("doctrine-timeline-key");
    const doctrineTimelineCaption = document.getElementById("doctrine-timeline-caption");

    const colorByFaction = Object.fromEntries(data.factions.map((faction) => [faction.name, faction.color]));
    const terrainBaseColors = {{
      coast: "#5a88c7",
      riverland: "#43b38f",
      highland: "#8b6a4f",
      hills: "#c49a63",
      marsh: "#6d7e4a",
      forest: "#3d7a48",
      steppe: "#d4bf63",
      plains: "#b8d879",
    }};
    const climateColors = {{
      temperate: "#8ebf78",
      oceanic: "#5b90cc",
      cold: "#9dc3d9",
      arid: "#d8b46a",
      steppe: "#c9c06f",
      tropical: "#4ea56d",
    }};
    const unrestColors = {{
      calm: "#9fb4a5",
      watch: "#d8c46a",
      disturbance: "#d88b4a",
      crisis: "#b24c37",
      secession: "#6e2a4a",
    }};
    const doctrineLineColors = {{
      expansion_posture: "#2d6a4f",
      war_posture: "#b24c37",
      development_posture: "#3c78a8",
      insularity: "#7b5ea7",
    }};

    if (!state.focusFactionName && data.factions.length) {{
      state.focusFactionName = data.factions[0].name;
    }}

    function getTerrainColor(tags) {{
      const [primaryTag = "plains"] = tags || [];
      return terrainBaseColors[primaryTag] || terrainBaseColors.plains;
    }}

    function getClimateColor(climate) {{
      return climateColors[climate || "temperate"] || climateColors.temperate;
    }}

    function getUnrestTier(regionSnapshot) {{
      const unrest = Number(regionSnapshot.unrest || 0);
      const eventLevel = regionSnapshot.unrest_event_level || "none";
      if (!regionSnapshot.owner) {{
        return "secession";
      }}
      if (eventLevel === "crisis") {{
        return "crisis";
      }}
      if (eventLevel === "disturbance") {{
        return "disturbance";
      }}
      if (unrest >= 7.5) {{
        return "crisis";
      }}
      if (unrest >= 4.0) {{
        return "disturbance";
      }}
      if (unrest >= 2.0) {{
        return "watch";
      }}
      return "calm";
    }}

    function getUnrestColor(regionSnapshot) {{
      return unrestColors[getUnrestTier(regionSnapshot)] || unrestColors.calm;
    }}

    function getUnrestLabel(regionSnapshot) {{
      const unrest = Number(regionSnapshot.unrest || 0);
      const eventLevel = regionSnapshot.unrest_event_level || "none";
      if (!regionSnapshot.owner) {{
        return "Seceded / Neutral";
      }}
      if (eventLevel === "crisis") {{
        return `Crisis (${{unrest.toFixed(1)}})`;
      }}
      if (eventLevel === "disturbance") {{
        return `Disturbance (${{unrest.toFixed(1)}})`;
      }}
      if (unrest >= 7.5) {{
        return `Critical (${{unrest.toFixed(1)}})`;
      }}
      if (unrest >= 4.0) {{
        return `Moderate (${{unrest.toFixed(1)}})`;
      }}
      if (unrest >= 2.0) {{
        return `Watch (${{unrest.toFixed(1)}})`;
      }}
      return `Calm (${{unrest.toFixed(1)}})`;
    }}

    function getTerrainAbbreviation(tags) {{
      const visibleTags = (tags || []).filter((tag) => tag !== "coast");
      return visibleTags.map((tag) => tag.slice(0, 2).toUpperCase()).join("/");
    }}

    function getRegionFill(regionSnapshot, staticRegion) {{
      if (state.colorMode === "terrain") {{
        return getTerrainColor(regionSnapshot.terrain_tags || staticRegion.terrain_tags);
      }}
      if (state.colorMode === "climate") {{
        return getClimateColor(regionSnapshot.climate || staticRegion.climate);
      }}
      if (state.colorMode === "unrest") {{
        return getUnrestColor(regionSnapshot);
      }}
      return colorByFaction[regionSnapshot.owner] || unclaimedColor;
    }}

    function getColorModeLabel() {{
      if (state.colorMode === "terrain") {{
        return "Terrain";
      }}
      if (state.colorMode === "climate") {{
        return "Climate";
      }}
      if (state.colorMode === "unrest") {{
        return "Unrest";
      }}
      return "Ownership";
    }}

    function cycleColorMode() {{
      if (state.colorMode === "ownership") {{
        state.colorMode = "terrain";
      }} else if (state.colorMode === "terrain") {{
        state.colorMode = "climate";
      }} else if (state.colorMode === "climate") {{
        state.colorMode = "unrest";
      }} else {{
        state.colorMode = "ownership";
      }}
    }}

    function formatPosture(value) {{
      if (value >= 0.72) {{
        return "High";
      }}
      if (value >= 0.46) {{
        return "Medium";
      }}
      return "Low";
    }}

    function getRegionDataByName(regionName) {{
      return data.regions.find((region) => region.name === regionName)
        || data.atlas_regions.find((region) => region.name === regionName)
        || null;
    }}

    function getFactionDataByName(factionName) {{
      return data.factions.find((faction) => faction.name === factionName) || null;
    }}

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

    function colorizeFactionNames(text) {{
      let highlighted = escapeHtml(text ?? "");
      const factionsByLength = [...data.factions]
        .sort((left, right) => right.name.length - left.name.length);

      for (const faction of factionsByLength) {{
        const safeName = escapeHtml(faction.name);
        highlighted = highlighted.split(safeName).join(
          `<span class="faction-inline" style="color:${{faction.color}};">${{safeName}}</span>`,
        );
      }}

      return highlighted;
    }}

    function getEventIconData(type) {{
      if (type === "expand") {{
        return {{ symbol: "◌", className: "event-icon-expand", label: "Expansion" }};
      }}
      if (type === "invest") {{
        return {{ symbol: "▲", className: "event-icon-invest", label: "Investment" }};
      }}
      if (type === "attack") {{
        return {{ symbol: "⚔", className: "event-icon-attack", label: "Attack" }};
      }}
      return {{ symbol: "•", className: "", label: "Event" }};
    }}

    function polygonPointsText(points) {{
      return points.map((point) => `${{point[0]}},${{point[1]}}`).join(" ");
    }}

    function getAtlasSymbolOffsets(count) {{
      if (count <= 1) {{
        return [
          [-32, -24],
          [0, -32],
          [32, -24],
          [-34, 0],
          [34, 0],
          [-24, 24],
          [24, 24],
        ];
      }}
      if (count === 2) {{
        return [
          [-36, -26],
          [0, -34],
          [36, -26],
          [-38, 2],
          [38, 2],
          [-28, 26],
          [0, 32],
          [28, 26],
        ];
      }}
      return [
        [-38, -28],
        [-10, -36],
        [20, -34],
        [40, -6],
        [36, 24],
        [8, 34],
        [-22, 32],
        [-40, 6],
      ];
    }}

    function getDisplayTerrainTags(tags) {{
      const filtered = (tags || []).filter((tag) => tag !== "plains" && tag !== "coast");
      if (filtered.length) {{
        return filtered.slice(0, 3);
      }}
      return ["plains"];
    }}

    function appendAtlasTerrainSymbol(group, tag, centerX, centerY, size) {{
      if (tag === "forest") {{
        for (const offset of [-size * 0.62, 0, size * 0.62]) {{
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset).toFixed(1)}} ${{(centerY + (size * 0.72)).toFixed(1)}} L ${{(centerX + offset).toFixed(1)}} ${{(centerY - (size * 0.2)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset - (size * 0.18)).toFixed(1)}} ${{(centerY - (size * 0.62)).toFixed(1)}} L ${{(centerX + offset - (size * 0.42)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} L ${{(centerX + offset + (size * 0.08)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} Z`,
            class: "atlas-symbol vegetation soft-fill",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset + (size * 0.12)).toFixed(1)}} ${{(centerY - (size * 0.68)).toFixed(1)}} L ${{(centerX + offset - (size * 0.22)).toFixed(1)}} ${{(centerY - (size * 0.1)).toFixed(1)}} L ${{(centerX + offset + (size * 0.42)).toFixed(1)}} ${{(centerY - (size * 0.08)).toFixed(1)}} Z`,
            class: "atlas-symbol vegetation soft-fill",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset - (size * 0.46)).toFixed(1)}} ${{(centerY + (size * 0.1)).toFixed(1)}} Q ${{(centerX + offset - (size * 0.12)).toFixed(1)}} ${{(centerY - (size * 0.52)).toFixed(1)}} ${{(centerX + offset + (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.08)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset - (size * 0.36)).toFixed(1)}} ${{(centerY + (size * 0.28)).toFixed(1)}} Q ${{(centerX + offset).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} ${{(centerX + offset + (size * 0.38)).toFixed(1)}} ${{(centerY + (size * 0.26)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
        }}
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.95)).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}} Q ${{centerX.toFixed(1)}} ${{(centerY + (size * 0.9)).toFixed(1)}} ${{(centerX + (size * 0.95)).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}}`,
          class: "atlas-symbol vegetation",
        }}));
        return;
      }}

      if (tag === "highland") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.55)).toFixed(1)}} L ${{(centerX - (size * 0.32)).toFixed(1)}} ${{(centerY - (size * 0.5)).toFixed(1)}} L ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}} L ${{(centerX + (size * 0.62)).toFixed(1)}} ${{(centerY - (size * 0.38)).toFixed(1)}} L ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.48)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.3)).toFixed(1)}} ${{(centerY + (size * 0.15)).toFixed(1)}} L ${{(centerX - (size * 0.12)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.72)).toFixed(1)}} ${{(centerY + (size * 0.46)).toFixed(1)}} L ${{(centerX - (size * 0.46)).toFixed(1)}} ${{(centerY - (size * 0.12)).toFixed(1)}} L ${{(centerX - (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}} L ${{(centerX + (size * 0.34)).toFixed(1)}} ${{(centerY - (size * 0.16)).toFixed(1)}} L ${{(centerX + (size * 0.7)).toFixed(1)}} ${{(centerY + (size * 0.38)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        return;
      }}

      if (tag === "riverland") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} C ${{(centerX - (size * 0.58)).toFixed(1)}} ${{(centerY - (size * 0.82)).toFixed(1)}}, ${{(centerX - (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}, ${{centerX.toFixed(1)}} ${{centerY.toFixed(1)}} C ${{(centerX + (size * 0.2)).toFixed(1)}} ${{(centerY - (size * 0.42)).toFixed(1)}}, ${{(centerX + (size * 0.56)).toFixed(1)}} ${{(centerY + (size * 0.82)).toFixed(1)}}, ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.68)).toFixed(1)}} ${{(centerY + (size * 0.22)).toFixed(1)}} C ${{(centerX - (size * 0.3)).toFixed(1)}} ${{(centerY + (size * 0.04)).toFixed(1)}}, ${{(centerX - (size * 0.12)).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}}, ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        return;
      }}

      if (tag === "coast") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY - (size * 0.12)).toFixed(1)}} C ${{(centerX - (size * 0.55)).toFixed(1)}} ${{(centerY - (size * 0.72)).toFixed(1)}}, ${{(centerX + (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.08)).toFixed(1)}}, ${{(centerX + size).toFixed(1)}} ${{(centerY - (size * 0.3)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.74)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}} Q ${{(centerX - (size * 0.28)).toFixed(1)}} ${{(centerY + (size * 0.06)).toFixed(1)}} ${{centerX.toFixed(1)}} ${{(centerY + (size * 0.32)).toFixed(1)}} Q ${{(centerX + (size * 0.28)).toFixed(1)}} ${{(centerY + (size * 0.58)).toFixed(1)}} ${{(centerX + (size * 0.74)).toFixed(1)}} ${{(centerY + (size * 0.28)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        return;
      }}

      if (tag === "marsh") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}} Q ${{(centerX - (size * 0.55)).toFixed(1)}} ${{(centerY + (size * 0.22)).toFixed(1)}} ${{(centerX - (size * 0.12)).toFixed(1)}} ${{(centerY + (size * 0.48)).toFixed(1)}} T ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.44)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        for (const offsetX of [-size * 0.48, 0, size * 0.48]) {{
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offsetX).toFixed(1)}} ${{(centerY + (size * 0.72)).toFixed(1)}} Q ${{(centerX + offsetX - (size * 0.08)).toFixed(1)}} ${{centerY.toFixed(1)}} ${{(centerX + offsetX).toFixed(1)}} ${{(centerY - (size * 0.46)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
        }}
        return;
      }}

      if (tag === "hills") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.5)).toFixed(1)}} Q ${{(centerX - (size * 0.58)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} ${{(centerX - (size * 0.16)).toFixed(1)}} ${{(centerY + (size * 0.22)).toFixed(1)}} Q ${{(centerX + (size * 0.16)).toFixed(1)}} ${{(centerY - (size * 0.22)).toFixed(1)}} ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.72)).toFixed(1)}} ${{(centerY + (size * 0.2)).toFixed(1)}} Q ${{centerX.toFixed(1)}} ${{(centerY - (size * 0.46)).toFixed(1)}} ${{(centerX + (size * 0.72)).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.92)).toFixed(1)}} ${{(centerY + (size * 0.58)).toFixed(1)}} Q ${{(centerX - (size * 0.54)).toFixed(1)}} ${{(centerY + (size * 0.1)).toFixed(1)}} ${{(centerX - (size * 0.2)).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}} Q ${{(centerX + (size * 0.42)).toFixed(1)}} ${{(centerY - (size * 0.12)).toFixed(1)}} ${{(centerX + (size * 0.92)).toFixed(1)}} ${{(centerY + (size * 0.52)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        return;
      }}

      if (tag === "steppe") {{
        for (const offsetX of [-size * 0.55, 0, size * 0.55]) {{
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offsetX).toFixed(1)}} ${{(centerY + (size * 0.72)).toFixed(1)}} Q ${{(centerX + offsetX - (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}} ${{(centerX + offsetX).toFixed(1)}} ${{(centerY - (size * 0.36)).toFixed(1)}} Q ${{(centerX + offsetX + (size * 0.22)).toFixed(1)}} ${{(centerY + (size * 0.06)).toFixed(1)}} ${{(centerX + offsetX).toFixed(1)}} ${{(centerY + (size * 0.64)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
        }}
        return;
      }}

      group.appendChild(svgElement("path", {{
        d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}} Q ${{(centerX - (size * 0.45)).toFixed(1)}} ${{(centerY + (size * 0.1)).toFixed(1)}} ${{centerX.toFixed(1)}} ${{(centerY + (size * 0.26)).toFixed(1)}} Q ${{(centerX + (size * 0.45)).toFixed(1)}} ${{(centerY - (size * 0.04)).toFixed(1)}} ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.24)).toFixed(1)}}`,
        class: "atlas-symbol earth",
      }}));
    }}

    function buildStaticMap() {{
      function attachTitle(element, id) {{
        const title = svgElement("title", {{ id }});
        element.appendChild(title);
      }}

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
          const polygon = svgElement("polygon", {{
            points: polygonPointsText(region.polygon),
            class: "atlas-territory",
            id: `atlas-region-${{region.name}}`,
          }});
          attachTitle(polygon, `atlas-title-${{region.name}}`);
          polygon.addEventListener("mouseenter", () => {{
            state.focusRegionName = region.name;
            renderRegionDetail(data.snapshots[state.currentTurn]);
          }});
          atlasLayer.appendChild(polygon);

          const terrainTags = getDisplayTerrainTags(region.terrain_tags);
          const symbolOffsets = getAtlasSymbolOffsets(terrainTags.length);
          const terrainGroup = svgElement("g", {{
            id: `atlas-symbols-${{region.name}}`,
          }});
          symbolOffsets.forEach((offset, index) => {{
            const tag = terrainTags[index % terrainTags.length];
            const [offsetX, offsetY] = offset;
            appendAtlasTerrainSymbol(
              terrainGroup,
              tag,
              region.label_x + offsetX,
              region.label_y + offsetY,
              8,
            );
          }});
          atlasSymbolLayer.appendChild(terrainGroup);

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

          atlasTerrainLayer.appendChild(svgElement("text", {{
            x: region.label_x,
            y: region.label_y + 28,
            "text-anchor": "middle",
            class: "terrain-overlay",
            id: `atlas-terrain-${{region.name}}`,
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
        const node = svgElement("circle", {{
          cx: region.x,
          cy: region.y,
          r: 25,
          class: "region-node",
          id: `region-node-${{region.name}}`,
        }});
        attachTitle(node, `region-title-${{region.name}}`);
        node.addEventListener("mouseenter", () => {{
          state.focusRegionName = region.name;
          renderRegionDetail(data.snapshots[state.currentTurn]);
        }});
        regionLayer.appendChild(node);

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

        terrainLayer.appendChild(svgElement("text", {{
          x: region.x,
          y: region.y + 28,
          "text-anchor": "middle",
          class: "terrain-overlay",
          id: `region-terrain-${{region.name}}`,
        }}));
      }}
    }}

    function renderViewToggle() {{
      terrainToggle.innerHTML = `
        <button type="button" class="secondary" data-terrain="overlay">Show Terrain</button>
        <button type="button" class="secondary" data-terrain="mode">Cycle Map Colors</button>
      `;

      if (!data.atlas_regions.length) {{
        graphLayer.classList.remove("hidden");
        atlasLayer.classList.add("hidden");
        atlasLabelLayer.classList.add("hidden");
        for (const button of terrainToggle.querySelectorAll("[data-terrain]")) {{
          const isActive = (
            (button.dataset.terrain === "overlay" && state.showTerrainOverlay)
            || (button.dataset.terrain === "mode" && state.colorMode !== "ownership")
          );
          button.classList.toggle("active", isActive);
          button.addEventListener("click", () => {{
            if (button.dataset.terrain === "overlay") {{
              state.showTerrainOverlay = !state.showTerrainOverlay;
            }} else if (button.dataset.terrain === "mode") {{
              cycleColorMode();
            }}
            syncMapView();
            renderLegend();
            renderTurn(state.currentTurn);
          }});
        }}
        syncMapView();
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
          renderTurn(state.currentTurn);
        }});
      }}

      for (const button of terrainToggle.querySelectorAll("[data-terrain]")) {{
        const isActive = (
          (button.dataset.terrain === "overlay" && state.showTerrainOverlay)
          || (button.dataset.terrain === "mode" && state.colorMode !== "ownership")
        );
        button.classList.toggle("active", isActive);
        button.addEventListener("click", () => {{
          if (button.dataset.terrain === "overlay") {{
            state.showTerrainOverlay = !state.showTerrainOverlay;
          }} else if (button.dataset.terrain === "mode") {{
            cycleColorMode();
          }}
          syncMapView();
          renderLegend();
          renderTurn(state.currentTurn);
        }});
      }}

      syncMapView();
    }}

    function syncMapView() {{
      const showAtlas = state.mapView === "atlas" && data.atlas_regions.length;
      atlasBackgroundLayer.classList.toggle("hidden", !showAtlas);
      atlasLayer.classList.toggle("hidden", !showAtlas);
      atlasSymbolLayer.classList.toggle("hidden", !showAtlas);
      atlasLabelLayer.classList.toggle("hidden", !showAtlas);
      atlasTerrainLayer.classList.toggle("hidden", !showAtlas || !state.showTerrainOverlay);
      graphLayer.classList.toggle("hidden", showAtlas);
      terrainLayer.classList.toggle("hidden", !state.showTerrainOverlay);

      for (const button of viewToggle.querySelectorAll("[data-view]")) {{
        button.classList.toggle("active", button.dataset.view === state.mapView);
      }}
      for (const button of terrainToggle.querySelectorAll("[data-terrain]")) {{
        const isActive = (
          (button.dataset.terrain === "overlay" && state.showTerrainOverlay)
          || (button.dataset.terrain === "mode" && state.colorMode !== "ownership")
        );
        button.classList.toggle("active", isActive);
      }}
    }}

    function renderLegend() {{
      let items;
      if (state.colorMode === "terrain") {{
        const uniqueTerrain = new Map();
        for (const region of data.regions) {{
          const key = region.terrain_label;
          if (!uniqueTerrain.has(key)) {{
            uniqueTerrain.set(key, region.terrain_tags);
          }}
        }}
        items = [...uniqueTerrain.entries()].map(([label, tags]) => `
          <span class="legend-item">
            <span class="swatch" style="background:${{getTerrainColor(tags)}}"></span>
            Terrain: ${{escapeHtml(label)}}
          </span>
        `);
      }} else if (state.colorMode === "climate") {{
        const uniqueClimates = new Map();
        for (const region of data.regions) {{
          if (!uniqueClimates.has(region.climate)) {{
            uniqueClimates.set(region.climate, region.climate_label);
          }}
        }}
        items = [...uniqueClimates.entries()].map(([climate, label]) => `
          <span class="legend-item">
            <span class="swatch" style="background:${{getClimateColor(climate)}}"></span>
            Climate: ${{escapeHtml(label)}}
          </span>
        `);
      }} else if (state.colorMode === "unrest") {{
        const unrestEntries = [
          ["calm", "Calm"],
          ["watch", "Watch"],
          ["disturbance", "Disturbance"],
          ["crisis", "Crisis"],
          ["secession", "Seceded / Neutral"],
        ];
        items = unrestEntries.map(([tier, label]) => `
          <span class="legend-item">
            <span class="swatch" style="background:${{unrestColors[tier]}}"></span>
            Unrest: ${{escapeHtml(label)}}
          </span>
        `);
      }} else {{
        items = [
          ...data.factions.map((faction) => `<span class="legend-item"><span class="swatch" style="background:${{faction.color}}"></span>${{escapeHtml(faction.name)}} <span class="subtle">${{escapeHtml(faction.doctrine_label)}}</span></span>`),
          `<span class="legend-item"><span class="swatch" style="background:${{unclaimedColor}}"></span>Unclaimed</span>`,
        ];
      }}
      legend.innerHTML = items.join("");
    }}

    function renderTerrainLegend() {{
      const uniqueTerrain = new Map();
      for (const region of data.regions) {{
        const key = region.terrain_label;
        if (!uniqueTerrain.has(key)) {{
          uniqueTerrain.set(key, region.terrain_tags);
        }}
      }}

      terrainLegend.innerHTML = [...uniqueTerrain.entries()].map(([label, tags]) => `
        <span class="legend-item">
          <span class="terrain-chip" style="background:${{getTerrainColor(tags)}}"></span>
          ${{escapeHtml(label)}}
        </span>
      `).join("");
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

    function buildDoctrineTimelineControls() {{
      doctrineTimelineControls.innerHTML = data.factions.map((faction) => `
        <button type="button" class="secondary${{faction.name === state.focusFactionName ? " active" : ""}}" data-faction="${{escapeHtml(faction.name)}}">
          ${{escapeHtml(faction.name)}}
        </button>
      `).join("");

      for (const button of doctrineTimelineControls.querySelectorAll("[data-faction]")) {{
        button.addEventListener("click", () => {{
          state.focusFactionName = button.dataset.faction;
          buildDoctrineTimelineControls();
          renderDoctrineTimeline();
        }});
      }}
    }}

    function renderDoctrineTimeline() {{
      const factionName = state.focusFactionName || data.factions[0]?.name;
      const faction = getFactionDataByName(factionName);
      if (!faction) {{
        doctrineTimeline.innerHTML = "";
        doctrineTimelineKey.innerHTML = "";
        doctrineTimelineCaption.textContent = "No faction selected.";
        return;
      }}

      const history = data.snapshots
        .filter((snapshot) => snapshot.turn > 0 && snapshot.metrics && snapshot.metrics.factions[factionName])
        .map((snapshot) => ({{
          turn: snapshot.turn,
          ...snapshot.metrics.factions[factionName],
        }}));

      if (!history.length) {{
        doctrineTimeline.innerHTML = "";
        doctrineTimelineKey.innerHTML = "";
        doctrineTimelineCaption.textContent = `${{factionName}} has no doctrine history yet.`;
        return;
      }}

      const width = 920;
      const height = 320;
      const margin = {{ top: 24, right: 22, bottom: 42, left: 54 }};
      const innerWidth = width - margin.left - margin.right;
      const innerHeight = height - margin.top - margin.bottom;
      const maxTurn = Math.max(...history.map((entry) => entry.turn));
      const xForTurn = (turn) => margin.left + (((turn - 1) / Math.max(1, maxTurn - 1)) * innerWidth);
      const yForValue = (value) => margin.top + ((1 - value) * innerHeight);
      const postureKeys = ["expansion_posture", "war_posture", "development_posture", "insularity"];
      const postureLabels = {{
        expansion_posture: "Expansion",
        war_posture: "War",
        development_posture: "Development",
        insularity: "Insularity",
      }};
      const horizontalTicks = [0, 0.25, 0.5, 0.75, 1];
      const verticalTicks = history.map((entry) => entry.turn);
      const shiftPoints = history.filter((entry, index) => index > 0 && history[index - 1].doctrine_label !== entry.doctrine_label);
      const makePath = (key) => history.map((entry, index) => {{
        const x = xForTurn(entry.turn).toFixed(1);
        const y = yForValue(entry[key]).toFixed(1);
        return `${{index === 0 ? "M" : "L"}}${{x}},${{y}}`;
      }}).join(" ");

      doctrineTimeline.innerHTML = `
        <rect x="0" y="0" width="${{width}}" height="${{height}}" rx="16" fill="rgba(255,255,255,0.72)"></rect>
        ${{horizontalTicks.map((tick) => `
          <g>
            <line x1="${{margin.left}}" y1="${{yForValue(tick).toFixed(1)}}" x2="${{(width - margin.right).toFixed(1)}}" y2="${{yForValue(tick).toFixed(1)}}" class="timeline-grid"></line>
            <text x="${{(margin.left - 12).toFixed(1)}}" y="${{(yForValue(tick) + 4).toFixed(1)}}" text-anchor="end" class="timeline-label">${{tick.toFixed(2)}}</text>
          </g>
        `).join("")}}
        ${{verticalTicks.map((tick) => `
          <g>
            <line x1="${{xForTurn(tick).toFixed(1)}}" y1="${{margin.top}}" x2="${{xForTurn(tick).toFixed(1)}}" y2="${{(height - margin.bottom).toFixed(1)}}" class="timeline-grid"></line>
            <text x="${{xForTurn(tick).toFixed(1)}}" y="${{(height - 16).toFixed(1)}}" text-anchor="middle" class="timeline-label">T${{tick}}</text>
          </g>
        `).join("")}}
        <line x1="${{margin.left}}" y1="${{(height - margin.bottom).toFixed(1)}}" x2="${{(width - margin.right).toFixed(1)}}" y2="${{(height - margin.bottom).toFixed(1)}}" class="timeline-axis"></line>
        <line x1="${{margin.left}}" y1="${{margin.top}}" x2="${{margin.left}}" y2="${{(height - margin.bottom).toFixed(1)}}" class="timeline-axis"></line>
        ${{postureKeys.map((key) => `
          <path d="${{makePath(key)}}" class="timeline-line" stroke="${{doctrineLineColors[key]}}"></path>
          ${{history.map((entry) => `
            <circle cx="${{xForTurn(entry.turn).toFixed(1)}}" cy="${{yForValue(entry[key]).toFixed(1)}}" r="4.5" class="timeline-dot" fill="${{doctrineLineColors[key]}}">
              <title>${{escapeHtml(factionName)}} | Turn ${{entry.turn}} | ${{escapeHtml(postureLabels[key])}}: ${{entry[key].toFixed(2)}} | Doctrine: ${{escapeHtml(entry.doctrine_label)}}</title>
            </circle>
          `).join("")}}
        `).join("")}}
        ${{shiftPoints.map((entry) => `
          <g>
            <circle cx="${{xForTurn(entry.turn).toFixed(1)}}" cy="${{(margin.top - 8).toFixed(1)}}" r="6" class="timeline-shift">
              <title>${{escapeHtml(factionName)}} | Turn ${{entry.turn}} | Doctrine shift to ${{escapeHtml(entry.doctrine_label)}}</title>
            </circle>
          </g>
        `).join("")}}
      `;

      doctrineTimelineKey.innerHTML = postureKeys.map((key) => `
        <span class="timeline-key-item">
          <span class="timeline-line-chip" style="background:${{doctrineLineColors[key]}}"></span>
          ${{escapeHtml(postureLabels[key])}}
        </span>
      `).join("");

      const openingDoctrine = history[0].doctrine_label;
      const closingDoctrine = history[history.length - 1].doctrine_label;
      const shiftCount = shiftPoints.length;
      doctrineTimelineCaption.textContent = `${{factionName}} began this run as ${{openingDoctrine}}, ended as ${{closingDoctrine}}, and shifted doctrine ${{shiftCount}} time${{shiftCount === 1 ? "" : "s"}} while its posture scores evolved across the simulation.`;
    }}

    function syncRunSummaryVisibility(turn) {{
      runSummaryPanel.classList.toggle("panel-hidden", turn < data.turns);
    }}

    function renderTurnContext(turn, snapshot) {{
      const eventCount = snapshot.events.length;
      const contestedCount = snapshot.contested_regions.length;
      const changedCount = snapshot.changed_regions.length;
      const unstableCount = Object.values(snapshot.regions).filter((region) =>
        Number(region.unrest || 0) >= 4 || ((region.unrest_event_level || "none") !== "none")
      ).length;
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
            <span>${{unstableCount}} unstable region${{unstableCount === 1 ? "" : "s"}}</span>
            <span>Map mode: ${{getColorModeLabel()}}</span>
          </div>
        `;
      }}

    function renderRegionDetail(snapshot) {{
      const regionName = state.focusRegionName || snapshot.changed_regions[0] || data.regions[0]?.name;
      if (!regionName) {{
        regionDetail.innerHTML = `<strong>No Region Selected</strong><p class="summary-copy">Hover a region on the map to inspect its terrain and current status.</p>`;
        return;
      }}

      const staticRegion = getRegionDataByName(regionName);
      const regionSnapshot = snapshot.regions[regionName];
      if (!staticRegion || !regionSnapshot) {{
        regionDetail.innerHTML = `<strong>No Region Selected</strong><p class="summary-copy">Hover a region on the map to inspect its terrain and current status.</p>`;
        return;
      }}

      const ownerText = regionSnapshot.owner || "Unclaimed";
      const foundingText = regionSnapshot.founding_name
        ? `${{escapeHtml(regionSnapshot.founding_name)}}${{regionSnapshot.founding_name !== regionName ? ` <span class="subtle">(${{
          escapeHtml(regionName)
        }})</span>` : ""}}`
        : escapeHtml(regionName);

      regionDetail.innerHTML = `
        <strong>${{escapeHtml(regionSnapshot.display_name || staticRegion.display_name || regionName)}}</strong>
        <div class="detail-grid">
          <div class="detail-row">
            <div class="detail-label">Region Code</div>
            <div class="detail-value">${{escapeHtml(regionName)}}</div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Terrain</div>
            <div class="detail-value">
              <span class="terrain-chip" style="background:${{getTerrainColor(regionSnapshot.terrain_tags || staticRegion.terrain_tags)}}; display:inline-block; margin-right:8px; vertical-align:middle;"></span>
              ${{escapeHtml(regionSnapshot.terrain_label || staticRegion.terrain_label)}}
            </div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Climate</div>
            <div class="detail-value">
              <span class="terrain-chip" style="background:${{getClimateColor(regionSnapshot.climate || staticRegion.climate)}}; display:inline-block; margin-right:8px; vertical-align:middle;"></span>
              ${{escapeHtml(regionSnapshot.climate_label || staticRegion.climate_label || "Temperate")}}
            </div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Owner</div>
            <div class="detail-value">${{escapeHtml(ownerText)}}</div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Integration</div>
            <div class="detail-value">${{escapeHtml(regionSnapshot.core_status || "frontier")}} (${{Number(regionSnapshot.integration_score || 0).toFixed(1)}})</div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Unrest</div>
            <div class="detail-value">
              <span class="terrain-chip" style="background:${{getUnrestColor(regionSnapshot)}}; display:inline-block; margin-right:8px; vertical-align:middle;"></span>
              ${{escapeHtml(getUnrestLabel(regionSnapshot))}}
            </div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Unrest Event</div>
            <div class="detail-value">
              ${{escapeHtml(regionSnapshot.unrest_event_level || "none")}}
              ${{Number(regionSnapshot.unrest_event_turns_remaining || 0) > 0 ? ` (${{Number(regionSnapshot.unrest_event_turns_remaining)}} turn${{Number(regionSnapshot.unrest_event_turns_remaining) === 1 ? "" : "s"}} left)` : ""}}
            </div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Homeland Of</div>
            <div class="detail-value">${{escapeHtml(regionSnapshot.homeland_faction_id || "None")}}</div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Resources</div>
            <div class="detail-value">R${{regionSnapshot.resources}}</div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Founding Name</div>
            <div class="detail-value">${{foundingText}}</div>
          </div>
          <div class="detail-row">
            <div class="detail-label">Neighbors</div>
            <div class="detail-value">${{staticRegion.neighbors.length}}</div>
          </div>
        </div>
      `;
    }}

    function renderDoctrinePanel(snapshot) {{
      const previousSnapshot = state.currentTurn > 0 ? data.snapshots[state.currentTurn - 1] : null;
      const currentMetrics = snapshot.metrics ? snapshot.metrics.factions : null;
      const previousMetrics = previousSnapshot && previousSnapshot.metrics
        ? previousSnapshot.metrics.factions
        : null;

      doctrinePanel.innerHTML = data.factions.map((faction) => {{
        const metrics = currentMetrics ? currentMetrics[faction.name] : null;
        const previous = previousMetrics ? previousMetrics[faction.name] : null;

        if (!metrics) {{
          return `
            <article class="summary-card">
              <strong>${{escapeHtml(faction.name)}}</strong>
              <div class="subtle">${{escapeHtml(faction.homeland_identity)}} homeland</div>
              <p class="summary-copy">Doctrine is still forming from the starting terrain before the first turn resolves.</p>
            </article>
          `;
        }}

        const doctrineShift = previous && previous.doctrine_label !== metrics.doctrine_label
          ? `<div class="event-meta">Shifted from ${{escapeHtml(previous.doctrine_label)}} on the previous turn.</div>`
          : "";
        const polityStatus = faction.is_rebel
          ? (
              (faction.proto_state
                ? "Proto-state rebellion"
                : `${{escapeHtml(faction.government_type || "State")}} successor`)
              + (faction.origin_faction ? ` from ${{escapeHtml(faction.origin_faction)}}` : "")
            )
          : "Established faction";
        const rebelLifecycle = faction.is_rebel
          ? `
              <div class="detail-row">
                <div class="detail-label">Rebel Age</div>
                <div class="detail-value">${{Number(faction.rebel_age || 0)}} turn${{Number(faction.rebel_age || 0) === 1 ? "" : "s"}}</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Independence</div>
                <div class="detail-value">${{Number(faction.independence_score || 0).toFixed(1)}}</div>
              </div>
            `
          : "";

        return `
          <article class="summary-card">
            <strong>${{escapeHtml(faction.name)}}</strong>
            <div class="detail-grid">
              <div class="detail-row">
                <div class="detail-label">Polity</div>
                <div class="detail-value">${{polityStatus}}</div>
              </div>
              ${{rebelLifecycle}}
              <div class="detail-row">
                <div class="detail-label">Doctrine</div>
                <div class="detail-value">${{escapeHtml(metrics.doctrine_label)}}</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Homeland</div>
                <div class="detail-value">${{escapeHtml(metrics.homeland_identity)}}</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Current Terrain Identity</div>
                <div class="detail-value">${{escapeHtml(metrics.terrain_identity)}}</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Climate Identity</div>
                <div class="detail-value">${{escapeHtml(metrics.climate_identity || faction.climate_identity || "Temperate")}}</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Realm Structure</div>
                <div class="detail-value">H${{metrics.homeland_regions}} / C${{metrics.core_regions}} / F${{metrics.frontier_regions}}</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Expansion</div>
                <div class="detail-value">${{formatPosture(metrics.expansion_posture)}} (${{metrics.expansion_posture.toFixed(2)}})</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">War</div>
                <div class="detail-value">${{formatPosture(metrics.war_posture)}} (${{metrics.war_posture.toFixed(2)}})</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Development</div>
                <div class="detail-value">${{formatPosture(metrics.development_posture)}} (${{metrics.development_posture.toFixed(2)}})</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Insularity</div>
                <div class="detail-value">${{formatPosture(metrics.insularity)}} (${{metrics.insularity.toFixed(2)}})</div>
              </div>
            </div>
            ${{doctrineShift}}
          </article>
        `;
      }}).join("");
    }}

    function renderStandings(snapshot) {{
      standings.innerHTML = snapshot.standings.map((entry, index) => `
        <article class="standing-item bar">
          <div class="standing-row">
            <strong>#${{index + 1}} ${{escapeHtml(entry.faction)}}</strong>
            <span class="pill" style="background:${{colorByFaction[entry.faction]}}22;">${{escapeHtml(data.factions.find((faction) => faction.name === entry.faction).doctrine_label)}}</span>
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

      turnEvents.innerHTML = snapshot.events.map((event) => {{
        const icon = getEventIconData(event.type);
        if (event.type === "unrest_disturbance" || event.type === "unrest_crisis") {{
          icon.symbol = "!";
          icon.className = "event-icon-unrest";
          icon.label = "Unrest";
        }} else if (event.type === "unrest_secession") {{
          icon.symbol = "x";
          icon.className = "event-icon-secession";
          icon.label = "Secession";
        }} else if (event.type === "rebel_independence") {{
          icon.symbol = "*";
          icon.className = "event-icon-success";
          icon.label = "Independence";
        }}
        return `
        <article class="event-item">
          <div class="event-header">
            <span class="event-icon ${{icon.className}}" title="${{escapeHtml(icon.label)}}">${{icon.symbol}}</span>
            <strong>${{colorizeFactionNames(event.title)}}</strong>
          </div>
          <div>${{colorizeFactionNames(event.summary)}}</div>
          <div class="event-meta">Type: ${{escapeHtml(event.type)}}${{event.region_reference ? ` - Region ${{escapeHtml(event.region_reference)}}` : ""}}${{event.terrain_label ? ` - Terrain ${{escapeHtml(event.terrain_label)}}` : ""}}</div>
        </article>
      `;
      }}).join("");
    }}

    function applyUnrestStyling(element, regionSnapshot, isGraphView) {{
      const tier = getUnrestTier(regionSnapshot);
      if (tier === "disturbance" || tier === "crisis" || tier === "secession") {{
        element.setAttribute("stroke", getUnrestColor(regionSnapshot));
        element.setAttribute("stroke-width", isGraphView ? (tier === "crisis" ? 4 : 3) : (tier === "crisis" ? 5 : 4));
      }} else {{
        element.removeAttribute("stroke");
        element.removeAttribute("stroke-width");
      }}
    }}

    function updateMap(snapshot) {{
      const changed = new Set(snapshot.changed_regions);
      const contested = new Set(snapshot.contested_regions);

      for (const region of data.regions) {{
        const regionSnapshot = snapshot.regions[region.name];
        const fill = getRegionFill(regionSnapshot, region);
        const node = document.getElementById(`region-node-${{region.name}}`);
        const label = document.getElementById(`region-label-${{region.name}}`);
        const resource = document.getElementById(`region-resource-${{region.name}}`);

        node.setAttribute("fill", fill);
        applyUnrestStyling(node, regionSnapshot, true);
        node.classList.toggle("changed", changed.has(region.name));
        node.classList.toggle("contested", contested.has(region.name));
        label.textContent = regionSnapshot.display_name || region.display_name || region.name;
        resource.textContent = `R${{regionSnapshot.resources}}${{(regionSnapshot.unrest_event_level || "none") === "crisis" ? " !!" : (Number(regionSnapshot.unrest || 0) >= 4 ? " !" : "")}}`;
        resource.setAttribute("fill", getUnrestColor(regionSnapshot));
        const title = document.getElementById(`region-title-${{region.name}}`);
        const terrainOverlay = document.getElementById(`region-terrain-${{region.name}}`);
        if (title) {{
          const ownerText = regionSnapshot.owner || "Unclaimed";
          const terrainText = regionSnapshot.terrain_label || region.terrain_label || "Plains";
          const climateText = regionSnapshot.climate_label || region.climate_label || "Temperate";
          const unrestText = getUnrestLabel(regionSnapshot);
          title.textContent = `${{regionSnapshot.display_name || region.display_name || region.name}} (${{region.name}}) - ${{ownerText}} - ${{terrainText}} - ${{climateText}} - Unrest: ${{unrestText}}`;
        }}
        if (terrainOverlay) {{
          terrainOverlay.textContent = getTerrainAbbreviation(regionSnapshot.terrain_tags || region.terrain_tags);
          terrainOverlay.setAttribute("fill", getTerrainColor(regionSnapshot.terrain_tags || region.terrain_tags));
        }}
      }}

      for (const region of data.atlas_regions) {{
        const regionSnapshot = snapshot.regions[region.name];
        const fill = getRegionFill(regionSnapshot, region);
        const polygon = document.getElementById(`atlas-region-${{region.name}}`);
        const label = document.getElementById(`atlas-label-${{region.name}}`);
        const resource = document.getElementById(`atlas-resource-${{region.name}}`);

        if (!polygon || !label || !resource) {{
          continue;
        }}

        polygon.setAttribute("fill", fill);
        applyUnrestStyling(polygon, regionSnapshot, false);
        polygon.classList.toggle("changed", changed.has(region.name));
        polygon.classList.toggle("contested", contested.has(region.name));
        label.textContent = regionSnapshot.display_name || region.display_name || region.name;
        resource.textContent = `R${{regionSnapshot.resources}}${{(regionSnapshot.unrest_event_level || "none") === "crisis" ? " !!" : (Number(regionSnapshot.unrest || 0) >= 4 ? " !" : "")}}`;
        resource.setAttribute("fill", getUnrestColor(regionSnapshot));
        const title = document.getElementById(`atlas-title-${{region.name}}`);
        const terrainOverlay = document.getElementById(`atlas-terrain-${{region.name}}`);
        if (title) {{
          const ownerText = regionSnapshot.owner || "Unclaimed";
          const terrainText = regionSnapshot.terrain_label || region.terrain_label || "Plains";
          const climateText = regionSnapshot.climate_label || region.climate_label || "Temperate";
          const unrestText = getUnrestLabel(regionSnapshot);
          title.textContent = `${{regionSnapshot.display_name || region.display_name || region.name}} (${{region.name}}) - ${{ownerText}} - ${{terrainText}} - ${{climateText}} - Unrest: ${{unrestText}}`;
        }}
        if (terrainOverlay) {{
          terrainOverlay.textContent = getTerrainAbbreviation(regionSnapshot.terrain_tags || region.terrain_tags);
          terrainOverlay.setAttribute("fill", getTerrainColor(regionSnapshot.terrain_tags || region.terrain_tags));
        }}
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
      renderDoctrinePanel(snapshot);
      renderRegionDetail(snapshot);
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
    renderTerrainLegend();
    renderViewToggle();
    renderRunSummary();
    buildDoctrineTimelineControls();
    renderDoctrineTimeline();
    renderTurn(0);
  </script>
</body>
</html>"""


def write_simulation_html(world, output_path=SIMULATION_VIEWER_OUTPUT):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_simulation_html(world), encoding="utf-8")
    return output_path
