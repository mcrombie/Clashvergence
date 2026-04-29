from __future__ import annotations

import html
import json
from pathlib import Path

from src.calendar import format_turn_date
from src.climate import format_climate_label
from src.event_analysis import get_final_standings
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
from src.metrics import get_metrics_log
from src.terrain import format_terrain_label

VIEWER_OUTPUT = Path("reports/simulation_view_claude.html")

INTERESTING_EVENT_TYPES = frozenset({
    "expand", "attack", "develop", "invest",
    "unrest_crisis", "unrest_secession", "rebel_independence",
    "polity_advance", "succession", "succession_crisis",
    "diplomacy_alliance", "diplomacy_pact", "diplomacy_rivalry",
    "technology_institutionalized", "regime_agitation",
})


# ── Data helpers ───────────────────────────────────────────────────────────────

def _fdname(world, fname):
    if not fname:
        return "—"
    f = world.factions.get(fname)
    return f.display_name if f else fname


def _event_title(event, world):
    fn = _fdname(world, event.faction)
    region = world.regions.get(event.region) if event.region else None
    rn = (region.display_name or region.name) if region else (event.region or "—")

    def cn(key):
        return _fdname(world, event.get(key))

    t = event.type
    if t == "expand":
        return f"{fn} expanded into {rn}"
    if t == "attack":
        ok = event.get("success", False)
        return f"{fn} {'seized' if ok else 'failed at'} {rn} (vs {cn('defender')})"
    if t in ("develop", "invest"):
        pt = (event.get("project_type") or "development").replace("_", " ")
        return f"{fn} developed {rn} — {pt}"
    if t == "unrest_crisis":
        return f"Crisis in {rn} under {fn}"
    if t == "unrest_secession":
        return f"{rn} broke from {fn} as {cn('rebel_faction')}"
    if t == "rebel_independence":
        return f"{fn} declared independence"
    if t == "polity_advance":
        gov = event.get("new_government_type") or event.get("new_polity_tier") or "higher tier"
        return f"{fn} advanced to {gov}"
    if t == "succession":
        return f"{fn} — new ruler: {event.get('new_ruler', '?')}"
    if t == "succession_crisis":
        return f"{fn} succession crisis"
    if t == "diplomacy_alliance":
        return f"{fn} & {cn('counterpart')} — alliance"
    if t == "diplomacy_pact":
        return f"{fn} & {cn('counterpart')} — pact"
    if t == "diplomacy_rivalry":
        return f"{fn} & {cn('counterpart')} — rivals"
    if t == "technology_institutionalized":
        return f"{fn} institutionalized {event.get('technology_label', 'new methods')}"
    if t == "regime_agitation":
        return f"Regime agitation in {rn} against {fn}"
    return t.replace("_", " ").title()


def _build_map_geometry(world):
    regions = MAPS[world.map_name]["regions"]
    if is_multi_ring_map(regions):
        geo = build_multi_ring_region_geometry(
            regions, map_name=world.map_name, width=700, height=700
        )
        coastline = build_multi_ring_coastline_polygon(width=700, height=700)
        return {
            "type": "polygon",
            "regions": {
                name: {
                    "polygon": [[round(p[0], 1), round(p[1], 1)] for p in g["polygon"]],
                    "label": [round(g["label"][0], 1), round(g["label"][1], 1)],
                }
                for name, g in geo.items()
            },
            "coastline": [[round(p[0], 1), round(p[1], 1)] for p in coastline],
        }
    positions = build_map_layout(regions, width=700, height=700)
    edges = get_map_edges(regions)
    return {
        "type": "node",
        "positions": {n: [round(x, 1), round(y, 1)] for n, (x, y) in positions.items()},
        "edges": [[a, b] for a, b in edges],
    }


def _build_faction_meta(world):
    return {
        fname: {
            "display_name": f.display_name,
            "color": get_faction_color(fname, internal_id=f.internal_id),
            "doctrine": f.doctrine_label,
            "government": f.government_type,
            "is_rebel": f.is_rebel,
        }
        for fname, f in world.factions.items()
    }


def _build_region_static(world):
    return {
        rname: {
            "terrain": format_terrain_label(region.terrain_tags),
            "climate": format_climate_label(region.climate),
        }
        for rname, region in world.regions.items()
    }


