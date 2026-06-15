from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from src.calendar import format_snapshot_label, format_turn_date
from src.narrative import build_chronicle
from src.region_naming import format_region_reference


LIVE_LORE_OUTPUT = Path("reports/live_lore.html")


def _faction_region_counts(world) -> dict[str, int]:
    counts = {faction_name: 0 for faction_name in world.factions}
    for region in world.regions.values():
        if region.owner in counts:
            counts[region.owner] += 1
    return counts


def _display_name(world, faction_name: str | None) -> str:
    if faction_name is None:
        return "another faction"
    faction = world.factions.get(faction_name)
    return faction.display_name if faction is not None else faction_name


def _region_reference(world, region_name: str | None) -> str:
    if region_name is None:
        return "an unrecorded place"
    region = world.regions.get(region_name)
    if region is None:
        return region_name
    return format_region_reference(region, include_code=True)


def _format_live_event(world, event) -> str:
    actor = _display_name(world, event.faction)
    region = _region_reference(world, event.region)
    date = format_turn_date(event.turn)

    if event.type == "expand":
        return f"{date}: {actor} expanded into {region}."
    if event.type == "band_migration":
        previous_region = event.get("previous_camp_region", "its prior camp")
        return f"{date}: {actor} moved camp from {previous_region} into {region}."
    if event.type == "attack":
        defender = _display_name(world, event.get("defender"))
        outcome = "captured" if event.get("success", False) else "failed against"
        return f"{date}: {actor} attacked {defender} in {region} and {outcome} the region."
    if event.type in {"develop", "invest"}:
        project = str(event.get("project_type", "development")).replace("_", " ")
        return f"{date}: {actor} invested in {region} through {project}."
    if event.type == "polity_advance":
        return (
            f"{date}: {actor} advanced into "
            f"{event.get('new_government_type', 'new institutions')}."
        )
    if event.type == "social_form_transition":
        return (
            f"{date}: {actor} settled into "
            f"{event.get('new_government_type', 'a tribal order')}."
        )
    if event.type == "unrest_secession":
        rebel = _display_name(world, event.get("rebel_faction"))
        return f"{date}: {region} seceded from {actor} as {rebel}."
    if event.type == "rebel_independence":
        origin = _display_name(world, event.get("origin_faction"))
        return f"{date}: {actor} declared full independence from {origin}."
    if event.type == "ideology_shift":
        return f"{date}: {actor} turned toward {event.get('new_label', 'a new political current')}."
    if event.type.startswith("shock_"):
        shock_label = event.get("shock_label", event.type.replace("_", " ").title())
        return f"{date}: {shock_label} affected {region} under {actor}."
    event_label = event.type.replace("_", " ")
    return f"{date}: {actor} recorded {event_label} in {region}."


def _build_recent_events(world, limit: int = 16) -> list[dict[str, Any]]:
    recent_events = world.events[-limit:]
    return [
        {
            "turn": event.turn + 1,
            "date_label": format_turn_date(event.turn),
            "type": event.type,
            "summary": _format_live_event(world, event),
        }
        for event in recent_events
    ]


def _build_factions(world) -> list[dict[str, Any]]:
    region_counts = _faction_region_counts(world)
    factions = []
    for faction_name, faction in world.factions.items():
        factions.append(
            {
                "name": faction.display_name,
                "treasury": round(float(faction.treasury or 0.0), 2),
                "regions": region_counts.get(faction_name, 0),
                "doctrine": faction.doctrine_label,
                "culture": faction.culture_name,
                "language_family": (
                    faction.identity.language_profile.family_name
                    if faction.identity is not None
                    else faction.culture_name
                ),
            }
        )
    factions.sort(
        key=lambda faction: (
            faction["treasury"],
            faction["regions"],
            faction["name"],
        ),
        reverse=True,
    )
    return factions


def build_live_lore_state(
    world,
    *,
    map_name: str,
    total_turns: int,
    status: str = "running",
) -> dict[str, Any]:
    completed_turns = int(world.turn)
    safe_total_turns = max(0, int(total_turns))
    progress = 1.0 if safe_total_turns == 0 else min(1.0, completed_turns / safe_total_turns)
    return {
        "status": status,
        "map_name": map_name,
        "completed_turns": completed_turns,
        "total_turns": safe_total_turns,
        "progress_percent": round(progress * 100, 1),
        "turn_label": format_snapshot_label(completed_turns) if completed_turns else "Opening setup",
        "faction_count": len(world.factions),
        "region_count": len(world.regions),
        "factions": _build_factions(world),
        "recent_events": _build_recent_events(world),
        "chronicle": build_chronicle(world),
    }


def _render_progress_bar(progress_percent: float) -> str:
    width = max(0.0, min(100.0, progress_percent))
    return f'<div class="progress-track"><div class="progress-fill" style="width: {width:.1f}%"></div></div>'


def _render_recent_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<p class="empty">No events recorded yet.</p>'
    items = []
    for event in reversed(events):
        items.append(
            "<li>"
            f"<span>{html.escape(event['date_label'])}</span>"
            f"{html.escape(event['summary'])}"
            "</li>"
        )
    return "<ol class=\"event-list\">" + "\n".join(items) + "</ol>"


