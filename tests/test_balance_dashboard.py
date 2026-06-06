import unittest

from experiments.experiment_balance_dashboard import (
    build_action_incentive_diagnostics,
    build_dual_track_observability,
    build_phase_action_counts,
    build_pressure_diagnostics,
    build_system_activity,
    format_setting_report,
)
from src.models import Event, Faction, RelationshipState, ShockState, WarState, WorldState


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

    def test_dual_track_observability_aggregates_metric_rows(self):
        world = WorldState(
            regions={},
            factions={"FactionA": Faction(name="FactionA")},
            metrics=[
                {
                    "turn": 1,
                    "factions": {
                        "FactionA": {
                            "regions": 5,
                            "attacks": 1,
                            "expansions": 0,
                            "military_track_used": True,
                            "admin_track_used": True,
                            "dual_track_qualified": True,
                            "dual_track_both_tracks_used": True,
                            "bloc_action_bias_abs": 0.08,
                            "dominant_bloc_track": "military",
                        }
                    },
                },
                {
                    "turn": 2,
                    "factions": {
                        "FactionA": {
                            "regions": 2,
                            "attacks": 0,
                            "expansions": 0,
                            "military_track_used": False,
                            "admin_track_used": True,
                            "dual_track_qualified": False,
                            "dual_track_both_tracks_used": False,
                            "bloc_action_bias_abs": 0.04,
                            "dominant_bloc_track": "admin",
                        }
                    },
                },
            ],
        )

        observability = build_dual_track_observability(world)

        self.assertEqual(observability["qualifying_turns"], 1)
        self.assertEqual(observability["both_track_turns"], 1)
        self.assertEqual(observability["dual_track_activation_rate"], 1.0)
        self.assertAlmostEqual(observability["bloc_competition_delta"], 0.06)
        self.assertEqual(observability["dominant_bloc_action_alignment"], 1.0)
        self.assertEqual(
            observability["track_split_by_faction_size"]["4-7"]["admin_track_rate"],
            1.0,
        )

    def test_action_incentive_diagnostics_aggregate_candidates(self):
        diagnostics = build_action_incentive_diagnostics([
            {
                "turn": 1,
                "faction": "FactionA",
                "dual_track_qualified": True,
                "selected_actions": [
                    {"action": "attack", "target": "RegionB"},
                    {"action": "develop", "target": "RegionA"},
                ],
                "utilities": {
                    "attack": 0.72,
                    "expand": 0.31,
                    "develop": 0.42,
                },
                "targets": {
                    "attack": "RegionB",
                    "expand": "RegionC",
                    "develop": "RegionA",
                },
                "components": {
                    "attack": {
                        "score": 61,
                        "success_chance": 0.64,
                        "active_war_bonus": 8,
                        "supply_risk": 0.2,
                        "manpower_commitment": 3.0,
                        "attacker_readiness": 0.75,
                        "resource_need_bonus": 2,
                        "trade_chokepoint_bonus": 1,
                        "foreign_gateway_bonus": 0,
                        "diplomacy_status": "rival",
                    },
                    "expand": {"score": 14},
                    "develop": {"score": 8},
                },
                "pressures": {
                    "frontier_pressure": 0.18,
                    "acute_development_need": 0.36,
                },
                "bloc_biases": {
                    "attack": 0.05,
                    "expand": -0.02,
                    "develop": 0.03,
                },
                "dominant_admin_agenda": "food",
                "resource_shortages": {
                    "food_security": 0.4,
                    "mobility_capacity": 0.1,
                    "metal_capacity": 0.0,
                },
            }
        ])

        self.assertEqual(diagnostics["total_faction_turns"], 1)
        self.assertEqual(diagnostics["selected_action_counts"]["attack"], 1)
        self.assertEqual(diagnostics["selected_action_counts"]["develop"], 1)
        self.assertEqual(diagnostics["best_utility_selection_rate"], 1.0)
        self.assertAlmostEqual(
            diagnostics["attack_candidate"]["average_success_chance"],
            0.64,
        )
        self.assertAlmostEqual(
            diagnostics["develop_candidate"]["average_acute_development_need"],
            0.36,
        )

    def test_pressure_diagnostics_capture_runaway_war_and_shock_pressure(self):
        world = WorldState(
            regions={},
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
            relationships={
                ("FactionA", "FactionB"): RelationshipState(status="rival"),
            },
            wars={
                ("FactionA", "FactionB"): WarState(
                    active=True,
                    aggressor="FactionA",
                    defender="FactionB",
                    war_exhaustion=0.45,
                ),
            },
            shock_history=[
                ShockState(
                    id="shock-1",
                    kind="famine",
                    affected_regions=["RegionA", "RegionB"],
                    duration_turns=3,
                    intensity=0.6,
                ),
            ],
            metrics=[
                {
                    "turn": 1,
                    "factions": {
                        "FactionA": {
                            "treasury": 10,
                            "regions": 2,
                            "population": 100,
                            "effective_income": 2,
                            "net_income": 1,
                            "force_projection": 1.0,
                            "manpower_pool": 4.0,
                            "manpower_capacity": 8.0,
                            "military_readiness": 0.55,
                            "administrative_efficiency": 0.95,
                            "administrative_reach": 0.9,
                            "administrative_overextension": 0.0,
                            "shock_exposure": 0.0,
                            "shock_resilience": 0.35,
                            "average_institutional_technology": 0.08,
                            "dual_track_qualified": False,
                            "dual_track_both_tracks_used": False,
                            "military_track_used": True,
                            "admin_track_used": False,
                            "bloc_action_bias_abs": 0.04,
                            "attacks": 0,
                            "expansions": 1,
                        },
                        "FactionB": {
                            "treasury": 12,
                            "regions": 2,
                            "population": 90,
                            "effective_income": 1,
                            "net_income": 1,
                            "force_projection": 1.0,
                            "manpower_pool": 3.0,
                            "manpower_capacity": 7.0,
                            "military_readiness": 0.45,
                            "administrative_efficiency": 0.98,
                            "administrative_reach": 0.9,
                            "administrative_overextension": 0.0,
                            "shock_exposure": 0.0,
                            "shock_resilience": 0.25,
                            "average_institutional_technology": 0.05,
                            "dual_track_qualified": False,
                            "dual_track_both_tracks_used": False,
                            "military_track_used": False,
                            "admin_track_used": True,
                            "bloc_action_bias_abs": 0.02,
                            "attacks": 0,
                            "expansions": 0,
                        },
                    },
                },
                {
                    "turn": 2,
                    "factions": {
                        "FactionA": {
                            "treasury": 30,
                            "regions": 4,
                            "population": 140,
                            "effective_income": 5,
                            "net_income": 3,
                            "force_projection": 4.0,
                            "manpower_pool": 8.0,
                            "manpower_capacity": 10.0,
                            "military_readiness": 0.72,
                            "administrative_efficiency": 0.9,
                            "administrative_reach": 0.84,
                            "administrative_overextension": 0.15,
                            "shock_exposure": 0.1,
                            "famine_pressure": 0.08,
                            "shock_resilience": 0.5,
                            "average_institutional_technology": 0.16,
                            "dual_track_qualified": True,
                            "dual_track_both_tracks_used": True,
                            "military_track_used": True,
                            "admin_track_used": True,
                            "bloc_action_bias_abs": 0.08,
                            "attacks": 1,
                            "expansions": 0,
                            "developments": 1,
                            "food_deficit": 0.2,
                            "migration_outflow": 5,
                            "net_income": 3,
                        },
                        "FactionB": {
                            "treasury": 20,
                            "regions": 2,
                            "population": 90,
                            "effective_income": 2,
                            "net_income": 1,
                            "force_projection": 2.0,
                            "manpower_pool": 4.0,
                            "manpower_capacity": 8.0,
                            "military_readiness": 0.5,
                            "administrative_efficiency": 0.96,
                            "administrative_reach": 0.9,
                            "administrative_overextension": 0.0,
                            "shock_exposure": 0.0,
                            "shock_resilience": 0.3,
                            "average_institutional_technology": 0.08,
                            "dual_track_qualified": False,
                            "dual_track_both_tracks_used": False,
                            "military_track_used": False,
                            "admin_track_used": True,
                            "bloc_action_bias_abs": 0.02,
                            "attacks": 0,
                            "expansions": 0,
                            "developments": 0,
                        },
                    },
                },
            ],
            events=[
                Event(
                    turn=1,
                    type="attack",
                    faction="FactionA",
                    region="RegionB",
                    details={
                        "success": True,
                        "defender": "FactionB",
                        "diplomacy_status": "rival",
                        "active_war_bonus": 8,
                        "active_war_objective": True,
                        "score": 41,
                        "success_chance": 0.32,
                        "supply_risk": 0.25,
                        "attacker_readiness": 0.72,
                        "manpower_commitment": 3.0,
                        "attacker_manpower": 8.0,
                        "target_taxable_value": 5.0,
                    },
                ),
                Event(turn=1, type="shock_famine", faction="FactionA"),
                Event(
                    turn=1,
                    type="shock_population_loss",
                    faction="FactionA",
                    details={"population_loss": 14},
                ),
                Event(turn=1, type="shock_recovery", faction="FactionA"),
            ],
        )
        competition = {
            "runaway": {
                "detected": True,
                "winner": "FactionA",
                "start_turn": 2,
            }
        }
        action_diagnostics = [
            {
                "turn": 2,
                "faction": "FactionA",
                "dual_track_qualified": True,
                "selected_actions": [{"action": "attack", "target": "RegionB"}],
                "utilities": {
                    "attack": 0.7,
                    "expand": 0.2,
                    "develop": 0.3,
                },
                "targets": {
                    "attack": "RegionB",
                    "expand": "RegionC",
                    "develop": "RegionA",
                },
                "components": {
                    "attack": {
                        "score": 41,
                        "success_chance": 0.32,
                        "active_war_bonus": 8,
                    },
                    "expand": {"score": 13},
                    "develop": {"score": 7},
                },
                "pressures": {
                    "frontier_pressure": 0.1,
                    "acute_development_need": 0.2,
                },
                "bloc_biases": {
                    "attack": 0.02,
                    "expand": 0.0,
                    "develop": 0.01,
                },
                "resource_shortages": {
                    "food_security": 0.2,
                    "mobility_capacity": 0.0,
                    "metal_capacity": 0.0,
                },
            },
        ]

        diagnostics = build_pressure_diagnostics(
            world,
            competition=competition,
            action_diagnostics=action_diagnostics,
        )

        self.assertEqual(diagnostics["runaway"]["winner"], "FactionA")
        self.assertGreater(diagnostics["runaway"]["average_treasury_margin"], 0)
        self.assertEqual(
            diagnostics["relationship_pressure"]["active_war_count"],
            1,
        )
        late_attacks = sum(
            phase["attacks"]
            for phase in diagnostics["late_war_cadence"].values()
        )
        self.assertEqual(late_attacks, 1)
        self.assertEqual(
            diagnostics["shock_volume"]["total_population_loss"],
            14,
        )
        self.assertEqual(
            diagnostics["action_incentives"]["selected_action_counts"]["attack"],
            1,
        )

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
        self.assertIn("Dual-Track Actions", report)
        self.assertIn("Pressure Diagnostics", report)
        self.assertIn("Runaway margins", report)
        self.assertIn("Shock volume", report)
        self.assertIn("Expansion", report)
        self.assertIn("Dead or near-silent systems", report)
        self.assertIn("War", report)


if __name__ == "__main__":
    unittest.main()
