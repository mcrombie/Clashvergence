import unittest
from unittest.mock import patch

from src.actions import attack, get_attack_target_score_components
from src.heartland import (
    CORE_INTEGRATION_SCORE,
    get_region_attack_projection_modifier,
    get_region_core_status,
    get_region_effective_income,
    get_region_maintenance_cost,
    update_region_integration,
)
from src.metrics import build_turn_metrics
from src.simulation import get_faction_economy_snapshot
from src.world import create_world


class HeartlandSystemTests(unittest.TestCase):
    def test_world_initializes_homeland_and_core_regions(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)

        for faction_name in world.factions:
            owned = [region for region in world.regions.values() if region.owner == faction_name]
            homeland_regions = [region for region in owned if region.core_status == "homeland"]
            self.assertEqual(len(homeland_regions), 1)
            for region in homeland_regions:
                self.assertEqual(region.homeland_faction_id, faction_name)
            for region in owned:
                self.assertIn(region.core_status, {"homeland", "core"})

    def test_conquered_region_resets_to_frontier(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        for faction in world.factions.values():
            faction.treasury = 1
        world.factions[attacker_name].treasury = 10

        target_region_name = "B"
        target_region = world.regions[target_region_name]
        target_region.owner = defender_name
        target_region.integrated_owner = defender_name
        target_region.integration_score = 6.0
        target_region.core_status = "core"
        target_region.ownership_turns = 3

        with patch("src.actions.random.random", return_value=0.0):
            succeeded = attack(attacker_name, target_region_name, world)

        self.assertTrue(succeeded)
        self.assertEqual(target_region.owner, attacker_name)
        self.assertEqual(target_region.core_status, "frontier")
        self.assertEqual(target_region.integration_score, 1.0)
        self.assertEqual(target_region.conquest_count, 1)

    def test_frontier_region_promotes_to_core_after_long_hold(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.integration_score = 1.0
        region.core_status = "frontier"
        region.ownership_turns = 1

        for _ in range(5):
            update_region_integration(world)

        self.assertGreaterEqual(region.integration_score, CORE_INTEGRATION_SCORE)
        self.assertEqual(get_region_core_status(region), "core")

    def test_attack_score_gets_extra_defense_for_homeland(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 6
        world.factions[defender_name].treasury = 6

        homeland_region = next(
            region.name
            for region in world.regions.values()
            if region.owner == defender_name and region.core_status == "homeland"
        )
        target = world.regions[homeland_region]
        plains_region = world.regions["M"]
        plains_region.owner = defender_name
        plains_region.integrated_owner = defender_name
        plains_region.core_status = "frontier"
        plains_region.integration_score = 1.0

        homeland_score = get_attack_target_score_components(homeland_region, attacker_name, world)
        frontier_score = get_attack_target_score_components("M", attacker_name, world)

        self.assertGreater(homeland_score["core_defense_bonus"], frontier_score["core_defense_bonus"])
        self.assertGreater(homeland_score["defender_strength"], frontier_score["defender_strength"])

    def test_metrics_include_homeland_core_and_frontier_counts(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        world.regions["M"].owner = faction_name
        world.regions["M"].integrated_owner = faction_name
        world.regions["M"].core_status = "frontier"
        world.regions["M"].integration_score = 1.0

        metrics = build_turn_metrics(world)
        faction_metrics = metrics["factions"][faction_name]

        self.assertIn("homeland_regions", faction_metrics)
        self.assertIn("core_regions", faction_metrics)
        self.assertIn("frontier_regions", faction_metrics)
        self.assertGreaterEqual(faction_metrics["homeland_regions"], 1)
        self.assertGreaterEqual(faction_metrics["frontier_regions"], 1)

    def test_frontier_friction_reduces_income_and_attack_projection(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        homeland_region = next(
            region
            for region in world.regions.values()
            if region.owner == faction_name and region.core_status == "homeland"
        )
        frontier_region = world.regions["M"]
        frontier_region.owner = faction_name
        frontier_region.integrated_owner = faction_name
        frontier_region.core_status = "frontier"
        frontier_region.integration_score = 1.0
        frontier_region.resources = 5

        self.assertEqual(get_region_effective_income(homeland_region), homeland_region.resources)
        self.assertEqual(get_region_effective_income(frontier_region), 3)
        self.assertEqual(get_region_maintenance_cost(homeland_region), 1)
        self.assertEqual(get_region_maintenance_cost(frontier_region), 2)
        self.assertEqual(get_region_attack_projection_modifier(frontier_region), -1)

        economy = get_faction_economy_snapshot(world)[faction_name]

        self.assertEqual(
            economy["nominal_income"],
            homeland_region.resources + frontier_region.resources,
        )
        self.assertEqual(
            economy["base_income"],
            homeland_region.resources + 3,
        )
        self.assertEqual(economy["maintenance"], 3)


if __name__ == "__main__":
    unittest.main()
