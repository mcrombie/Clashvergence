import unittest

from src.actions import get_attack_target_score_components
from src.doctrine import (
    get_faction_climate_affinity,
    get_faction_region_alignment,
    update_faction_doctrines,
)
from src.heartland import (
    get_region_effective_income,
    get_region_maintenance_cost,
    get_region_attack_projection_modifier,
    update_region_integration,
)
from src.world import create_world


class ClimateSystemTests(unittest.TestCase):
    def test_world_loads_climate_data_for_thirty_seven_region_ring(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)

        self.assertEqual(world.regions["O1"].climate, "oceanic")
        self.assertEqual(world.regions["M1"].climate, "temperate")
        self.assertEqual(world.regions["I1"].climate, "cold")
        self.assertEqual(world.regions["C"].climate, "temperate")

    def test_homeland_climate_initializes_from_starting_region(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)

        for faction in world.factions.values():
            homeland_region = faction.doctrine_state.homeland_region
            self.assertIsNotNone(homeland_region)
            self.assertEqual(
                faction.doctrine_state.homeland_climate,
                world.regions[homeland_region].climate,
            )
            self.assertEqual(faction.doctrine_profile.climate_identity, "Temperate")

    def test_matching_climate_improves_region_alignment(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        adapted = world.factions[faction_names[0]]
        unadapted = world.factions[faction_names[1]]

        adapted.doctrine_state.homeland_climate = "cold"
        adapted.doctrine_state.climate_experience = {"cold": 16.0}
        unadapted.doctrine_state.homeland_climate = "temperate"
        unadapted.doctrine_state.climate_experience = {"temperate": 16.0}

        adapted_alignment = get_faction_region_alignment(adapted, ["highland", "forest"], "cold")
        unadapted_alignment = get_faction_region_alignment(unadapted, ["highland", "forest"], "cold")

        self.assertGreater(adapted_alignment["climate_affinity"], unadapted_alignment["climate_affinity"])
        self.assertGreaterEqual(adapted_alignment["combat_modifier"], unadapted_alignment["combat_modifier"])
        self.assertTrue(adapted_alignment["climate_match"])
        self.assertFalse(unadapted_alignment["climate_match"])

    def test_climate_affinity_grows_through_exposure_over_time(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        target_region = world.regions["B"]
        target_region.owner = faction_name
        target_region.integrated_owner = faction_name
        target_region.homeland_faction_id = "OtherFaction"
        target_region.climate = "cold"

        initial_affinity = get_faction_climate_affinity(faction, "cold")
        for _ in range(3):
            update_faction_doctrines(world)
        adapted_affinity = get_faction_climate_affinity(faction, "cold")

        self.assertGreater(adapted_affinity, initial_affinity)

    def test_matching_climate_integrates_faster_than_foreign_climate(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))

        temperate_region = world.regions["B"]
        cold_region = world.regions["C"]

        for region, climate in ((temperate_region, "temperate"), (cold_region, "cold")):
            region.owner = faction_name
            region.integrated_owner = faction_name
            region.homeland_faction_id = "SomeoneElse"
            region.integration_score = 1.0
            region.core_status = "frontier"
            region.ownership_turns = 1
            region.climate = climate

        update_region_integration(world)

        self.assertGreater(temperate_region.integration_score, cold_region.integration_score)

    def test_attack_projection_penalizes_foreign_climate_staging(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.integration_score = 1.0
        region.core_status = "frontier"

        region.climate = "temperate"
        matching_projection = get_region_attack_projection_modifier(
            region,
            world=world,
            faction_name=faction_name,
        )

        region.climate = "cold"
        mismatched_projection = get_region_attack_projection_modifier(
            region,
            world=world,
            faction_name=faction_name,
        )

        self.assertEqual(matching_projection, -1)
        self.assertEqual(mismatched_projection, -3)

    def test_climate_affinity_improves_income_and_reduces_maintenance(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]

        matched_region = world.regions["B"]
        matched_region.owner = faction_name
        matched_region.integrated_owner = faction_name
        matched_region.homeland_faction_id = "OtherFaction"
        matched_region.core_status = "frontier"
        matched_region.integration_score = 1.0
        matched_region.resources = 4
        matched_region.climate = faction.doctrine_state.homeland_climate

        foreign_region = world.regions["C"]
        foreign_region.owner = faction_name
        foreign_region.integrated_owner = faction_name
        foreign_region.homeland_faction_id = "OtherFaction"
        foreign_region.core_status = "frontier"
        foreign_region.integration_score = 1.0
        foreign_region.resources = 4
        foreign_region.climate = "cold" if faction.doctrine_state.homeland_climate != "cold" else "arid"

        self.assertGreaterEqual(
            get_region_effective_income(matched_region, world),
            get_region_effective_income(foreign_region, world),
        )
        self.assertLessEqual(
            get_region_maintenance_cost(matched_region, world),
            get_region_maintenance_cost(foreign_region, world),
        )

    def test_attack_score_exposes_climate_sensitive_alignment(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 8
        world.factions[defender_name].treasury = 8
        world.regions["D"].owner = defender_name
        world.regions["D"].climate = "cold"

        score = get_attack_target_score_components("D", attacker_name, world)

        self.assertIn("doctrine_combat_modifier", score)
        self.assertIn("terrain_affinity", score)
        self.assertGreaterEqual(score["success_chance"], 0.2)


if __name__ == "__main__":
    unittest.main()
