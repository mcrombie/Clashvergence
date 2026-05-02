import unittest
from unittest.mock import patch

from src.actions import attack, develop, get_attack_target_score_components, get_development_target_score_components
from src.heartland import build_region_snapshot
from src.metrics import build_turn_metrics
from src.military import (
    PROJECT_BUILD_FORTIFICATIONS,
    PROJECT_BUILD_LOGISTICS_NODE,
    PROJECT_BUILD_NAVAL_BASE,
    PROJECT_RAISE_GARRISON,
    get_region_fortification_defense_bonus,
    refresh_military_state,
)
from src.models import Faction, Region, WorldState
from src.resource_economy import update_faction_resource_economy
from src.resources import RESOURCE_GRAIN, seed_region_resource_profile
from src.technology import TECH_COPPER_WORKING, TECH_ORGANIZED_LEVIES, TECH_ROAD_ADMINISTRATION


class MilitaryInstitutionTests(unittest.TestCase):
    def _border_world(self) -> WorldState:
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=320,
                    terrain_tags=["plains", "coast"],
                    climate="temperate",
                    settlement_level="town",
                    infrastructure_level=1.0,
                    road_level=0.8,
                    storehouse_level=0.6,
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=3,
                    population=260,
                    terrain_tags=["plains", "coast"],
                    climate="temperate",
                    settlement_level="town",
                    infrastructure_level=0.9,
                    road_level=0.5,
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    trade_gateway_role="sea_gateway",
                    trade_throughput=4.0,
                    trade_foreign_flow=2.0,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=20),
                "FactionB": Faction(name="FactionB", treasury=14),
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
            region.resource_established[RESOURCE_GRAIN] = 0.7
        update_faction_resource_economy(world)
        refresh_military_state(world)
        return world

    def test_fortifications_and_garrisons_raise_defense_and_reduce_success(self):
        world = self._border_world()
        baseline = get_attack_target_score_components("B", "FactionA", world)

        target = world.regions["B"]
        target.fortification_level = 1.35
        target.garrison_strength = 1.2
        fortified = get_attack_target_score_components("B", "FactionA", world)

        self.assertGreater(get_region_fortification_defense_bonus(target, world), 0)
        self.assertGreater(fortified["defender_strength"], baseline["defender_strength"])
        self.assertLess(fortified["success_chance"], baseline["success_chance"])
        self.assertGreater(fortified["fortification_defense_bonus"], 0)

    def test_logistics_quality_and_reforms_raise_attack_profile(self):
        baseline_world = self._border_world()
        baseline = get_attack_target_score_components("B", "FactionA", baseline_world)

        improved_world = self._border_world()
        attacker = improved_world.factions["FactionA"]
        attacker.institutional_technologies[TECH_ORGANIZED_LEVIES] = 0.85
        attacker.institutional_technologies[TECH_COPPER_WORKING] = 0.65
        attacker.institutional_technologies[TECH_ROAD_ADMINISTRATION] = 0.75
        attacker.military_tradition = 0.5
        improved_world.regions["A"].logistics_node_level = 1.5
        improved_world.regions["A"].road_level = 1.5
        refresh_military_state(improved_world)
        improved = get_attack_target_score_components("B", "FactionA", improved_world)

        self.assertGreater(improved["military_attack_bonus"], baseline["military_attack_bonus"])
        self.assertGreater(improved["attacker_army_quality"], baseline["attacker_army_quality"])
        self.assertGreater(improved["attacker_logistics"], baseline["attacker_logistics"])

    def test_battle_losses_reduce_manpower_and_are_recorded_on_attack(self):
        world = self._border_world()
        refresh_military_state(world)
        attacker_before = world.factions["FactionA"].manpower_pool
        defender_before = world.factions["FactionB"].manpower_pool

        with patch("src.actions.random.random", return_value=0.0):
            succeeded = attack("FactionA", "B", world)

        self.assertTrue(succeeded)
        self.assertLess(world.factions["FactionA"].manpower_pool, attacker_before)
        self.assertLess(world.factions["FactionB"].manpower_pool, defender_before)
        attack_event = next(event for event in world.events if event.type == "attack")
        self.assertGreater(attack_event.get("attacker_manpower_loss", 0.0), 0.0)
        self.assertGreater(attack_event.get("defender_manpower_loss", 0.0), 0.0)
        self.assertTrue(any(event.type == "military_battle_losses" for event in world.events))

    def test_naval_bases_support_maritime_attacks_and_blockades(self):
        world = self._border_world()
        world.regions["A"].naval_base_level = 1.4
        refresh_military_state(world)
        score = get_attack_target_score_components("B", "FactionA", world)

        self.assertTrue(score["naval_operation"])
        self.assertGreater(score["attacker_naval_power"], 0.0)
        self.assertGreater(score["naval_attack_bonus"], 0.0)

        with patch("src.actions.random.random", return_value=0.0):
            attack("FactionA", "B", world)
        attack_event = next(event for event in world.events if event.type == "attack")
        self.assertGreater(attack_event.get("trade_blockade_added", 0.0), 0.0)
        self.assertTrue(attack_event.get("naval_operation", False))

    def test_development_can_build_durable_military_projects(self):
        world = self._border_world()
        region = world.regions["A"]
        region.infrastructure_level = 1.8
        region.road_level = 1.8
        region.storehouse_level = 1.8
        region.granary_level = 1.8
        region.market_level = 1.8
        region.irrigation_level = 1.8
        region.pasture_level = 1.8
        region.logging_camp_level = 1.8
        region.copper_mine_level = 1.8
        region.stone_quarry_level = 1.8
        region.agriculture_level = 1.8
        region.pastoral_level = 1.8
        region.extractive_level = 1.8
        score = get_development_target_score_components("A", "FactionA", world)

        self.assertIn(
            score["project_type"],
            {
                PROJECT_BUILD_FORTIFICATIONS,
                PROJECT_RAISE_GARRISON,
                PROJECT_BUILD_LOGISTICS_NODE,
                PROJECT_BUILD_NAVAL_BASE,
            },
        )
        self.assertTrue(develop("FactionA", "A", world))
        self.assertTrue(
            region.fortification_level > 0.0
            or region.garrison_strength > 0.0
            or region.logistics_node_level > 0.0
            or region.naval_base_level > 0.0
        )

    def test_metrics_and_region_snapshots_expose_military_state(self):
        world = self._border_world()
        world.regions["A"].fortification_level = 0.8
        world.regions["A"].garrison_strength = 0.6
        world.regions["A"].logistics_node_level = 0.9
        world.regions["A"].naval_base_level = 0.7
        refresh_military_state(world)

        metrics = build_turn_metrics(world)["factions"]["FactionA"]
        snapshot = build_region_snapshot(world)["A"]

        self.assertIn("standing_forces", metrics)
        self.assertIn("manpower_capacity", metrics)
        self.assertIn("army_quality", metrics)
        self.assertIn("logistics_capacity", metrics)
        self.assertIn("naval_power", metrics)
        self.assertGreater(metrics["standing_forces"], 0.0)
        self.assertEqual(snapshot["fortification_level"], 0.8)
        self.assertEqual(snapshot["garrison_strength"], 0.6)
        self.assertEqual(snapshot["logistics_node_level"], 0.9)
        self.assertEqual(snapshot["naval_base_level"], 0.7)


if __name__ == "__main__":
    unittest.main()