def _build_sparklines(world):
    lines = {fname: [] for fname in world.factions}
    for snap in get_metrics_log(world):
        for fname, fm in snap.get("factions", {}).items():
            if fname in lines:
                lines[fname].append(fm.get("treasury", 0))
    return lines


def _build_lean_turns(world):
    metrics_by_turn = {m["turn"]: m for m in get_metrics_log(world)}
    turns = []

    # Turn 0: initial state from region_history[0]
    init_hist = world.region_history[0] if world.region_history else {}
    init_regions = {}
    for rname, region in world.regions.items():
        h = init_hist.get(rname, {})
        init_regions[rname] = {
            "owner": h.get("owner", region.owner),
            "name": h.get("display_name") or region.display_name or rname,
            "pop": h.get("population", region.population),
            "unrest": 0.0,
            "status": h.get("core_status", "frontier"),
            "settlement": h.get("settlement_level", region.settlement_level),
            "taxable": round(float(h.get("taxable_value", 0.0)), 1),
            "res": h.get("resource_output_summary", ""),
        }
    turns.append({
        "turn": 0,
        "date": "Initial State",
        "regions": init_regions,
        "factions": {},
        "events": [],
    })

    for t in range(1, world.turn + 1):
        history = world.region_history[t] if len(world.region_history) > t else {}
        metrics = metrics_by_turn.get(t, {})
        turn_events = [e for e in world.events if e.turn == t - 1]

        regions = {}
        for rname, region in world.regions.items():
            h = history.get(rname, {})
            regions[rname] = {
                "owner": h.get("owner", region.owner),
                "name": h.get("display_name") or region.display_name or rname,
                "pop": h.get("population", region.population),
                "unrest": round(float(h.get("unrest", 0.0)), 2),
                "status": h.get("core_status", "frontier"),
                "settlement": h.get("settlement_level", region.settlement_level),
                "taxable": round(float(h.get("taxable_value", 0.0)), 1),
                "res": h.get("resource_output_summary", ""),
            }

        factions = {}
        for fname, fm in metrics.get("factions", {}).items():
            factions[fname] = {
                "treasury": fm.get("treasury", 0),
                "regions": fm.get("regions", 0),
                "pop": fm.get("population", 0),
                "net": round(float(fm.get("net_income", 0)), 1),
            }

        events = [
            {
                "type": e.type,
                "faction": e.faction,
                "title": _event_title(e, world),
            }
            for e in turn_events
            if e.type in INTERESTING_EVENT_TYPES
        ]

        turns.append({
            "turn": t,
            "date": format_turn_date(t - 1),
            "regions": regions,
            "factions": factions,
            "events": events,
        })

    return turns


# ── SVG map ────────────────────────────────────────────────────────────────────

def _render_svg(geometry, region_names):
    parts = ['<svg id="map-svg" viewBox="0 0 700 700" xmlns="http://www.w3.org/2000/svg">']
    if geometry["type"] == "polygon":
        if geometry.get("coastline"):
            pts = " ".join(f"{p[0]},{p[1]}" for p in geometry["coastline"])
            parts.append(f'  <polygon class="coast" points="{pts}"/>')
        for rname in region_names:
            g = geometry["regions"].get(rname)
            if not g:
                continue
            pts = " ".join(f"{p[0]},{p[1]}" for p in g["polygon"])
            parts.append(
                f'  <polygon id="r-{rname}" data-r="{rname}" class="rpoly" points="{pts}"/>'
            )
        for rname in region_names:
            g = geometry["regions"].get(rname)
            if not g:
                continue
            lx, ly = g["label"]
            parts.append(
                f'  <text id="lbl-{rname}" class="rlabel" x="{lx}" y="{ly}" data-r="{rname}"></text>'
            )
    else:
        for a, b in geometry.get("edges", []):
            pa = geometry["positions"].get(a)
            pb = geometry["positions"].get(b)
            if pa and pb:
                parts.append(
                    f'  <line x1="{pa[0]}" y1="{pa[1]}" x2="{pb[0]}" y2="{pb[1]}" class="eline"/>'
                )
        for rname in region_names:
            pos = geometry["positions"].get(rname)
            if not pos:
                continue
            x, y = pos
            parts.append(
                f'  <circle id="r-{rname}" data-r="{rname}" class="rnode" cx="{x}" cy="{y}" r="22"/>'
            )
            parts.append(
                f'  <text id="lbl-{rname}" class="rlabel" x="{x}" y="{y + 4}" data-r="{rname}"></text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


# ── HTML renderer ──────────────────────────────────────────────────────────────

def render_simulation_html_claude(world) -> str:
    geo = _build_map_geometry(world)
    region_names = sorted(MAPS[world.map_name]["regions"].keys(), key=natural_sort_key)
    faction_meta = _build_faction_meta(world)
    region_static = _build_region_static(world)
    sparklines = _build_sparklines(world)
    turns = _build_lean_turns(world)
    final_standings = get_final_standings(world)
    map_svg = _render_svg(geo, region_names)
    factions_ordered = [s["faction"] for s in final_standings]
    map_title = world.map_name.replace("_", " ").title()

    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clashvergence — {html.escape(map_title)}</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; overflow: hidden; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  font-size: 13px;
  background: #f0ece4;
  color: #1a1a1a;
  display: flex;
  flex-direction: column;
}}

