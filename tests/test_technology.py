from copy import deepcopy
import unittest

from src.actions import get_attack_target_score_components
from src.administration import refresh_administrative_state
from src.resource_economy import get_region_resource_output
from src.technology import (
    TECH_COPPER_WORKING,
    TECH_IRRIGATION_METHODS,
    TECH_MARKET_ACCOUNTING,
    TECH_ORGANIZED_LEVIES,
    TECH_ROAD_ADMINISTRATION,
    apply_development_technology_experience,
    update_technology_diffusion,
)
from src.world import create_world


class TechnologyDiffusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_world = create_world(
            map_name="thirty_seven_region_ring",
            num_factions=4,
            seed="tech-base",
        )

    @staticmethod
    def _world():
        return deepcopy(TechnologyDiffusionTests.base_world)

    def test_initialization_seeds_regionally_plausible_methods(self):
        world = self._world()
        river_regions = [
            region
            for region in world.regions.values()
            if "riverland" in region.terrain_tags
        ]
        copper_regions = [
            region
            for region in world.regions.values()
            if region.resource_fixed_endowments.get("copper", 0.0) > 0.35
        ]

        self.assertTrue(river_regions)
        self.assertTrue(copper_regions)
        self.assertTrue(
            any(
                region.technology_presence.get(TECH_IRRIGATION_METHODS, 0.0) > 0.05
                for region in river_regions
            )
        )
        self.assertTrue(
            any(
                region.technology_presence.get(TECH_COPPER_WORKING, 0.0) > 0.05
                for region in copper_regions
            )
        )

    def test_trade_and_adjacency_diffuse_technology_presence(self):
        world = self._world()
        regions = list(world.regions.values())
        source = regions[0]
        target = next(
            region
            for region in regions
            if region.name in source.neighbors
        )
        source.technology_adoption[TECH_MARKET_ACCOUNTING] = 0.9
        source.technology_presence[TECH_MARKET_ACCOUNTING] = 0.95
        target.technology_presence[TECH_MARKET_ACCOUNTING] = 0.02
        target.trade_throughput = 8.0
        before = target.technology_presence[TECH_MARKET_ACCOUNTING]

        update_technology_diffusion(world)

        self.assertGreater(
            world.regions[target.name].technology_presence[TECH_MARKET_ACCOUNTING],
            before,
        )

    def test_development_projects_raise_relevant_adoption(self):
        world = self._world()
        region = next(
            region
            for region in world.regions.values()
            if region.owner is not None and region.resource_suitability.get("grain", 0.0) > 0.4
        )
        before = region.technology_adoption[TECH_IRRIGATION_METHODS]

        apply_development_technology_experience(region, "build_irrigation", "grain")

        self.assertGreater(region.technology_adoption[TECH_IRRIGATION_METHODS], before)

    def test_technology_effects_resource_output(self):
        world = self._world()
        region = next(
            region
            for region in world.regions.values()
            if region.owner is not None and region.resource_established.get("grain", 0.0) > 0.2
        )
        region.technology_adoption[TECH_IRRIGATION_METHODS] = 0.0
        baseline = get_region_resource_output(region, world)["grain"]

        region.technology_adoption[TECH_IRRIGATION_METHODS] = 1.0
        improved = get_region_resource_output(region, world)["grain"]

        self.assertGreater(improved, baseline)

    def test_institutional_road_administration_improves_admin_capacity(self):
        world = self._world()
        faction_name = next(iter(world.factions))
        refresh_administrative_state(world)
        baseline = world.factions[faction_name].administrative_capacity

        world.factions[faction_name].institutional_technologies[TECH_ROAD_ADMINISTRATION] = 1.0
        refresh_administrative_state(world)

        self.assertGreater(world.factions[faction_name].administrative_capacity, baseline)

    def test_organized_levies_increase_attack_strength(self):
        world = self._world()
        attacker_name, defender_name = list(world.factions)[:2]
        staging_region = next(region for region in world.regions.values() if region.owner == attacker_name)
        target_name = staging_region.neighbors[0]
        target_region = world.regions[target_name]
        target_region.owner = defender_name
        target_region.integrated_owner = defender_name
        target_region.core_status = "frontier"
        world.factions[attacker_name].known_regions = list(world.regions)

        world.factions[attacker_name].institutional_technologies[TECH_ORGANIZED_LEVIES] = 0.0
        baseline = get_attack_target_score_components(target_name, attacker_name, world)
        world.factions[attacker_name].institutional_technologies[TECH_ORGANIZED_LEVIES] = 1.0
        improved = get_attack_target_score_components(target_name, attacker_name, world)

        self.assertGreater(improved["attacker_strength"], baseline["attacker_strength"])


if __name__ == "__main__":
    unittest.main()