def _render_factions(factions: list[dict[str, Any]]) -> str:
    rows = []
    for faction in factions:
        rows.append(
            "<tr>"
            f"<td>{html.escape(faction['name'])}</td>"
            f"<td>{html.escape(faction['language_family'])}</td>"
            f"<td>{html.escape(faction['doctrine'])}</td>"
            f"<td>{faction['regions']}</td>"
            f"<td>{faction['treasury']}</td>"
            "</tr>"
        )
    return (
        '<table class="faction-table">'
        "<thead><tr><th>Faction</th><th>Language</th><th>Doctrine</th><th>Regions</th><th>Treasury</th></tr></thead>"
        "<tbody>"
        + "\n".join(rows)
        + "</tbody></table>"
    )


def render_live_lore_html(state: dict[str, Any]) -> str:
    status = str(state["status"])
    refresh_meta = '<meta http-equiv="refresh" content="2">' if status == "running" else ""
    status_label = "Running" if status == "running" else "Complete"
    progress = float(state["progress_percent"])
    chronicle = html.escape(state["chronicle"])
    state_json = json.dumps(state, ensure_ascii=True, sort_keys=True)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {refresh_meta}
  <title>Clashvergence Live Lore</title>
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f1e8;
      --ink: #1f2420;
      --muted: #687067;
      --line: #d7c9b6;
      --panel: #fffaf0;
      --accent: #2f766d;
      --accent-strong: #9a4f28;
      --shadow: rgba(31, 36, 32, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 15px/1.55 "Segoe UI", system-ui, sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      border-bottom: 1px solid var(--line);
      background: rgba(246, 241, 232, 0.96);
      backdrop-filter: blur(10px);
    }}
    .topbar {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 16px 24px 14px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      font-weight: 750;
      letter-spacing: 0;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }}
    .status {{
      min-width: 220px;
      text-align: right;
      color: var(--muted);
      font-size: 13px;
    }}
    .status strong {{
      display: block;
      color: var(--accent);
      font-size: 18px;
    }}
    .progress-track {{
      height: 7px;
      overflow: hidden;
      background: #e8ddce;
      border-top: 1px solid var(--line);
    }}
    .progress-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-strong));
      transition: width 180ms ease-out;
    }}
    main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 22px 24px 40px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(300px, 380px);
      gap: 22px;
      align-items: start;
    }}
    section, aside {{
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: 0 10px 30px var(--shadow);
    }}
    section {{
      padding: 22px;
    }}
    aside {{
      position: sticky;
      top: 96px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 15px;
      color: var(--accent-strong);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      font: 15px/1.6 Georgia, "Times New Roman", serif;
    }}
    .side-section {{
      padding: 18px;
      border-bottom: 1px solid var(--line);
    }}
    .side-section:last-child {{
      border-bottom: 0;
    }}
    .event-list {{
      margin: 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 12px;
    }}
    .event-list li {{
      padding-left: 12px;
      border-left: 3px solid var(--accent);
    }}
    .event-list span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 2px;
    }}
    .faction-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .faction-table th,
    .faction-table td {{
      padding: 8px 6px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    .faction-table th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .empty {{
      margin: 0;
      color: var(--muted);
    }}
    @media (max-width: 960px) {{
      .topbar {{
        grid-template-columns: 1fr;
      }}
      .status {{
        min-width: 0;
        text-align: left;
      }}
      main {{
        grid-template-columns: 1fr;
      }}
      aside {{
        position: static;
      }}
    }}
  </style>
</head>
<body data-status="{html.escape(status)}">
  <header>
    <div class="topbar">
      <div>
        <h1>{html.escape(str(state["map_name"]))}</h1>
        <div class="meta">
          <span>{html.escape(str(state["turn_label"]))}</span>
          <span>{state["completed_turns"]}/{state["total_turns"]} turns</span>
          <span>{state["region_count"]} regions</span>
          <span>{state["faction_count"]} factions</span>
        </div>
      </div>
      <div class="status">
        <strong>{status_label}</strong>
        {progress:.1f}% complete
      </div>
    </div>
    {_render_progress_bar(progress)}
  </header>
  <main>
    <section>
      <h2>Chronicle</h2>
      <pre>{chronicle}</pre>
    </section>
    <aside>
      <div class="side-section">
        <h2>Recent Events</h2>
        {_render_recent_events(state["recent_events"])}
      </div>
      <div class="side-section">
        <h2>Factions</h2>
        {_render_factions(state["factions"])}
      </div>
    </aside>
  </main>
  <script id="live-lore-state" type="application/json">{html.escape(state_json)}</script>
  <script>
    const scrollKey = "clashvergence-live-lore-scroll";
    window.addEventListener("load", () => {{
      const saved = sessionStorage.getItem(scrollKey);
      if (saved !== null) {{
        requestAnimationFrame(() => window.scrollTo(0, Number(saved) || 0));
      }}
    }});
    setInterval(() => {{
      sessionStorage.setItem(scrollKey, String(window.scrollY));
    }}, 250);
  </script>
</body>
</html>
"""


def write_live_lore(
    world,
    *,
    map_name: str,
    total_turns: int,
    status: str = "running",
    output_path: Path = LIVE_LORE_OUTPUT,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    state = build_live_lore_state(
        world,
        map_name=map_name,
        total_turns=total_turns,
        status=status,
    )
    output_path.write_text(render_live_lore_html(state), encoding="utf-8")
    output_path.with_suffix(".json").write_text(
        json.dumps(state, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return output_path
