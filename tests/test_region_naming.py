import unittest
from unittest.mock import patch

from src.actions import attack, expand
from src.simulation_ui import build_simulation_snapshots
from src.world import create_world
from src.region_naming import assign_region_founding_name


class RegionNamingTests(unittest.TestCase):
    def test_starting_regions_receive_homeland_display_names(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)

        owned_regions = [region for region in world.regions.values() if region.owner is not None]
        self.assertTrue(owned_regions)

        for region in owned_regions:
            owner = world.factions[region.owner]
            self.assertTrue(region.display_name)
            self.assertEqual(region.founding_name, region.display_name)
            self.assertEqual(region.original_namer_faction_id, owner.internal_id)
            self.assertEqual(region.display_name, owner.culture_name)

    def test_first_expansion_assigns_founding_name_and_conquest_keeps_it(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 10
        world.factions[defender_name].treasury = 1

        expanded = expand(attacker_name, "M", world)
        self.assertTrue(expanded)

        named_region = world.regions["M"]
        founded_name = named_region.display_name
        self.assertTrue(founded_name)
        self.assertNotEqual(founded_name, "M")
        self.assertEqual(named_region.founding_name, founded_name)
        self.assertEqual(
            named_region.original_namer_faction_id,
            world.factions[attacker_name].internal_id,
        )

        with patch("src.actions.random.random", return_value=0.0):
            succeeded = attack(attacker_name, "D", world)

        self.assertTrue(succeeded)
        conquered_region = world.regions["D"]
        self.assertEqual(conquered_region.owner, attacker_name)
        self.assertEqual(conquered_region.display_name, world.factions[defender_name].culture_name)
        self.assertEqual(
            conquered_region.original_namer_faction_id,
            world.factions[defender_name].internal_id,
        )

    def test_snapshots_show_code_name_until_region_is_first_named(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        world.factions[faction_name].treasury = 10

        self.assertTrue(expand(faction_name, "M", world))
        world.turn = 1

        snapshots = build_simulation_snapshots(world)
        self.assertEqual(snapshots[0]["regions"]["M"]["display_name"], "M")
        self.assertNotEqual(snapshots[1]["regions"]["M"]["display_name"], "M")

    def test_homeland_naming_stays_direct_even_with_terrain(self):
        world = create_world(map_name="multi_ring_symmetry", num_factions=4)

        for region in world.regions.values():
            if region.owner is None:
                continue
            self.assertEqual(region.display_name, world.factions[region.owner].culture_name)

    def test_terrain_aware_naming_uses_region_cues(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))

        region = world.regions["M"]
        region.display_name = ""
        region.founding_name = ""
        region.original_namer_faction_id = None
        region.name_metadata = {}
        region.terrain_tags = ["riverland", "forest"]

        assigned_name = assign_region_founding_name(world, "M", faction_name, is_homeland=False)
        expected_terms = {"Banks", "Ford", "Grove", "Hollow", "Wash", "Wood"}
        self.assertTrue(
            any(term in assigned_name for term in expected_terms),
            msg=f"Expected a terrain-aware name, got {assigned_name}",
        )
        self.assertEqual(region.name_metadata["terrain_label"], "Riverland Forest")


if __name__ == "__main__":
    unittest.main()