/* Header */
#hdr {{
  flex: 0 0 48px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  background: #fff;
  border-bottom: 1px solid #e4dfd6;
  z-index: 10;
}}
#hdr h1 {{ font-size: 14px; font-weight: 700; letter-spacing: 0.03em; }}
.sep {{ color: #c8c2b8; }}
#map-lbl {{ font-size: 13px; color: #6b7280; }}
#turn-display {{
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: #1d5a55;
  min-width: 200px;
  text-align: right;
}}

/* Main layout */
#main {{
  flex: 1 1 0;
  display: flex;
  overflow: hidden;
}}

/* Map panel */
#map-panel {{
  flex: 1 1 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e8e3da;
  overflow: hidden;
}}
#map-svg {{
  width: 100%;
  height: 100%;
  max-width: 700px;
  max-height: 700px;
  cursor: pointer;
}}
.coast {{ fill: #bed4e4; stroke: none; }}
.rpoly {{
  stroke: rgba(255,255,255,0.9);
  stroke-width: 1.2;
  fill: #cdc8bf;
  transition: fill 0.2s;
  cursor: pointer;
}}
.rpoly:hover {{ stroke: #333; stroke-width: 2; }}
.rpoly.sel {{ stroke: #1a1a1a; stroke-width: 2.5; }}
.rlabel {{
  font-size: 9.5px;
  fill: rgba(0,0,0,0.72);
  text-anchor: middle;
  dominant-baseline: middle;
  pointer-events: none;
  font-weight: 600;
  letter-spacing: 0.02em;
}}
.rnode {{
  stroke: rgba(255,255,255,0.9);
  stroke-width: 2;
  fill: #cdc8bf;
  cursor: pointer;
  transition: fill 0.2s;
}}
.rnode:hover {{ stroke: #333; stroke-width: 2.5; }}
.eline {{ stroke: #c0bab2; stroke-width: 1.5; }}

/* Sidebar */
#sidebar {{
  flex: 0 0 270px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-left: 1px solid #e4dfd6;
  overflow: hidden;
}}
.sec-hdr {{
  padding: 10px 14px 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #9ca3af;
  border-bottom: 1px solid #f0ece6;
  flex: 0 0 auto;
}}

/* Faction cards */
#standings {{ overflow-y: auto; flex: 0 0 auto; max-height: 55%; }}
.fc {{
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 14px 9px;
  border-bottom: 1px solid #f0ece6;
}}
.fc-top {{
  display: flex;
  align-items: center;
  gap: 7px;
}}
.fc-swatch {{
  width: 9px;
  height: 9px;
  border-radius: 2px;
  flex-shrink: 0;
}}
.fc-name {{
  font-size: 12px;
  font-weight: 600;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.fc-gov {{
  font-size: 10px;
  color: #9ca3af;
  white-space: nowrap;
}}
.fc-treasury {{
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #1d5a55;
  min-width: 36px;
  text-align: right;
}}
.fc-row2 {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 16px;
  font-size: 11px;
  color: #6b7280;
  font-variant-numeric: tabular-nums;
}}
.fc-net {{ white-space: nowrap; }}
.fc-net.pos {{ color: #16a34a; }}
.fc-net.neg {{ color: #dc2626; }}
.fc-spark {{ margin-left: auto; }}

/* Event log */
#ev-wrap {{
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}}
#ev-scroll {{ flex: 1 1 0; overflow-y: auto; min-height: 0; }}
#ev-list {{ padding: 2px 0; }}
.ev {{
  display: flex;
  align-items: baseline;
  gap: 7px;
  padding: 5px 14px;
  border-bottom: 1px solid #f5f2ed;
  font-size: 11.5px;
  line-height: 1.4;
}}
.ev:last-child {{ border-bottom: none; }}
.ev-dot {{
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 4px;
}}
.ev-txt {{ color: #374151; flex: 1; }}
.ev-empty {{
  padding: 14px;
  color: #9ca3af;
  font-size: 12px;
  font-style: italic;
}}

/* Timeline */
#timeline {{
  flex: 0 0 48px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  background: #fff;
  border-top: 1px solid #e4dfd6;
}}
.tl-btn {{
  background: none;
  border: none;
  cursor: pointer;
  padding: 5px 7px;
  border-radius: 5px;
  font-size: 13px;
  color: #374151;
  line-height: 1;
  transition: background 0.12s;
}}
.tl-btn:hover {{ background: #f0ece6; }}
#scrubber {{
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  border-radius: 2px;
  background: #e0dbd3;
  outline: none;
  cursor: pointer;
}}
#scrubber::-webkit-slider-thumb {{
  -webkit-appearance: none;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #1d5a55;
  cursor: pointer;
}}
#scrubber::-moz-range-thumb {{
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: #1d5a55;
  border: none;
  cursor: pointer;
}}
#tl-counter {{
  font-size: 11px;
  color: #6b7280;
  font-variant-numeric: tabular-nums;
  min-width: 52px;
  text-align: right;
}}

/* Region detail panel */
#detail {{
  position: fixed;
  bottom: 48px;
  left: 0;
  right: 270px;
  background: #1c1c1c;
  color: #f0ece4;
  padding: 10px 18px 12px;
  border-top: 2px solid #1d5a55;
  display: none;
  z-index: 20;
}}
#detail.vis {{ display: block; }}
#det-close {{
  position: absolute;
  top: 7px;
  right: 12px;
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 17px;
  line-height: 1;
  padding: 2px 5px;
}}
#det-close:hover {{ color: #f0ece4; }}
#det-name {{ font-size: 13px; font-weight: 700; margin-bottom: 2px; }}
#det-meta {{ font-size: 11px; color: #9ca3af; margin-bottom: 5px; }}
#det-stats {{ font-size: 12px; color: #d4cfc7; }}
#det-res {{ font-size: 11px; color: #9ca3af; margin-top: 2px; }}

/* Scrollbar */
::-webkit-scrollbar {{ width: 4px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: #cdc8bf; border-radius: 2px; }}
</style>
</head>
<body>

<div id="hdr">
  <h1>Clashvergence</h1>
  <span class="sep">·</span>
  <span id="map-lbl">{html.escape(map_title)}</span>
  <span id="turn-display">Initial State</span>
</div>

<div id="main">
  <div id="map-panel">
    {map_svg}
  </div>
  <div id="sidebar">
    <div class="sec-hdr">Standings</div>
    <div id="standings"></div>
    <div id="ev-wrap">
      <div class="sec-hdr">Events This Turn</div>
      <div id="ev-scroll"><div id="ev-list"></div></div>
    </div>
  </div>
</div>

<div id="detail">
  <button id="det-close" onclick="closeDetail()">&#215;</button>
  <div id="det-name"></div>
  <div id="det-meta"></div>
  <div id="det-stats"></div>
  <div id="det-res"></div>
</div>

<div id="timeline">
  <button class="tl-btn" onclick="stepTurn(-1)" title="Previous (&#8592;)">&#9664;</button>
  <button class="tl-btn" id="btn-play" onclick="togglePlay()" title="Play/Pause (Space)">&#9654;</button>
  <button class="tl-btn" onclick="stepTurn(1)" title="Next (&#8594;)">&#9654;&#9654;</button>
  <input type="range" id="scrubber" min="0" max="{world.turn}" value="0" oninput="goTurn(+this.value)">
  <span id="tl-counter">0 / {world.turn}</span>
</div>

<script>
const WORLD = {{
  map_name: {js(world.map_name)},
  total_turns: {world.turn},
  factions: {js(faction_meta)},
  factions_ordered: {js(factions_ordered)},
  region_static: {js(region_static)},
  sparklines: {js(sparklines)},
  turns: {js(turns)}
}};

let currentTurn = 0;
let selectedRegion = null;
let playTimer = null;

// Color helpers
function hexToRgb(h) {{
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}}
function rgbToHex(r, g, b) {{
  return '#' + [r, g, b].map(v => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2,'0')).join('');
}}
function mixWhite(hex, t) {{
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r + (255-r)*t, g + (255-g)*t, b + (255-b)*t);
}}
function mixRed(hex, t) {{
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r+(210-r)*t, g*(1-t*0.6), b*(1-t*0.6));
}}
function regionFill(owner, status, unrest) {{
  if (!owner) return '#cdc8bf';
  const meta = WORLD.factions[owner];
  if (!meta) return '#bfbab2';
  let c = meta.color;
  if (status === 'frontier')    c = mixWhite(c, 0.44);
  else if (status === 'core')   c = mixWhite(c, 0.18);
  if (unrest > 0.45) c = mixRed(c, Math.min(0.55, (unrest - 0.45) * 0.9));
  return c;
}}

