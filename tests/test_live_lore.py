import json
import shutil
import unittest
from pathlib import Path

from src.live_lore import write_live_lore
from src.simulation import run_simulation
from src.world import create_world


class LiveLoreTests(unittest.TestCase):
    def test_run_simulation_invokes_turn_callback_after_each_completed_turn(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="live-lore-callback")
        completed_turns = []

        run_simulation(
            world,
            num_turns=2,
            verbose=False,
            turn_callback=lambda current_world: completed_turns.append(current_world.turn),
        )

        self.assertEqual(completed_turns, [1, 2])

    def test_write_live_lore_outputs_refreshing_html_and_json_state(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="live-lore-output")
        run_simulation(world, num_turns=1, verbose=False)
        tmp_dir = Path("tests/.tmp_live_lore")
        output_path = tmp_dir / "live_lore.html"

        try:
            written_path = write_live_lore(
                world,
                map_name="thirteen_region_ring",
                total_turns=4,
                status="running",
                output_path=output_path,
            )
            html = written_path.read_text(encoding="utf-8")
            state = json.loads(written_path.with_suffix(".json").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        self.assertIn("Simulation Chronicle", html)
        self.assertIn('http-equiv="refresh"', html)
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["completed_turns"], 1)
        self.assertEqual(state["total_turns"], 4)
        self.assertGreater(state["progress_percent"], 0)
        self.assertTrue(state["recent_events"])


if __name__ == "__main__":
    unittest.main()
