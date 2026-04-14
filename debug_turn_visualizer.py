from __future__ import annotations

import argparse
import copy
import random
from pathlib import Path

from src.factions import get_map_starting_region_counts
from src.map_visualization import (
    build_map_layout,
    get_faction_color,
    get_map_edges,
    natural_sort_key,
)
from src.maps import MAPS
from src.metrics import get_turn_metrics
from src.simulation import run_simulation
from src.world import create_world


DEFAULT_OUTPUT = Path("reports/debug_turn_playback.gif")


def import_matplotlib():
    try:
        import matplotlib.pyplot as plt
        from matplotlib import animation
        from matplotlib.widgets import Button, CheckButtons, Slider
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "This debug visualizer requires matplotlib. "
            "Install it in this environment and rerun, for example: pip install matplotlib pillow"
        ) from exc

    return plt, animation, Button, CheckButtons, Slider


def parse_args():
    parser = argparse.ArgumentParser(
        description="Temporary debug visualizer for stepping through simulation history."
    )
    parser.add_argument("--map", default="thirteen_region_ring", help="Map name to simulate.")
    parser.add_argument("--turns", type=int, default=20, help="Number of turns to simulate.")
    parser.add_argument(
        "--num-factions",
        type=int,
        help="Number of factions to include. Defaults to the number of factions with starting regions on the map.",
    )
    parser.add_argument("--seed", type=int, default=12345, help="Random seed for reproducible playback.")
    parser.add_argument(
        "--hide-connectivity",
        action="store_true",
        help="Start with region connectivity lines hidden.",
    )
    parser.add_argument(
        "--hide-resources",
        action="store_true",
        help="Start with resource labels hidden.",
    )
    parser.add_argument(
        "--save",
        type=Path,
        help="Optional output GIF path. If provided, saves an animated playback instead of opening an interactive window.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=2,
        help="Frames per second for saved animation.",
    )
    return parser.parse_args()


def validate_map(map_name):
    if map_name not in MAPS:
        available_maps = ", ".join(sorted(MAPS))
        raise ValueError(f"Unknown map: {map_name}. Available maps: {available_maps}")


def infer_num_factions(map_name):
    return len(get_map_starting_region_counts(map_name))


def build_snapshot(world, turn_number, regions_state):
    turn_events = [event for event in world.events if event.turn == turn_number - 1]
    newly_claimed = []
    invested_regions = []

    for event in turn_events:
        if event.type == "expand" and event.region is not None:
            regions_state[event.region]["owner"] = event.faction
            newly_claimed.append(event.region)
        elif event.type == "invest" and event.region is not None:
            new_resources = event.impact.get("new_resources", event.new_resources)
            if new_resources is not None:
                regions_state[event.region]["resources"] = new_resources
            invested_regions.append(event.region)

    metrics = get_turn_metrics(world, turn_number)
    return {
        "turn": turn_number,
        "regions": copy.deepcopy(regions_state),
        "newly_claimed": newly_claimed,
        "invested_regions": invested_regions,
        "metrics": metrics,
        "events": turn_events,
    }


def reconstruct_turn_snapshots(world, map_name):
    """Rebuilds ownership/resources turn by turn from initial map state plus event history."""
    map_regions = MAPS[map_name]["regions"]
    regions_state = {
        region_name: {
            "owner": region_data["owner"],
            "resources": region_data["resources"],
            "neighbors": list(region_data["neighbors"]),
        }
        for region_name, region_data in map_regions.items()
    }

    snapshots = [{
        "turn": 0,
        "regions": copy.deepcopy(regions_state),
        "newly_claimed": [],
        "invested_regions": [],
        "metrics": None,
        "events": [],
    }]

    for turn_number in range(1, world.turn + 1):
        snapshots.append(build_snapshot(world, turn_number, regions_state))

    return snapshots


def get_faction_turn_summary(snapshot, faction_name):
    metrics = snapshot["metrics"]["factions"][faction_name]
    faction_events = [event for event in snapshot["events"] if event.faction == faction_name]
    treasury_delta = 0
    event_lines = []
    claims = []
    investments = []

    for event in faction_events:
        treasury_delta += event.get("treasury_change", 0)

        if event.type == "expand" and event.region is not None:
            claims.append(event.region)
            cost = event.get("cost", 0)
            event_lines.append(f"  expand {event.region} (-${cost})")
        elif event.type == "invest" and event.region is not None:
            change = event.get("resource_change", 0)
            new_resources = event.get("new_resources")
            investments.append(event.region)
            if new_resources is not None:
                event_lines.append(f"  invest {event.region} (+{change}R -> R{new_resources})")
            else:
                event_lines.append(f"  invest {event.region} (+{change}R)")
        elif event.type == "income":
            income = event.get("income", 0)
            owned_regions = event.get("owned_regions", 0)
            event_lines.append(f"  income +${income} from {owned_regions} regions")
        elif event.type == "maintenance":
            maintenance = event.get("maintenance", 0)
            owned_regions = event.get("owned_regions", 0)
            event_lines.append(f"  upkeep -${maintenance} on {owned_regions} regions")

    return {
        "treasury": metrics["treasury"],
        "regions": metrics["regions"],
        "treasury_delta": treasury_delta,
        "income": metrics.get("income", 0),
        "maintenance": metrics.get("maintenance", 0),
        "net_income": metrics.get("net_income", 0),
        "expansions": metrics["expansions"],
        "investments": metrics["investments"],
        "claims": claims,
        "invested_regions": investments,
        "event_lines": event_lines,
    }


