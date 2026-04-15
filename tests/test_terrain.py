import unittest

from src.actions import (
    get_attack_target_score_components,
    get_expand_target_score_components,
)
from src.simulation_ui import build_simulation_view_model
from src.terrain import format_terrain_label, get_terrain_profile, normalize_terrain_tags
from src.world import create_world


class TerrainSystemTests(unittest.TestCase):
    def test_terrain_profile_combines_composite_tags(self):
        profile = get_terrain_profile(["highland", "forest"])

        self.assertEqual(profile["terrain_tags"], ["highland", "forest"])
        self.assertEqual(profile["terrain_label"], "Highland Forest")
        self.assertEqual(profile["expansion_modifier"], -3)
        self.assertEqual(profile["defense_modifier"], 3)
        self.assertEqual(profile["economic_modifier"], 0)
        self.assertIn("Ridge", profile["name_cues"])
        self.assertIn("Wood", profile["name_cues"])

    def test_normalize_terrain_tags_defaults_to_plains(self):
        self.assertEqual(normalize_terrain_tags([]), ["plains"])
        self.assertEqual(format_terrain_label(None), "Plains")

    def test_world_loads_map_terrain_tags(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)

        self.assertEqual(world.regions["O1"].terrain_tags, ["coast", "forest"])
        self.assertEqual(world.regions["M3"].terrain_tags, ["riverland", "plains"])
        self.assertEqual(world.regions["I1"].terrain_tags, ["highland", "forest"])
        self.assertEqual(world.regions["C"].terrain_tags, ["riverland", "plains"])

    def test_expand_target_score_reflects_terrain_modifiers(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        region = world.regions["M"]

        region.terrain_tags = ["plains"]
        plains_score = get_expand_target_score_components("M", world)

        region.terrain_tags = ["highland", "forest"]
        rough_score = get_expand_target_score_components("M", world)

        self.assertGreater(plains_score["score"], rough_score["score"])
        self.assertEqual(rough_score["terrain_label"], "Highland Forest")
        self.assertEqual(rough_score["terrain_expansion_modifier"], -3)

    def test_attack_target_score_reflects_defensive_terrain(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 6
        world.factions[defender_name].treasury = 6
        world.regions["D"].owner = defender_name

        world.regions["D"].terrain_tags = ["plains"]
        plains_score = get_attack_target_score_components("D", attacker_name, world)

        world.regions["D"].terrain_tags = ["highland", "forest"]
        rough_score = get_attack_target_score_components("D", attacker_name, world)

        self.assertGreater(rough_score["defender_strength"], plains_score["defender_strength"])
        self.assertLess(rough_score["success_chance"], plains_score["success_chance"])
        self.assertEqual(rough_score["terrain_label"], "Highland Forest")

    def test_view_model_exposes_terrain_data(self):
        world = create_world(map_name="asymmetric_frontier", num_factions=4)
        view_model = build_simulation_view_model(world)

        regions_by_name = {region["name"]: region for region in view_model["regions"]}
        self.assertEqual(regions_by_name["C"]["terrain_label"], "Riverland Forest")
        self.assertEqual(regions_by_name["C"]["terrain_tags"], ["riverland", "forest"])


if __name__ == "__main__":
    unittest.main()
