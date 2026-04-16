import unittest

from src.metrics import analyze_competition_metrics
from src.models import Faction, WorldState


class CompetitionMetricsTests(unittest.TestCase):
    def test_analyze_competition_metrics_detects_runaway_comeback_and_elimination(self):
        world = WorldState(
            regions={},
            factions={
                "FactionA": Faction(name="FactionA", strategy="balanced"),
                "FactionB": Faction(name="FactionB", strategy="opportunist"),
                "FactionC": Faction(name="FactionC", strategy="economic"),
            },
            metrics=[
                {
                    "turn": 1,
                    "factions": {
                        "FactionA": {"treasury": 10, "regions": 3},
                        "FactionB": {"treasury": 8, "regions": 3},
                        "FactionC": {"treasury": 6, "regions": 2},
                    },
                },
                {
                    "turn": 2,
                    "factions": {
                        "FactionA": {"treasury": 9, "regions": 3},
                        "FactionB": {"treasury": 12, "regions": 4},
                        "FactionC": {"treasury": 4, "regions": 1},
                    },
                },
                {
                    "turn": 3,
                    "factions": {
                        "FactionA": {"treasury": 7, "regions": 2},
                        "FactionB": {"treasury": 14, "regions": 4},
                        "FactionC": {"treasury": 1, "regions": 1},
                    },
                },
                {
                    "turn": 4,
                    "factions": {
                        "FactionA": {"treasury": 16, "regions": 4},
                        "FactionB": {"treasury": 15, "regions": 3},
                        "FactionC": {"treasury": 0, "regions": 0},
                    },
                },
                {
                    "turn": 5,
                    "factions": {
                        "FactionA": {"treasury": 20, "regions": 5},
                        "FactionB": {"treasury": 14, "regions": 2},
                        "FactionC": {"treasury": 0, "regions": 0},
                    },
                },
            ],
        )

        analysis = analyze_competition_metrics(world)

        self.assertEqual(analysis["lead_changes"], 2)
        self.assertEqual(analysis["largest_treasury_lead"]["leader"], "FactionB")
        self.assertEqual(analysis["largest_treasury_lead"]["turn"], 3)
        self.assertEqual(analysis["largest_treasury_lead"]["margin"], 7)
        self.assertTrue(analysis["runaway"]["detected"])
        self.assertEqual(analysis["runaway"]["winner"], "FactionA")
        self.assertEqual(analysis["runaway"]["start_turn"], 4)
        self.assertTrue(analysis["comeback"]["detected"])
        self.assertEqual(analysis["comeback"]["winner"], "FactionA")
        self.assertEqual(analysis["comeback"]["midpoint_turn"], 3)
        self.assertEqual(analysis["comeback"]["midpoint_deficit"], 7)
        self.assertEqual(analysis["comeback"]["max_deficit_overcome"], 7)
        self.assertTrue(analysis["eliminations"]["FactionC"]["eliminated"])
        self.assertEqual(analysis["eliminations"]["FactionC"]["turn"], 4)
        self.assertEqual(analysis["eliminated_factions"], 1)


if __name__ == "__main__":
    unittest.main()
