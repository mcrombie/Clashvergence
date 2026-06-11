import unittest
from unittest.mock import patch

from src.civilization_cycle import (
    PHASE_COMMERCE,
    PHASE_CONQUESTS,
    PHASE_DECLINE,
    PHASE_PIONEERS,
    REVIVAL_SURGE_REQUIRED,
    initialize_rebel_civilization_cycle,
    update_civilization_cycle,
)
from src.metrics import build_turn_metrics
from src.models import Faction, WorldState
from src.simulation_ui import build_simulation_view_model, render_simulation_html
from src.world import create_world


class CivilizationCycleTests(unittest.TestCase):
    def test_prosperity_raises_material_accumulation_and_drains_social_energy(self):
        faction = Faction(
            name="Prosperous",
            treasury=200,
            food_consumption=10.0,
            food_balance=10.0,
            trade_income=30.0,
            material_accumulation=0.10,
            social_energy=0.80,
        )
        world = WorldState(regions={}, factions={faction.name: faction})

        update_civilization_cycle(world)

        self.assertGreater(faction.material_accumulation, 0.10)
        self.assertLess(faction.social_energy, 0.80)

    def test_pioneers_transition_to_conquests_when_conditions_are_met(self):
        faction = Faction(
            name="Frontier",
            civilizational_phase=PHASE_PIONEERS,
            civilizational_phase_turns=7,
            material_accumulation=0.50,
            social_energy=0.80,
            food_consumption=10.0,
            food_balance=2.0,
        )
        world = WorldState(regions={}, factions={faction.name: faction}, turn=12)

        with patch("src.civilization_cycle.random.random", return_value=0.0):
            update_civilization_cycle(world)

        self.assertEqual(faction.civilizational_phase, PHASE_CONQUESTS)
        self.assertEqual(faction.civilizational_phase_turns, 0)
        self.assertEqual(world.events[-1].type, "civilizational_phase_transition")
        self.assertEqual(world.events[-1].details["from"], PHASE_PIONEERS)
        self.assertEqual(world.events[-1].details["to"], PHASE_CONQUESTS)

    def test_overdue_conquests_can_transition_without_high_trade_income(self):
        faction = Faction(
            name="Entrenched",
            civilizational_phase=PHASE_CONQUESTS,
            civilizational_phase_turns=82,
            material_accumulation=0.31,
            social_energy=0.60,
            trade_income=0.0,
        )
        world = WorldState(regions={}, factions={faction.name: faction}, turn=200)

        with patch("src.civilization_cycle.random.random", return_value=0.0):
            update_civilization_cycle(world)

        self.assertEqual(faction.civilizational_phase, PHASE_COMMERCE)
        self.assertEqual(world.events[-1].details["from"], PHASE_CONQUESTS)
        self.assertEqual(world.events[-1].details["to"], PHASE_COMMERCE)

    def test_decline_revival_resets_to_conquests_and_spikes_reform_pressure(self):
        faction = Faction(
            name="Survivors",
            civilizational_phase=PHASE_DECLINE,
            civilizational_phase_turns=7,
            social_energy=0.15,
            religious_vitality=0.70,
            material_accumulation=0.25,
            famine_pressure=0.25,
            epidemic_pressure=0.20,
            shock_exposure=0.20,
            revival_surge_turns=REVIVAL_SURGE_REQUIRED - 1,
        )
        world = WorldState(regions={}, factions={faction.name: faction}, turn=88)

        with patch("src.civilization_cycle.random.random", return_value=0.0):
            update_civilization_cycle(world)

        self.assertEqual(faction.civilizational_phase, PHASE_CONQUESTS)
        self.assertEqual(faction.revival_surge_turns, 0)
        self.assertGreaterEqual(faction.religion.reform_pressure, 0.45)
        self.assertEqual(world.events[-1].details["from"], PHASE_DECLINE)
        self.assertEqual(world.events[-1].details["to"], PHASE_CONQUESTS)

    def test_young_rebels_wait_before_cycle_updates(self):
        faction = Faction(
            name="Rebels",
            is_rebel=True,
            rebel_age=2,
            civilizational_phase_turns=0,
            material_accumulation=0.12,
        )
        world = WorldState(regions={}, factions={faction.name: faction})

        update_civilization_cycle(world)

        self.assertEqual(faction.civilizational_phase_turns, 0)
        self.assertEqual(faction.material_accumulation, 0.12)

    def test_rebel_cycle_initialization_sets_pioneer_profile(self):
        faction = Faction(name="New Rebels")
        initialize_rebel_civilization_cycle(faction)

        self.assertEqual(faction.civilizational_phase, PHASE_PIONEERS)
        self.assertEqual(faction.civilizational_phase_turns, 0)
        self.assertGreaterEqual(faction.social_energy, 0.82)
        self.assertGreaterEqual(faction.religious_vitality, 0.72)

    def test_metrics_view_model_and_html_expose_civilization_cycle(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))

        metrics = build_turn_metrics(world)
        faction_metrics = metrics["factions"][faction_name]
        self.assertIn("civilizational_phase", faction_metrics)
        self.assertIn("social_energy", faction_metrics)
        self.assertIn("religious_vitality", faction_metrics)
        self.assertIn("material_accumulation", faction_metrics)
        self.assertIn("intellectual_activity", faction_metrics)

        view_model = build_simulation_view_model(world)
        faction_payload = next(
            faction
            for faction in view_model["factions"]
            if faction["name"] == faction_name
        )
        self.assertIn("civilizational_phase", faction_payload)
        self.assertIn("revival_surge_turns", faction_payload)

        html = render_simulation_html(world)
        self.assertIn("CIVI_STAGES", html)
        self.assertIn("Civilizational Age", html)
        self.assertIn("stage-indicator", html)


if __name__ == "__main__":
    unittest.main()
