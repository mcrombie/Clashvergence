import unittest

from src.faction_arrivals import is_faction_inactive
from src.maps import MAPS
from src.player_view import build_observer_snapshot
from src.simulation import run_turn
from src.world import create_world
from src.world_serialization import deserialize_world, serialize_world


class FactionArrivalTests(unittest.TestCase):
    def test_disruptive_arrival_activates_faction_and_seizes_entry_region(self):
        map_name = "arrival_test_map"
        MAPS[map_name] = {
            "description": "test delayed disruptive arrival",
            "num_factions": 2,
            "regions": {
                "Native Core": {
                    "neighbors": ["Colony Gate"],
                    "owner": "Faction1",
                    "resources": 2,
                    "terrain_tags": ["plains"],
                    "climate": "temperate",
                },
                "Colony Gate": {
                    "neighbors": ["Native Core"],
                    "owner": "Faction1",
                    "resources": 2,
                    "terrain_tags": ["coast"],
                    "climate": "temperate",
                },
            },
            "faction_arrivals": {
                "Faction2": {
                    "arrival_turn": 1,
                    "arrival_type": "disruptive_colonial_landing",
                    "entry_region": "Colony Gate",
                    "origin": "foreign land",
                    "status": "foreign_colony",
                }
            },
        }
        try:
            world = create_world(map_name=map_name, num_factions=2, seed="arrival-test")
            native_name = next(
                faction_name
                for faction_name, faction in world.factions.items()
                if faction.internal_id == "Faction1"
            )
            arrival_name = next(
                faction_name
                for faction_name, faction in world.factions.items()
                if faction.internal_id == "Faction2"
            )

            self.assertTrue(is_faction_inactive(world, arrival_name))
            self.assertEqual(world.regions["Colony Gate"].owner, native_name)
            self.assertNotIn(
                arrival_name,
                [faction["name"] for faction in build_observer_snapshot(world)["factions"]],
            )

            run_turn(world, randomize_order=False, verbose=False)
            self.assertTrue(is_faction_inactive(world, arrival_name))
            self.assertEqual(world.regions["Colony Gate"].owner, native_name)

            serialized = serialize_world(world)
            world = deserialize_world(serialized)
            run_turn(world, randomize_order=False, verbose=False)

            self.assertFalse(is_faction_inactive(world, arrival_name))
            self.assertEqual(world.regions["Colony Gate"].owner, arrival_name)
            self.assertIn(
                arrival_name,
                [faction["name"] for faction in build_observer_snapshot(world)["factions"]],
            )
            arrival_event = next(
                event
                for event in world.events
                if event.type == "colonial_arrival"
            )
            self.assertEqual(arrival_event.turn, 1)
            self.assertEqual(arrival_event.faction, arrival_name)
            self.assertEqual(arrival_event.region, "Colony Gate")
            self.assertEqual(arrival_event.details["owner_before"], native_name)
            self.assertTrue(arrival_event.details["disruptive"])
        finally:
            MAPS.pop(map_name, None)


if __name__ == "__main__":
    unittest.main()