def format_metrics_text(snapshot):
    faction_names = sorted(
        {
            *(snapshot["metrics"]["factions"].keys() if snapshot["metrics"] is not None else []),
            *{
                region["owner"]
                for region in snapshot["regions"].values()
                if region["owner"] is not None
            },
        },
        key=natural_sort_key,
    )

    if snapshot["metrics"] is None:
        lines = ["Initial state", "", "Ownership Colors"]
        for faction_name in faction_names:
            lines.append(f"{faction_name}: {get_faction_color(faction_name)}")
        lines.append(f"Unclaimed: {get_faction_color(None)}")
        lines.extend(["", "Faction Activity", "No turn events yet."])
        return "\n".join(lines)

    lines = ["Ownership Colors"]
    for faction_name in faction_names:
        lines.append(f"{faction_name}: {get_faction_color(faction_name)}")
    lines.append(f"Unclaimed: {get_faction_color(None)}")
    lines.extend(["", "Faction Activity"])

    for faction_name in sorted(snapshot["metrics"]["factions"]):
        summary = get_faction_turn_summary(snapshot, faction_name)
        delta_prefix = "+" if summary["treasury_delta"] >= 0 else ""
        lines.append("")
        lines.append(
            f"{faction_name}: ${summary['treasury']} "
            f"({delta_prefix}{summary['treasury_delta']} this turn)"
        )
        lines.append(
            f"  regions={summary['regions']} | "
            f"income=+${summary['income']} | "
            f"upkeep=-${summary['maintenance']} | "
            f"net=+${summary['net_income']}"
            if summary["net_income"] >= 0
            else f"  regions={summary['regions']} | "
                 f"income=+${summary['income']} | "
                 f"upkeep=-${summary['maintenance']} | "
                 f"net=${summary['net_income']}"
        )
        lines.append(
            f"  gains: +{summary['expansions']} claim | +{summary['investments']} invest"
        )

        if summary["claims"]:
            lines.append(
                "  claimed: " + ", ".join(sorted(summary["claims"], key=natural_sort_key))
            )
        if summary["invested_regions"]:
            lines.append(
                "  invested: " + ", ".join(sorted(summary["invested_regions"], key=natural_sort_key))
            )
        if summary["event_lines"]:
            lines.append("  events:")
            lines.extend(summary["event_lines"])
        else:
            lines.append("  events: none")

    if snapshot["newly_claimed"] or snapshot["invested_regions"]:
        lines.append("")
        if snapshot["newly_claimed"]:
            lines.append(
                "Map claims: " + ", ".join(sorted(snapshot["newly_claimed"], key=natural_sort_key))
            )
        if snapshot["invested_regions"]:
            lines.append(
                "Map invests: " + ", ".join(sorted(snapshot["invested_regions"], key=natural_sort_key))
            )

    return "\n".join(lines)


def create_debug_world(map_name, num_turns, seed, num_factions):
    random.seed(seed)
    world = create_world(map_name=map_name, num_factions=num_factions)
    return run_simulation(world, num_turns=num_turns, verbose=False)


def draw_snapshot(
    ax,
    snapshot,
    positions,
    edges,
    show_connectivity=True,
    show_resources=True,
):
    ax.clear()
    ax.set_aspect("equal")
    ax.axis("off")

    if show_connectivity:
        for first_name, second_name in edges:
            x1, y1 = positions[first_name]
            x2, y2 = positions[second_name]
            ax.plot(
                [x1, x2],
                [y1, y2],
                color="#b8b2a6",
                linewidth=1.6,
                zorder=1,
            )

    for region_name in sorted(snapshot["regions"], key=natural_sort_key):
        region = snapshot["regions"][region_name]
        x, y = positions[region_name]
        fill = get_faction_color(region["owner"])
        is_new = region_name in snapshot["newly_claimed"]
        is_invested = region_name in snapshot["invested_regions"]

        edge_color = "#222222"
        line_width = 1.2
        if is_new:
            edge_color = "#111827"
            line_width = 3.0
        elif is_invested:
            edge_color = "#30638e"
            line_width = 2.5

        ax.scatter(
            [x],
            [y],
            s=1600,
            c=[fill],
            edgecolors=edge_color,
            linewidths=line_width,
            zorder=3,
        )
        ax.text(
            x,
            y + 10,
            region_name,
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            zorder=4,
        )

        if show_resources:
            ax.text(
                x,
                y - 12,
                f"R{region['resources']}",
                ha="center",
                va="center",
                fontsize=8,
                color="#243b53",
                zorder=4,
            )

    ax.set_title(
        f"Turn {snapshot['turn']}" if snapshot["turn"] > 0 else "Initial State",
        fontsize=16,
        pad=18,
    )


