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
    expand,
    get_attack_target_score_components,
    get_treasury_concentration_multiplier,
)
from src.heartland import (
    CORE_INTEGRATION_SCORE,
    apply_unrest_secession,
    estimate_region_population,
    faction_has_ethnic_claim,
    get_faction_ethnic_claims,
    get_region_dominant_ethnicity,
    get_region_ethnic_claimants,
    get_region_ethnic_integration_multiplier,
    get_rebel_reclaim_bonus,
    get_region_attack_projection_modifier,
    get_region_core_status,
    get_region_effective_income,
    get_region_maintenance_cost,
    get_region_ruling_ethnic_affinity,
    get_region_unrest_pressure,
    resolve_unrest_events,
    seed_region_ethnicity,
    update_region_populations,
    update_rebel_faction_status,
    update_region_integration,
)
from src.metrics import build_turn_metrics
from src.simulation_ui import build_simulation_snapshots, build_simulation_view_model
from src.simulation import get_faction_economy_snapshot
from src.world import create_world


class HeartlandSystemTests(unittest.TestCase):
    def _spawn_rebel_from_region(self, world, faction_name, region_name="M"):
        region = world.regions[region_name]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.core_status = "frontier"
        region.integration_score = 1.0
        if region.population <= 0:
            region.population = estimate_region_population(
                region.resources,
                len(region.neighbors),
                owner=faction_name,
            )
        if not region.ethnic_composition:
            seed_region_ethnicity(
                region,
                world.factions[faction_name].primary_ethnicity,
            )
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

    def test_world_seeds_population_only_for_starting_factions(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        owned_region = world.regions["A"]
        unowned_region = world.regions["C"]
        faction_name = owned_region.owner

        self.assertEqual(
            owned_region.population,
            estimate_region_population(
                owned_region.resources,
                len(owned_region.neighbors),
                owner=owned_region.owner,
            ),
        )
        self.assertEqual(
            get_region_dominant_ethnicity(owned_region),
            world.factions[faction_name].primary_ethnicity,
        )
        self.assertEqual(unowned_region.population, 0)
        self.assertEqual(unowned_region.ethnic_composition, {})

    def test_population_growth_responds_to_unrest(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        calm_region = world.regions["A"]
        crisis_region = world.regions["M"]
        calm_before = calm_region.population
        crisis_region.owner = calm_region.owner
        crisis_region.integrated_owner = calm_region.owner
        crisis_region.population = calm_before
        crisis_before = crisis_region.population
        crisis_region.unrest = 10.0

        update_region_populations(world)

        self.assertGreater(calm_region.population, calm_before)
        self.assertLess(crisis_region.population, crisis_before)

    def test_ruling_ethnic_affinity_tracks_owner_population_share(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.population = 100
        region.ethnic_composition = {
            world.factions[faction_name].primary_ethnicity: 70,
            "Neighborfolk": 30,
        }

        self.assertAlmostEqual(get_region_ruling_ethnic_affinity(region, world), 0.7)

    def test_ethnic_affinity_reduces_unrest_and_speeds_integration(self):
        aligned_world = create_world(map_name="thirteen_region_ring", num_factions=4)
        mismatched_world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(aligned_world.factions))

        aligned_region = aligned_world.regions["M"]
        aligned_region.owner = faction_name
        aligned_region.integrated_owner = faction_name
        aligned_region.core_status = "frontier"
        aligned_region.integration_score = 1.0
        aligned_region.population = 100
        aligned_region.climate = aligned_world.factions[faction_name].doctrine_state.homeland_climate
        aligned_region.ethnic_composition = {
            aligned_world.factions[faction_name].primary_ethnicity: 100,
        }

        mismatched_region = mismatched_world.regions["M"]
        mismatched_region.owner = faction_name
        mismatched_region.integrated_owner = faction_name
        mismatched_region.core_status = "frontier"
        mismatched_region.integration_score = 1.0
        mismatched_region.population = 100
        mismatched_region.climate = mismatched_world.factions[faction_name].doctrine_state.homeland_climate
        mismatched_region.ethnic_composition = {"Neighborfolk": 100}

        self.assertGreater(
            get_region_ethnic_integration_multiplier(aligned_region, aligned_world),
            get_region_ethnic_integration_multiplier(mismatched_region, mismatched_world),
        )
        self.assertLess(
            get_region_unrest_pressure(aligned_region, aligned_world),
            get_region_unrest_pressure(mismatched_region, mismatched_world),
        )

        update_region_integration(aligned_world)
        update_region_integration(mismatched_world)

        self.assertGreater(aligned_region.integration_score, mismatched_region.integration_score)
        self.assertLess(aligned_region.unrest, mismatched_region.unrest)

    def test_ethnic_claims_follow_dominant_ethnicity_and_help_the_ruler(self):
        claim_world = create_world(map_name="thirteen_region_ring", num_factions=4)
        no_claim_world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(claim_world.factions))
        primary_ethnicity = claim_world.factions[faction_name].primary_ethnicity

        claim_region = claim_world.regions["M"]
        claim_region.owner = faction_name
        claim_region.integrated_owner = faction_name
        claim_region.core_status = "frontier"
        claim_region.integration_score = 1.0
        claim_region.population = 100
        claim_region.climate = claim_world.factions[faction_name].doctrine_state.homeland_climate
        claim_region.ethnic_composition = {
            primary_ethnicity: 45,
            "Neighborfolk": 40,
            "Hillfolk": 15,
        }

        no_claim_region = no_claim_world.regions["M"]
        no_claim_region.owner = faction_name
        no_claim_region.integrated_owner = faction_name
        no_claim_region.core_status = "frontier"
        no_claim_region.integration_score = 1.0
        no_claim_region.population = 100
        no_claim_region.climate = no_claim_world.factions[faction_name].doctrine_state.homeland_climate
        no_claim_region.ethnic_composition = {
            no_claim_world.factions[faction_name].primary_ethnicity: 45,
            "Neighborfolk": 55,
        }

        self.assertTrue(faction_has_ethnic_claim(claim_world, claim_region, faction_name))
        self.assertFalse(faction_has_ethnic_claim(no_claim_world, no_claim_region, faction_name))
        self.assertIn(faction_name, get_region_ethnic_claimants(claim_region, claim_world))
        self.assertIn("M", get_faction_ethnic_claims(claim_world, faction_name))

        self.assertGreater(
            get_region_ethnic_integration_multiplier(claim_region, claim_world),
            get_region_ethnic_integration_multiplier(no_claim_region, no_claim_world),
        )
        self.assertLess(
            get_region_unrest_pressure(claim_region, claim_world),
            get_region_unrest_pressure(no_claim_region, no_claim_world),
        )

    def test_expansion_transfers_population_from_adjacent_owned_region(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        source_region = world.regions["A"]
        target_region = world.regions["B"]
        world.factions[faction_name].treasury = 10
        source_before = source_region.population
        source_ethnicity = world.factions[faction_name].primary_ethnicity

        succeeded = expand(faction_name, "B", world)

        self.assertTrue(succeeded)
        self.assertEqual(target_region.owner, faction_name)
        self.assertGreater(target_region.population, 0)
        self.assertLess(source_region.population, source_before)
        self.assertGreater(world.events[-1].details["population_transfer"], 0)
        self.assertEqual(get_region_dominant_ethnicity(target_region), source_ethnicity)

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
        region.owner = faction_name
        region.integrated_owner = faction_name
        if region.population <= 0:
            region.population = estimate_region_population(
                region.resources,
                len(region.neighbors),
                owner=faction_name,
            )
        if not region.ethnic_composition:
            seed_region_ethnicity(
                region,
                world.factions[faction_name].primary_ethnicity,
            )
        population_before = region.population

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
        self.assertLess(region.population, population_before)
        self.assertEqual(region.unrest_crisis_streak, 0)
        self.assertEqual(world.events[-1].type, "unrest_secession")
        self.assertEqual(world.events[-1].details["rebel_faction"], rebel_name)
        self.assertEqual(rebel_faction.doctrine_state.homeland_region, region.name)
        self.assertEqual(
            rebel_faction.doctrine_state.homeland_climate,
            region.climate,
        )

    def test_extinct_ethnicity_can_restore_original_faction_via_rebellion(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        occupier_name = faction_names[0]
        restored_name = faction_names[1]
        restored_ethnicity = world.factions[restored_name].primary_ethnicity
        faction_count_before = len(world.factions)

        restored_regions = [
            region
            for region in world.regions.values()
            if region.owner == restored_name
        ]
        self.assertTrue(restored_regions)

        target_region = restored_regions[0]
        for region in restored_regions:
            region.owner = occupier_name
            region.integrated_owner = occupier_name
            region.core_status = "frontier"
            region.integration_score = 1.0

        apply_unrest_secession(world, target_region)

        self.assertEqual(target_region.owner, restored_name)
        self.assertEqual(len(world.factions), faction_count_before)
        self.assertEqual(world.events[-1].type, "unrest_secession")
        self.assertTrue(world.events[-1].details["restoration"])
        self.assertEqual(world.events[-1].details["restored_faction"], restored_name)
        self.assertEqual(world.events[-1].details["revived_ethnicity"], restored_ethnicity)
        self.assertIn("restoration", world.events[-1].tags)
        self.assertIn("revival", world.events[-1].tags)
        self.assertFalse(world.factions[restored_name].proto_state)
        self.assertEqual(world.factions[restored_name].primary_ethnicity, restored_ethnicity)

    def test_unrest_secession_can_pull_in_adjacent_unrestful_regions(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction_count_before = len(world.factions)
        seed_region = world.regions["M"]
        join_region = world.regions[seed_region.neighbors[0]]

        for region, unrest in ((seed_region, 9.5), (join_region, 5.0)):
            region.owner = faction_name
            region.integrated_owner = faction_name
            region.core_status = "frontier"
            region.integration_score = 1.0
            region.homeland_faction_id = None
            region.population = estimate_region_population(
                region.resources,
                len(region.neighbors),
                owner=faction_name,
            )
            seed_region_ethnicity(region, world.factions[faction_name].primary_ethnicity)
            region.unrest = unrest
            region.unrest_event_level = "disturbance" if unrest >= 4.0 else "none"
            region.secession_cooldown_turns = 0

        apply_unrest_secession(world, seed_region)

        rebel_name = seed_region.owner
        self.assertEqual(len(world.factions), faction_count_before + 1)
        self.assertEqual(join_region.owner, rebel_name)
        self.assertEqual(join_region.integrated_owner, rebel_name)
        self.assertEqual(join_region.core_status, "core")
        self.assertEqual(world.events[-1].details["joined_region_count"], 1)
        self.assertIn(join_region.name, world.events[-1].details["joined_regions"])
        self.assertIn("regional_uprising", world.events[-1].tags)

    def test_adjacent_secession_joins_existing_rebel_movement(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        seed_region = world.regions["M"]
        join_region = world.regions[seed_region.neighbors[0]]

        for region in (seed_region, join_region):
            region.owner = faction_name
            region.integrated_owner = faction_name
            region.core_status = "frontier"
            region.integration_score = 1.0
            region.homeland_faction_id = None
            region.population = estimate_region_population(
                region.resources,
                len(region.neighbors),
                owner=faction_name,
            )
            seed_region_ethnicity(region, world.factions[faction_name].primary_ethnicity)
            region.secession_cooldown_turns = 0

        seed_region.unrest = 9.5
        seed_region.unrest_event_level = "crisis"
        join_region.unrest = 1.0
        join_region.unrest_event_level = "none"

        faction_count_after_first = len(world.factions) + 1
        apply_unrest_secession(world, seed_region)
        rebel_name = seed_region.owner
        self.assertEqual(len(world.factions), faction_count_after_first)

        join_region.unrest = 9.5
        join_region.unrest_event_level = "crisis"
        join_region.secession_cooldown_turns = 0

        apply_unrest_secession(world, join_region)

        self.assertEqual(join_region.owner, rebel_name)
        self.assertEqual(len(world.factions), faction_count_after_first)
        self.assertTrue(world.events[-1].details["joined_existing_rebellion"])
        self.assertEqual(world.events[-1].details["rebel_faction"], rebel_name)

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
        rebel_name, region = self._spawn_rebel_from_region(world, faction_name)
        rebel_faction = world.factions[rebel_name]
        treasury_before = rebel_faction.treasury
        parent_ethnicity = world.factions[faction_name].primary_ethnicity
        rebel_faction.independence_score = REBEL_FULL_INDEPENDENCE_THRESHOLD - 0.2

        update_rebel_faction_status(world)
        self.assertEqual(world.events[-1].type, "rebel_independence")
        self.assertEqual(world.events[-1].faction, rebel_name)
        self.assertFalse(rebel_faction.proto_state)
        self.assertEqual(rebel_faction.polity_tier, "state")
        self.assertEqual(rebel_faction.government_form, "council")
        self.assertEqual(rebel_faction.government_type, REBEL_MATURE_GOVERNMENT_TYPE)
        self.assertNotEqual(rebel_faction.primary_ethnicity, parent_ethnicity)
        self.assertEqual(rebel_faction.display_name, rebel_faction.primary_ethnicity)
        self.assertEqual(rebel_faction.culture_name, rebel_faction.primary_ethnicity)
        self.assertIn(rebel_faction.primary_ethnicity, world.ethnicities)
        self.assertEqual(world.ethnicities[rebel_faction.primary_ethnicity].parent_ethnicity, parent_ethnicity)
        self.assertTrue(world.ethnicities[rebel_faction.primary_ethnicity].language_profile.onsets)
        self.assertTrue(rebel_faction.identity.language_profile.seed_fragments)
        self.assertEqual(get_region_dominant_ethnicity(region), rebel_faction.primary_ethnicity)
        self.assertGreater(region.ethnic_composition.get(rebel_faction.primary_ethnicity, 0), 0)
        self.assertGreater(region.ethnic_composition.get(parent_ethnicity, 0), 0)
        self.assertGreater(
            region.ethnic_composition.get(rebel_faction.primary_ethnicity, 0),
            region.ethnic_composition.get(parent_ethnicity, 0),
        )
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

    def test_attack_inflicts_population_loss_on_target_region(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]
        target_region = world.regions["B"]
        target_region.owner = defender_name
        target_region.integrated_owner = defender_name
        if target_region.population <= 0:
            target_region.population = estimate_region_population(
                target_region.resources,
                len(target_region.neighbors),
                owner=defender_name,
            )
        if not target_region.ethnic_composition:
            seed_region_ethnicity(
                target_region,
                world.factions[defender_name].primary_ethnicity,
            )
        before = target_region.population
        world.factions[attacker_name].treasury = 10

        with patch("src.actions.random.random", return_value=0.0):
            attack(attacker_name, "B", world)

        self.assertLess(target_region.population, before)
        self.assertGreater(world.events[-1].details["population_loss"], 0)

    def test_metrics_and_snapshots_include_population(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))

        metrics = build_turn_metrics(world)
        self.assertIn("population", metrics["factions"][faction_name])

        snapshots = build_simulation_snapshots(world)
        self.assertIn("population", snapshots[0]["regions"]["A"])
        self.assertIn("ruling_ethnic_affinity", snapshots[0]["regions"]["A"])
        self.assertIn("owner_primary_ethnicity", snapshots[0]["regions"]["A"])
        self.assertIn("ethnic_claimants", snapshots[0]["regions"]["A"])
        self.assertIn("owner_has_ethnic_claim", snapshots[0]["regions"]["A"])

        view_model = build_simulation_view_model(world)
        self.assertIn("population", view_model["regions"][0])
        self.assertIn("ruling_ethnic_affinity", view_model["regions"][0])
        self.assertIn("ethnic_claimants", view_model["regions"][0])
        self.assertIn("ethnic_claims", view_model["factions"][0])


if __name__ == "__main__":
    unittest.main()
