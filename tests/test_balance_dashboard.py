import unittest

from experiments.experiment_balance_dashboard import (
    build_phase_action_counts,
    build_system_activity,
    format_setting_report,
)
from src.models import Event, Faction, WorldState


class BalanceDashboardObservationTests(unittest.TestCase):
    def test_phase_action_counts_include_develop_events(self):
        world = WorldState(
            regions={},
            factions={"FactionA": Faction(name="FactionA")},
            metrics=[
                {"turn": 1, "factions": {}},
                {"turn": 2, "factions": {}},
                {"turn": 3, "factions": {}},
            ],
            events=[
                Event(turn=0, type="develop", faction="FactionA"),
                Event(turn=1, type="invest", faction="FactionA"),
                Event(turn=2, type="expand", faction="FactionA"),
            ],
        )

        phase_counts = build_phase_action_counts(world)

        total_investments = sum(phase["investments"] for phase in phase_counts.values())
        total_expansions = sum(phase["expansions"] for phase in phase_counts.values())
        self.assertEqual(total_investments, 2)
        self.assertEqual(total_expansions, 1)

    def test_system_activity_combines_events_and_metric_signals(self):
        world = WorldState(
            regions={},
            factions={"FactionA": Faction(name="FactionA")},
            events=[
                Event(turn=0, type="expand", faction="FactionA"),
                Event(turn=1, type="religious_reform", faction="FactionA"),
                Event(
                    turn=2,
                    type="attack",
                    faction="FactionA",
                    details={"trade_warfare_hit": True},
                ),
            ],
            metrics=[
                {
                    "turn": 1,
                    "factions": {
                        "FactionA": {
                            "trade_income": 1.0,
                            "administrative_overextension": 0.2,
                            "food_deficit": 0.0,
                        }
                    },
                },
                {
                    "turn": 2,
                    "factions": {
                        "FactionA": {
                            "migration_inflow": 20,
                            "claimant_pressure": 0.35,
                            "food_shortage": 0.4,
                        }
                    },
                },
            ],
        )

        activity = build_system_activity(world)

        self.assertTrue(activity["expansion"]["active"])
        self.assertEqual(activity["expansion"]["event_count"], 1)
        self.assertTrue(activity["religion"]["active"])
        self.assertTrue(activity["trade_disruption"]["active"])
        self.assertTrue(activity["trade_economy"]["active"])
        self.assertTrue(activity["administration"]["active"])
        self.assertTrue(activity["migration"]["active"])
        self.assertTrue(activity["succession"]["active"])
        self.assertTrue(activity["food_stress"]["active"])
        self.assertEqual(activity["trade_economy"]["first_turn"], 1)

    def test_setting_report_includes_system_activity_section(self):
        result = {
            "map_name": "test_map",
            "num_turns": 4,
            "runs": 1,
            "factions": ["FactionA"],
            "doctrines": {"FactionA": "Adaptive Plains"},
            "outcome_balance": {
                "outright_win_rate": {"FactionA": 1.0},
                "shared_first_rate": {"FactionA": 0.0},
                "non_starting_outright_win_rate": 0.0,
                "non_starting_shared_first_rate": 0.0,
                "average_treasury": {"FactionA": 3.0},
                "average_regions": {"FactionA": 2.0},
                "win_rate_spread": 0.0,
                "win_rate_stddev": 0.0,
            },
            "game_health": {
                "average_lead_changes": 0.0,
                "runaway_rate": 0.0,
                "average_runaway_turn": None,
                "comeback_rate": 0.0,
                "average_comeback_deficit": 0.0,
                "average_eliminated_factions": 0.0,
                "average_largest_treasury_lead": 0.0,
                "average_largest_region_lead": 0.0,
                "average_final_factions": 1.0,
            },
            "survival": {
                "elimination_rate": {"FactionA": 0.0},
                "average_elimination_turn": {"FactionA": None},
            },
            "pacing": {
                "early": {
                    "attacks": 0.0,
                    "successful_attacks": 0.0,
                    "expansions": 1.0,
                    "investments": 1.0,
                }
            },
            "diplomacy": {
                "truces": 0.0,
                "truce_ends": 0.0,
                "pacts": 0.0,
                "alliances": 0.0,
                "rivalries": 0.0,
                "breaks": 0.0,
                "secessions": 0.0,
                "independence": 0.0,
            },
            "system_activity": {
                "expansion": {
                    "label": "Expansion",
                    "average_events": 1.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 1.0,
                    "dead_run_rate": 0.0,
                    "average_first_turn": 1.0,
                    "status": "active",
                },
                "war": {
                    "label": "War",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "development": {
                    "label": "Development",
                    "average_events": 1.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 1.0,
                    "dead_run_rate": 0.0,
                    "average_first_turn": 1.0,
                    "status": "active",
                },
                "polity": {
                    "label": "Polity Advancement",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "diplomacy": {
                    "label": "Diplomacy",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "trade_economy": {
                    "label": "Trade Economy",
                    "average_events": 0.0,
                    "average_metric_signals": 1.0,
                    "active_rate": 1.0,
                    "dead_run_rate": 0.0,
                    "average_first_turn": 1.0,
                    "status": "active",
                },
                "trade_disruption": {
                    "label": "Trade Disruption",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "administration": {
                    "label": "Administration",
                    "average_events": 0.0,
                    "average_metric_signals": 1.0,
                    "active_rate": 1.0,
                    "dead_run_rate": 0.0,
                    "average_first_turn": 2.0,
                    "status": "active",
                },
                "unrest": {
                    "label": "Unrest",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "rebellion": {
                    "label": "Rebellion",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "migration": {
                    "label": "Migration",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "religion": {
                    "label": "Religion",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "succession": {
                    "label": "Succession",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
                "food_stress": {
                    "label": "Food Stress",
                    "average_events": 0.0,
                    "average_metric_signals": 0.0,
                    "active_rate": 0.0,
                    "dead_run_rate": 1.0,
                    "average_first_turn": None,
                    "status": "dead",
                },
            },
        }

        report = format_setting_report(result)

        self.assertIn("System Activity", report)
        self.assertIn("Expansion", report)
        self.assertIn("Dead or near-silent systems", report)
        self.assertIn("War", report)


if __name__ == "__main__":
    unittest.main()