def render_playback(world, map_name, save_path=None, fps=2, show_connectivity=True, show_resources=True):
    plt, animation, Button, CheckButtons, Slider = import_matplotlib()
    snapshots = reconstruct_turn_snapshots(world, map_name)
    positions = build_map_layout(MAPS[map_name]["regions"], width=900, height=900)
    edges = get_map_edges(MAPS[map_name]["regions"])

    fig = plt.figure(figsize=(15, 8.5))
    ax_map = fig.add_axes([0.05, 0.12, 0.60, 0.80])
    ax_side = fig.add_axes([0.68, 0.11, 0.30, 0.74])
    ax_side.axis("off")

    state = {
        "index": 0,
        "show_connectivity": show_connectivity,
        "show_resources": show_resources,
    }

    def redraw():
        snapshot = snapshots[state["index"]]
        draw_snapshot(
            ax_map,
            snapshot,
            positions,
            edges,
            show_connectivity=state["show_connectivity"],
            show_resources=state["show_resources"],
        )
        ax_side.clear()
        ax_side.axis("off")
        ax_side.text(
            0,
            1,
            format_metrics_text(snapshot),
            va="top",
            ha="left",
            fontsize=9.5,
            family="monospace",
        )
        fig.canvas.draw_idle()

    redraw()

    if save_path:
        def frame_update(frame_index):
            state["index"] = frame_index
            snapshot = snapshots[frame_index]
            draw_snapshot(
                ax_map,
                snapshot,
                positions,
                edges,
                show_connectivity=state["show_connectivity"],
                show_resources=state["show_resources"],
            )
            ax_side.clear()
            ax_side.axis("off")
            ax_side.text(
                0,
                1,
                format_metrics_text(snapshot),
                va="top",
                ha="left",
                fontsize=9.5,
                family="monospace",
            )

        anim = animation.FuncAnimation(
            fig,
            frame_update,
            frames=len(snapshots),
            interval=max(1, int(1000 / fps)),
            repeat=False,
        )
        save_path.parent.mkdir(parents=True, exist_ok=True)
        anim.save(save_path, writer="pillow", fps=fps)
        print(f"Saved playback to {save_path}")
        plt.close(fig)
        return

    slider_ax = fig.add_axes([0.10, 0.04, 0.50, 0.03])
    turn_slider = Slider(
        ax=slider_ax,
        label="Turn",
        valmin=0,
        valmax=len(snapshots) - 1,
        valinit=0,
        valstep=1,
    )

    prev_ax = fig.add_axes([0.63, 0.035, 0.07, 0.05])
    next_ax = fig.add_axes([0.71, 0.035, 0.07, 0.05])
    prev_button = Button(prev_ax, "Prev")
    next_button = Button(next_ax, "Next")

    toggle_ax = fig.add_axes([0.81, 0.025, 0.16, 0.09])
    toggles = CheckButtons(
        toggle_ax,
        ["Connectivity", "Resources"],
        [show_connectivity, show_resources],
    )

    def set_index(new_index):
        clamped_index = max(0, min(len(snapshots) - 1, new_index))
        if clamped_index != state["index"]:
            state["index"] = clamped_index
            turn_slider.set_val(clamped_index)
        else:
            redraw()

    def on_slider_change(value):
        state["index"] = int(value)
        redraw()

    def on_prev(_event):
        set_index(state["index"] - 1)

    def on_next(_event):
        set_index(state["index"] + 1)

    def on_key(event):
        if event.key in {"right", "down"}:
            set_index(state["index"] + 1)
        elif event.key in {"left", "up"}:
            set_index(state["index"] - 1)
        elif event.key == "home":
            set_index(0)
        elif event.key == "end":
            set_index(len(snapshots) - 1)

    def on_toggle(_label):
        toggle_states = toggles.get_status()
        state["show_connectivity"] = toggle_states[0]
        state["show_resources"] = toggle_states[1]
        redraw()

    turn_slider.on_changed(on_slider_change)
    prev_button.on_clicked(on_prev)
    next_button.on_clicked(on_next)
    toggles.on_clicked(on_toggle)
    fig.canvas.mpl_connect("key_press_event", on_key)

    plt.show()


def main():
    args = parse_args()
    validate_map(args.map)
    num_factions = args.num_factions or infer_num_factions(args.map)

    world = create_debug_world(args.map, args.turns, args.seed, num_factions=num_factions)
    save_path = args.save if args.save is not None else None
    render_playback(
        world,
        map_name=args.map,
        save_path=save_path,
        fps=args.fps,
        show_connectivity=not args.hide_connectivity,
        show_resources=not args.hide_resources,
    )


if __name__ == "__main__":
    main()
