import unittest

from src.factions import validate_map_factions
from src.map_generator import build_generated_map_definition, build_generation_config
from src.map_visualization import build_map_layout
from src.maps import MAPS
from src.world import create_world


class DynamicMapGeneratorTests(unittest.TestCase):
    def test_generated_map_is_deterministic_for_name_and_faction_count(self):
        first = build_generated_map_definition("generated_ring", 4)
        second = build_generated_map_definition("generated_ring", 4)

        self.assertEqual(first, second)

    def test_generated_map_assigns_one_start_per_configured_faction(self):
        map_name = "generated_frontier"
        num_factions = 6
        definition = build_generated_map_definition(map_name, num_factions)
        MAPS[map_name] = definition

        validate_map_factions(map_name, num_factions)

        starting_owners = [
            region["owner"]
            for region in definition["regions"].values()
            if region["owner"] is not None
        ]
        self.assertEqual(
            sorted(starting_owners),
            [f"Faction{index}" for index in range(1, num_factions + 1)],
        )

    def test_create_world_accepts_generated_map_names(self):
        world = create_world(map_name="generated_basin", num_factions=5)

        self.assertEqual(world.map_name, "generated_basin")
        self.assertIn("generated_basin", MAPS)
        self.assertEqual(len(world.factions), 5)
        self.assertGreaterEqual(len(world.regions), 25)
        self.assertTrue(world.river_links)
        for faction_name in world.factions:
            owned_regions = [
                region
                for region in world.regions.values()
                if region.owner == faction_name
            ]
            self.assertEqual(len(owned_regions), 1)

    def test_archipelago_generation_creates_sea_links_and_positions(self):
        definition = build_generated_map_definition(
            "generated_archipelago",
            6,
            config={
                "seed": "test-archipelago",
                "region_count": 54,
                "landmass_count": 4,
                "water_level": 0.7,
            },
        )

        self.assertTrue(definition["sea_links"])
        self.assertGreaterEqual(len(definition["river_links"]), 1)
        for region in definition["regions"].values():
            self.assertIn("position", region)
            self.assertGreaterEqual(region["position"]["x"], 0.0)
            self.assertLessEqual(region["position"]["x"], 1.0)
            self.assertGreaterEqual(region["position"]["y"], 0.0)
            self.assertLessEqual(region["position"]["y"], 1.0)

    def test_generation_config_honors_overrides(self):
        config = build_generation_config(
            "generated_world",
            5,
            {
                "style": "highlands",
                "seed": "ridge-test",
                "regions": 64,
                "landmasses": 2,
                "rivers": 5,
                "mountains": 6,
                "starts": "heartland",
            },
        )

        self.assertEqual(config.style, "highlands")
        self.assertEqual(config.seed, "ridge-test")
        self.assertEqual(config.region_count, 64)
        self.assertEqual(config.landmass_count, 2)
        self.assertEqual(config.river_count, 5)
        self.assertEqual(config.mountain_spines, 6)
        self.assertEqual(config.start_strategy, "heartland")

    def test_generated_world_has_connected_graph_and_varied_geography(self):
        definition = build_generated_map_definition(
            "generated_world",
            5,
            config={
                "style": "highlands",
                "seed": "connectivity-test",
                "region_count": 60,
                "landmass_count": 2,
                "river_count": 4,
                "mountain_spines": 6,
                "terrain_diversity": 0.9,
            },
        )
        regions = definition["regions"]
        seen = set()
        stack = [next(iter(regions))]
        while stack:
            region_name = stack.pop()
            if region_name in seen:
                continue
            seen.add(region_name)
            stack.extend(regions[region_name]["neighbors"])

        terrain_signatures = {
            tuple(region["terrain_tags"])
            for region in regions.values()
        }
        climates = {region["climate"] for region in regions.values()}

        self.assertEqual(len(seen), len(regions))
        self.assertGreaterEqual(len(terrain_signatures), 4)
        self.assertGreaterEqual(len(climates), 2)

    def test_map_layout_uses_generated_region_positions(self):
        definition = build_generated_map_definition(
            "generated_world",
            4,
            config={"seed": "layout-test", "region_count": 36},
        )
        positions = build_map_layout(definition["regions"], width=1000, height=800)
        region_name, region = next(iter(definition["regions"].items()))

        self.assertAlmostEqual(
            positions[region_name][0],
            region["position"]["x"] * 1000,
            delta=1.0,
        )
        self.assertAlmostEqual(
            positions[region_name][1],
            region["position"]["y"] * 800,
            delta=1.0,
        )


if __name__ == "__main__":
    unittest.main()
