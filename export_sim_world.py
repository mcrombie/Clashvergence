"""Convert a saved world_state.json to sim_world.json (SimWorldState format for the web viewer).

Usage:
    python export_sim_world.py [world_state.json] [sim_world.json]

Defaults:
    world_state.json = reports/runs/azhora_sc4_live/world_state.json
    sim_world.json   = reports/runs/azhora_sc4_live/sim_world.json
"""
import json
import sys
from pathlib import Path

from src.world_serialization import deserialize_world
from src.player_view import build_world_builder_snapshot

INPUT_DEFAULT  = Path("reports/runs/azhora_sc4_live/world_state.json")
OUTPUT_DEFAULT = Path("reports/runs/azhora_sc4_live/sim_world.json")


def main() -> None:
    input_path  = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_DEFAULT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_DEFAULT

    if not input_path.exists():
        raise SystemExit(f"Error: input file not found: {input_path}")

    with open(input_path, encoding="utf-8") as f:
        world_data = json.load(f)

    world = deserialize_world(world_data)
    snapshot = build_world_builder_snapshot(world)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, separators=(",", ":"))

    print(f"sim_world.json written to {output_path} (turn {snapshot.get('turn')})")


if __name__ == "__main__":
    main()
