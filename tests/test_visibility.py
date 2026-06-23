import unittest

from src.actions import explore, get_explorable_regions
from src.heartland import create_rebel_faction
from src.models import Faction, Region, WorldState
from src.visibility import refresh_faction_visibility
from src.world import create_world


class VisibilityTests(unittest.TestCase):
    def test_factions_start_knowing_only_homeland_and_neighbor_regions(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        homeland_region = faction.doctrine_state.homeland_region

        self.assertIsNotNone(homeland_region)
        expected_known = {homeland_region, *world.regions[homeland_region].neighbors}

        self.assertEqual(set(faction.known_regions), expected_known)
        self.assertEqual(set(faction.visible_regions), expected_known)
        self.assertNotIn("H", faction.known_regions)

    def test_visibility_refresh_reveals_neighbors_of_newly_owned_regions(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]

        self.assertNotIn("D", faction.known_regions)
        world.regions["B"].owner = faction_name
        refresh_faction_visibility(world, faction_name)

        self.assertIn("B", faction.visible_regions)
        self.assertIn("C", faction.visible_regions)
        self.assertIn("C", faction.known_regions)
        self.assertNotIn("D", faction.known_regions)

    def test_rebel_faction_inherits_parent_known_regions(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        parent_name = next(iter(world.factions))
        parent_faction = world.factions[parent_name]

        world.regions["B"].owner = parent_name
        refresh_faction_visibility(world, parent_name)
        parent_known_before = set(parent_faction.known_regions)

        rebel_name, _restored = create_rebel_faction(world, world.regions["M"], parent_name)
        rebel_faction = world.factions[rebel_name]

        self.assertTrue(parent_known_before.issubset(set(rebel_faction.known_regions)))
        self.assertIn("M", rebel_faction.known_regions)
        self.assertIn("E", rebel_faction.known_regions)

    def test_explore_reveals_unknown_neighbors_without_claiming_target(self):
        world = WorldState(
            regions={
                "A": Region(name="A", neighbors=["B"], owner="FactionA", resources=3),
                "B": Region(name="B", neighbors=["A", "C", "D"], owner=None, resources=2),
                "C": Region(name="C", neighbors=["B"], owner=None, resources=2),
                "D": Region(name="D", neighbors=["B"], owner="FactionB", resources=2),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=0),
                "FactionB": Faction(name="FactionB", treasury=0),
            },
        )
        faction = world.factions["FactionA"]
        faction.known_regions = ["A", "B"]
        faction.visible_regions = ["A", "B"]
        faction.known_factions = ["FactionA"]

        self.assertIn("B", get_explorable_regions("FactionA", world))
        self.assertTrue(explore("FactionA", "B", world))

        self.assertIsNone(world.regions["B"].owner)
        self.assertIn("C", faction.known_regions)
        self.assertIn("D", faction.known_regions)
        self.assertIn("FactionB", faction.known_factions)
        event = world.events[-1]
        self.assertEqual(event.type, "explore")
        self.assertEqual(event.details["revealed_region_count"], 2)
        self.assertEqual(event.impact["frontier_regions_revealed"], 1)


if __name__ == "__main__":
    unittest.main()