const SYM = {{ city: '◆ ', town: '▪ ', rural: '· ', wild: '' }};

// Map rendering
function renderMap(td) {{
  for (const [rname, rd] of Object.entries(td.regions)) {{
    const el = document.getElementById('r-' + rname);
    if (el) el.style.fill = regionFill(rd.owner, rd.status, rd.unrest);
    const lbl = document.getElementById('lbl-' + rname);
    if (lbl) lbl.textContent = (SYM[rd.settlement] || '') + (rd.name || rname);
  }}
  // Re-apply selection highlight
  if (selectedRegion) {{
    const sel = document.getElementById('r-' + selectedRegion);
    if (sel) sel.classList.add('sel');
  }}
}}

// Sparkline
function sparkline(fname, upTo) {{
  const vals = (WORLD.sparklines[fname] || []).slice(0, upTo);
  if (vals.length < 2) return '';
  const W = 56, H = 16;
  const mn = Math.min(...vals), mx = Math.max(...vals);
  const rng = mx - mn || 1;
  const pts = vals.map((v, i) => {{
    const x = (i / (vals.length - 1)) * W;
    const y = H - ((v - mn) / rng) * (H - 1);
    return x.toFixed(1) + ',' + y.toFixed(1);
  }}).join(' ');
  const color = WORLD.factions[fname]?.color || '#9ca3af';
  return `<svg width="${{W}}" height="${{H}}" style="display:block;overflow:visible">` +
    `<polyline points="${{pts}}" fill="none" stroke="${{color}}" stroke-width="1.5" stroke-linecap="round"/></svg>`;
}}

