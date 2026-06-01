"""Generate a 50-turn simulation GIF from a randomly generated continent."""
from __future__ import annotations

import random
import sys
from pathlib import Path

SEED         = 7
NUM_TURNS    = 50
NUM_FACTIONS = 4
MAP_NAME     = "generated_continent"
OUT_PATH     = Path("reports/fifty_turns.gif")
FPS          = 6

random.seed(SEED)

from src.world import create_world
from src.simulation import run_simulation
from src.maps import MAPS

print(f"Generating map ({MAP_NAME}, seed={SEED})...")
world = create_world(
    map_name=MAP_NAME,
    num_factions=NUM_FACTIONS,
    seed=SEED,
    map_generation_config={"regions": 30, "seed": SEED},
)
map_def = MAPS[MAP_NAME]
print(f"  {len(map_def['regions'])} regions, {NUM_FACTIONS} factions")

print(f"Simulating {NUM_TURNS} turns...")
world = run_simulation(world, num_turns=NUM_TURNS, verbose=False)
print("  Done.")

# ── rendering ─────────────────────────────────────────────────────────────────

from debug_turn_visualizer import reconstruct_turn_snapshots, draw_snapshot
from src.map_visualization import build_map_layout, get_map_edges, get_faction_color

try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    import matplotlib.patches as mpatches
except ModuleNotFoundError:
    sys.exit("matplotlib not found — pip install matplotlib pillow")

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

regions_def = map_def["regions"]
snapshots   = reconstruct_turn_snapshots(world, MAP_NAME)
positions   = build_map_layout(regions_def, width=900, height=900)
edges       = get_map_edges(regions_def)

# Build a mapping: generic "FactionN" owner → named faction key
# The map assigns homelands to Faction1..N; world.factions has the real names.
faction_keys = list(world.factions.keys())
faction_map  = {f"Faction{i+1}": key for i, key in enumerate(faction_keys)}

def faction_display(owner: str | None) -> str:
    if owner is None:
        return "Unclaimed"
    return faction_map.get(owner, owner)

def draw_sidebar(ax, snap):
    ax.clear()
    ax.set_facecolor("#0d1117")
    ax.axis("off")

    turn_label = f"Turn {snap['turn']}" if snap['turn'] > 0 else "Initial State"
    ax.text(0.05, 0.97, turn_label, transform=ax.transAxes,
            color="white", fontsize=13, fontweight="bold", va="top")

    # Count regions per owner from this snapshot
    region_counts: dict[str, int] = {}
    for r in snap["regions"].values():
        key = faction_display(r["owner"])
        region_counts[key] = region_counts.get(key, 0) + 1

    # Faction standings
    standings = []
    for generic, named in faction_map.items():
        f = world.factions.get(named)
        count = region_counts.get(named, 0)
        treasury = f.treasury if f else 0
        color = get_faction_color(generic)
        standings.append((count, named, generic, color, treasury))
    standings.sort(reverse=True)

    ax.text(0.05, 0.88, "STANDINGS", transform=ax.transAxes,
            color="#94a3b8", fontsize=8, fontweight="bold", va="top")

    y = 0.82
    for rank, (count, named, generic, color, treasury) in enumerate(standings, 1):
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.05, y - 0.055), 0.90, 0.055,
            boxstyle="round,pad=0.005",
            facecolor=color + "33", edgecolor=color, linewidth=1.0,
            transform=ax.transAxes, clip_on=False,
        ))
        ax.text(0.09, y - 0.008, f"#{rank}  {named}",
                transform=ax.transAxes, color="white", fontsize=8.5, va="top")
        ax.text(0.09, y - 0.028, f"  {count} regions  ·  ${treasury} treasury",
                transform=ax.transAxes, color="#94a3b8", fontsize=7.5, va="top")
        y -= 0.075

    # Events this turn
    if snap["turn"] > 0:
        events = []
        for r in snap["expanded_regions"]:
            events.append(("expand", r))
        for r in snap["conquered_regions"]:
            events.append(("conquer", r))
        for r in snap["failed_attacks"]:
            events.append(("fail", r))

        if events:
            y -= 0.02
            ax.text(0.05, y, "EVENTS THIS TURN", transform=ax.transAxes,
                    color="#94a3b8", fontsize=8, fontweight="bold", va="top")
            y -= 0.04
            for kind, region in events[:8]:
                icon = {"expand": "→", "conquer": "⚔", "fail": "✗"}.get(kind, "·")
                color_ev = {"expand": "#4ade80", "conquer": "#f87171", "fail": "#94a3b8"}.get(kind, "white")
                ax.text(0.07, y, f"{icon} {region} ({kind})",
                        transform=ax.transAxes, color=color_ev, fontsize=7.5, va="top")
                y -= 0.038

print(f"Rendering {len(snapshots)} frames at {FPS} fps...")

fig = plt.figure(figsize=(14, 8), facecolor="#0d1117")
ax_map  = fig.add_axes([0.02, 0.04, 0.62, 0.92])
ax_side = fig.add_axes([0.66, 0.04, 0.32, 0.92])
ax_map.set_facecolor("#0d1117")

def render_frame(idx):
    snap = snapshots[idx]
    draw_snapshot(ax_map, snap, positions, edges, show_connectivity=True, show_resources=False)
    ax_map.set_facecolor("#0d1117")
    ax_map.title.set_color("white")
    for spine in ax_map.spines.values():
        spine.set_visible(False)
    draw_sidebar(ax_side, snap)

print(f"Saving {OUT_PATH}...")
ani = animation.FuncAnimation(
    fig, render_frame,
    frames=len(snapshots),
    interval=1000 // FPS,
    repeat=False,
)
ani.save(str(OUT_PATH), writer="pillow", fps=FPS, dpi=110)
plt.close(fig)
print(f"Done: {OUT_PATH.resolve()}")
