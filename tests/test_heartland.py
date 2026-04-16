import unittest
from unittest.mock import patch

from src.config import (
    MIN_TREASURY_CONCENTRATION,
    REBEL_FULL_INDEPENDENCE_THRESHOLD,
    REBEL_INDEPENDENCE_TREASURY_BONUS,
    REBEL_MATURE_GOVERNMENT_TYPE,
    UNREST_SECESSION_CRISIS_TURNS,
)
from src.actions import (
    attack,
    get_attack_target_score_components,
    get_treasury_concentration_multiplier,
)
from src.heartland import (
    CORE_INTEGRATION_SCORE,
    get_rebel_reclaim_bonus,
    get_region_attack_projection_modifier,
    get_region_core_status,
    get_region_effective_income,
    get_region_maintenance_cost,
    resolve_unrest_events,
    update_rebel_faction_status,
    update_region_integration,
)
from src.metrics import build_turn_metrics
from src.simulation import get_faction_economy_snapshot
from src.world import create_world


class HeartlandSystemTests(unittest.TestCase):
    def _spawn_rebel_from_region(self, world, faction_name, region_name="M"):
        region = world.regions[region_name]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.core_status = "frontier"
        region.integration_score = 1.0
        region.unrest = 9.5

        for crisis_turn in range(UNREST_SECESSION_CRISIS_TURNS):
            resolve_unrest_events(world)
            update_region_integration(world)
            if crisis_turn < UNREST_SECESSION_CRISIS_TURNS - 1:
                region.unrest = 9.5

        return region.owner, region

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
        self.assertGreater(target_region.unrest, 0.0)

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

        self.assertEqual(get_region_effective_income(homeland_region, world), homeland_region.resources)
        self.assertEqual(get_region_effective_income(frontier_region, world), 3)
        self.assertEqual(get_region_maintenance_cost(homeland_region, world), 1)
        self.assertEqual(get_region_maintenance_cost(frontier_region, world), 2)
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

    def test_unrest_reduces_income_and_increases_maintenance(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.core_status = "frontier"
        region.integration_score = 1.0
        region.resources = 5

        region.unrest = 0.0
        calm_income = get_region_effective_income(region, world)
        calm_maintenance = get_region_maintenance_cost(region, world)

        region.unrest = 8.0
        unstable_income = get_region_effective_income(region, world)
        unstable_maintenance = get_region_maintenance_cost(region, world)

        self.assertLess(unstable_income, calm_income)
        self.assertGreater(unstable_maintenance, calm_maintenance)

    def test_unrest_reduces_attack_projection(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.core_status = "frontier"
        region.integration_score = 1.0
        region.climate = world.factions[faction_name].doctrine_state.homeland_climate

        region.unrest = 0.0
        calm_projection = get_region_attack_projection_modifier(
            region,
            world=world,
            faction_name=faction_name,
        )

        region.unrest = 8.0
        unstable_projection = get_region_attack_projection_modifier(
            region,
            world=world,
            faction_name=faction_name,
        )

        self.assertLess(unstable_projection, calm_projection)

    def test_homeland_unrest_decays_toward_zero(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        homeland_region = next(
            region
            for region in world.regions.values()
            if region.owner == faction_name and region.core_status == "homeland"
        )
        homeland_region.unrest = 3.0

        update_region_integration(world)

        self.assertLess(homeland_region.unrest, 3.0)

    def test_moderate_unrest_triggers_disturbance_event_without_stalling_integration(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.core_status = "frontier"
        region.integration_score = 2.0
        region.unrest = 5.0
        treasury_before = world.factions[faction_name].treasury

        resolve_unrest_events(world)

        self.assertEqual(region.unrest_event_level, "disturbance")
        self.assertEqual(region.unrest_event_turns_remaining, 1)
        self.assertEqual(world.events[-1].type, "unrest_disturbance")
        self.assertEqual(world.events[-1].impact["integration_stalled"], False)
        self.assertEqual(world.factions[faction_name].treasury, treasury_before)

        score_before = region.integration_score
        disturbed_income = get_region_effective_income(region, world)
        update_region_integration(world)

        self.assertGreater(region.integration_score, score_before)
        self.assertEqual(region.unrest_event_level, "none")
        self.assertLess(disturbed_income, region.resources)

    def test_critical_unrest_triggers_crisis_and_lasts_two_turns(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.core_status = "frontier"
        region.integration_score = 2.0
        region.unrest = 8.5

        resolve_unrest_events(world)

        self.assertEqual(region.unrest_event_level, "crisis")
        self.assertEqual(region.unrest_event_turns_remaining, 2)
        crisis_projection = get_region_attack_projection_modifier(
            region,
            world=world,
            faction_name=faction_name,
        )

        update_region_integration(world)
        self.assertEqual(region.unrest_event_level, "crisis")
        self.assertEqual(region.unrest_event_turns_remaining, 1)

        self.assertLess(crisis_projection, -1)

        update_region_integration(world)
        self.assertEqual(region.unrest_event_level, "none")

    def test_sustained_crisis_can_force_region_to_secede(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.resources = 4

        rebel_name, region = self._spawn_rebel_from_region(world, faction_name)
        self.assertIsNotNone(region.owner)
        self.assertIn(rebel_name, world.factions)
        rebel_faction = world.factions[rebel_name]
        self.assertTrue(rebel_faction.is_rebel)
        self.assertEqual(rebel_faction.origin_faction, faction_name)
        self.assertTrue(rebel_faction.proto_state)
        self.assertEqual(region.integrated_owner, rebel_name)
        self.assertEqual(region.core_status, "core")
        self.assertEqual(region.resources, 3)
        self.assertEqual(region.unrest_crisis_streak, 0)
        self.assertEqual(world.events[-1].type, "unrest_secession")
        self.assertEqual(world.events[-1].details["rebel_faction"], rebel_name)
        self.assertEqual(rebel_faction.doctrine_state.homeland_region, region.name)
        self.assertEqual(
            rebel_faction.doctrine_state.homeland_climate,
            region.climate,
        )

    def test_origin_faction_gets_decay_reclaim_bonus_against_proto_rebels(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        rebel_name, region = self._spawn_rebel_from_region(world, faction_name)
        self.assertGreater(
            get_rebel_reclaim_bonus(faction_name, rebel_name, world),
            0,
        )
        score_components = get_attack_target_score_components(region.name, faction_name, world)
        self.assertGreater(score_components["rebel_reclaim_bonus"], 0)

        world.factions[rebel_name].independence_score = REBEL_FULL_INDEPENDENCE_THRESHOLD
        world.factions[rebel_name].proto_state = False
        self.assertEqual(
            get_rebel_reclaim_bonus(faction_name, rebel_name, world),
            0,
        )

    def test_proto_rebel_matures_into_successor_state_and_emits_event(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        rebel_name, _region = self._spawn_rebel_from_region(world, faction_name)
        rebel_faction = world.factions[rebel_name]
        treasury_before = rebel_faction.treasury
        rebel_faction.independence_score = REBEL_FULL_INDEPENDENCE_THRESHOLD - 0.2

        update_rebel_faction_status(world)
        self.assertEqual(world.events[-1].type, "rebel_independence")
        self.assertEqual(world.events[-1].faction, rebel_name)
        self.assertFalse(rebel_faction.proto_state)
        self.assertEqual(rebel_faction.government_type, REBEL_MATURE_GOVERNMENT_TYPE)
        self.assertEqual(
            rebel_faction.treasury,
            treasury_before + REBEL_INDEPENDENCE_TREASURY_BONUS,
        )

    def test_proto_rebel_uses_less_concentrated_treasury_than_mature_successor(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        rebel_name, _region = self._spawn_rebel_from_region(world, faction_name)
        rebel_faction = world.factions[rebel_name]
        rebel_faction.treasury = 10
        defender_name = next(name for name in world.factions if name not in {faction_name, rebel_name})
        world.factions[defender_name].treasury = 5
        world.regions["D"].owner = defender_name

        proto_score = get_attack_target_score_components("D", rebel_name, world)

        rebel_faction.proto_state = False
        mature_score = get_attack_target_score_components("D", rebel_name, world)

        self.assertLess(
            proto_score["attacker_treasury_multiplier"],
            mature_score["attacker_treasury_multiplier"],
        )
        self.assertLess(
            proto_score["attacker_deployable_treasury"],
            mature_score["attacker_deployable_treasury"],
        )

    def test_secession_sets_cooldown_to_block_immediate_repeat(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        _rebel_name, region = self._spawn_rebel_from_region(world, faction_name)

        self.assertGreater(region.secession_cooldown_turns, 0)

    def test_rebel_regions_do_not_spawn_recursive_rebel_factions(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        rebel_name, region = self._spawn_rebel_from_region(world, faction_name)
        faction_count_before = len(world.factions)
        region.unrest_event_level = "crisis"
        region.unrest_event_turns_remaining = 2
        region.unrest_crisis_streak = UNREST_SECESSION_CRISIS_TURNS - 1
        region.unrest = 9.5

        update_region_integration(world)

        self.assertEqual(region.owner, rebel_name)
        self.assertEqual(len(world.factions), faction_count_before)
        self.assertLess(region.unrest, 9.5)

    def test_treasury_concentration_declines_with_empire_size(self):
        self.assertEqual(get_treasury_concentration_multiplier(1), 1.0)
        self.assertLess(get_treasury_concentration_multiplier(3), 1.0)
        self.assertLess(
            get_treasury_concentration_multiplier(5),
            get_treasury_concentration_multiplier(3),
        )
        self.assertGreaterEqual(
            get_treasury_concentration_multiplier(20),
            MIN_TREASURY_CONCENTRATION,
        )

    def test_attack_score_uses_only_part_of_large_empire_treasury(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 12
        world.factions[defender_name].treasury = 12
        world.regions["D"].owner = defender_name

        small_empire_score = get_attack_target_score_components("D", attacker_name, world)

        world.regions["M"].owner = attacker_name
        world.regions["B"].owner = attacker_name
        large_empire_score = get_attack_target_score_components("D", attacker_name, world)

        self.assertEqual(small_empire_score["attacker_region_count"], 1)
        self.assertEqual(large_empire_score["attacker_region_count"], 3)
        self.assertEqual(small_empire_score["attacker_deployable_treasury"], 12)
        self.assertLess(large_empire_score["attacker_deployable_treasury"], 12)
        self.assertLess(
            large_empire_score["attacker_treasury_multiplier"],
            small_empire_score["attacker_treasury_multiplier"],
        )


if __name__ == "__main__":
    unittest.main()