// Standings
function renderStandings(td) {{
  const sorted = [...WORLD.factions_ordered].sort((a, b) => {{
    return (td.factions[b]?.treasury ?? -1) - (td.factions[a]?.treasury ?? -1);
  }});
  document.getElementById('standings').innerHTML = sorted.map(fn => {{
    const meta = WORLD.factions[fn];
    if (!meta) return '';
    const fd = td.factions[fn] || {{}};
    const treas = fd.treasury != null ? fd.treasury : '—';
    const regs  = fd.regions  != null ? fd.regions  : '—';
    const pop   = fd.pop      != null ? (fd.pop >= 1000 ? (fd.pop/1000).toFixed(1)+'k' : fd.pop) : '—';
    const net   = fd.net      != null ? fd.net : null;
    const netCls = net != null ? (net > 0 ? 'pos' : net < 0 ? 'neg' : '') : '';
    const netStr = net != null ? (net > 0 ? '+'+net : String(net)) : '';
    const spark = sparkline(fn, td.turn);
    return `<div class="fc">
      <div class="fc-top">
        <div class="fc-swatch" style="background:${{meta.color}}"></div>
        <div class="fc-name">${{meta.display_name}}</div>
        <div class="fc-gov">${{meta.government}}</div>
        <div class="fc-treasury">${{treas}}</div>
      </div>
      <div class="fc-row2">
        <span>${{regs}} rgns</span>
        <span>·</span>
        <span>${{pop}} pop</span>
        ${{net != null ? `<span class="fc-net ${{netCls}}">${{netStr}}/turn</span>` : ''}}
        <span class="fc-spark">${{spark}}</span>
      </div>
    </div>`;
  }}).join('');
}}

// Events
function renderEvents(td) {{
  const el = document.getElementById('ev-list');
  if (!td.events || td.events.length === 0) {{
    el.innerHTML = '<div class="ev-empty">No notable events this turn.</div>';
    return;
  }}
  el.innerHTML = td.events.map(ev => {{
    const color = WORLD.factions[ev.faction]?.color || '#9ca3af';
    return `<div class="ev">
      <div class="ev-dot" style="background:${{color}}"></div>
      <div class="ev-txt">${{ev.title}}</div>
    </div>`;
  }}).join('');
}}

// Region detail
function showDetail(rname) {{
  selectedRegion = rname;
  document.querySelectorAll('.rpoly, .rnode').forEach(e => e.classList.remove('sel'));
  const el = document.getElementById('r-' + rname);
  if (el) el.classList.add('sel');

  const td = WORLD.turns[currentTurn];
  const rd = td.regions[rname];
  const rs = WORLD.region_static[rname] || {{}};
  if (!rd) return;

  const owner  = rd.owner ? (WORLD.factions[rd.owner]?.display_name || rd.owner) : 'Unclaimed';
  const ocolor = rd.owner ? (WORLD.factions[rd.owner]?.color || '#9ca3af') : '#9ca3af';
  const uLabel = rd.unrest > 0.65 ? 'HIGH' : rd.unrest > 0.35 ? 'elevated' : rd.unrest > 0.12 ? 'low' : 'stable';

  document.getElementById('det-name').innerHTML =
    `${{rd.name || rname}} <span style="color:${{ocolor}};font-size:11px;font-weight:400"> ▸ ${{owner}}</span>`;
  document.getElementById('det-meta').textContent =
    [rs.terrain, rs.climate, rd.settlement !== 'wild' ? rd.settlement : null].filter(Boolean).join(' · ');
  document.getElementById('det-stats').textContent =
    `Pop: ${{(rd.pop||0).toLocaleString()}}  ·  Unrest: ${{uLabel}}  ·  Tax value: ${{rd.taxable}}  ·  Status: ${{rd.status}}`;
  document.getElementById('det-res').textContent =
    rd.res ? 'Output: ' + rd.res : '';

  document.getElementById('detail').classList.add('vis');
}}

function closeDetail() {{
  selectedRegion = null;
  document.querySelectorAll('.rpoly, .rnode').forEach(e => e.classList.remove('sel'));
  document.getElementById('detail').classList.remove('vis');
}}

// Navigation
function goTurn(t) {{
  currentTurn = Math.max(0, Math.min(WORLD.total_turns, t));
  const td = WORLD.turns[currentTurn];
  document.getElementById('scrubber').value = currentTurn;
  document.getElementById('tl-counter').textContent = currentTurn + ' / ' + WORLD.total_turns;
  document.getElementById('turn-display').textContent =
    currentTurn === 0 ? 'Initial State' : 'Turn ' + currentTurn + ' — ' + td.date;
  renderMap(td);
  renderStandings(td);
  renderEvents(td);
  if (selectedRegion) showDetail(selectedRegion);
}}

function stepTurn(d) {{ goTurn(currentTurn + d); }}

function togglePlay() {{
  const btn = document.getElementById('btn-play');
  if (playTimer) {{
    clearInterval(playTimer);
    playTimer = null;
    btn.innerHTML = '&#9654;';
  }} else {{
    if (currentTurn >= WORLD.total_turns) goTurn(0);
    btn.innerHTML = '&#9646;&#9646;';
    playTimer = setInterval(() => {{
      if (currentTurn >= WORLD.total_turns) {{
        togglePlay();
      }} else {{
        stepTurn(1);
      }}
    }}, 800);
  }}
}}

// Keyboard
document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowLeft')  {{ stepTurn(-1); e.preventDefault(); }}
  if (e.key === 'ArrowRight') {{ stepTurn(1);  e.preventDefault(); }}
  if (e.key === ' ')          {{ togglePlay();  e.preventDefault(); }}
  if (e.key === 'Escape')     {{ closeDetail(); }}
}});

// Map click
document.getElementById('map-svg').addEventListener('click', e => {{
  const rname = e.target.dataset.r;
  if (!rname) {{ closeDetail(); return; }}
  if (selectedRegion === rname) {{ closeDetail(); return; }}
  showDetail(rname);
}});

goTurn(0);
</script>
</body>
</html>"""


def write_simulation_html_claude(world, output_path=VIEWER_OUTPUT):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_simulation_html_claude(world), encoding="utf-8")
    return output_path
