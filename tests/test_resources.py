import unittest

from src.actions import get_invest_target_score_components, invest
from src.resource_economy import (
    advance_region_domesticable_resources,
    update_faction_resource_economy,
)
from src.heartland import (
    estimate_region_population_from_resource_profile,
    handle_region_owner_change,
)
from src.models import Faction, Region, WorldState
from src.resources import (
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_STONE,
    seed_region_resource_profile,
)
from src.world import create_world


class ResourceSystemTests(unittest.TestCase):
    def test_world_seeding_creates_specific_resource_profiles(self):
        world = create_world(map_name="seven_region_ring", num_factions=3)

        hill_region = world.regions["D"]
        river_region = world.regions["M"]

        self.assertGreater(
            hill_region.resource_fixed_endowments[RESOURCE_COPPER],
            river_region.resource_fixed_endowments[RESOURCE_COPPER],
        )
        self.assertGreater(
            hill_region.resource_fixed_endowments[RESOURCE_STONE],
            river_region.resource_fixed_endowments[RESOURCE_STONE],
        )
        self.assertGreater(
            river_region.resource_suitability[RESOURCE_GRAIN],
            hill_region.resource_suitability[RESOURCE_GRAIN],
        )

    def test_starting_population_can_be_estimated_from_resource_profile(self):
        fertile_region = Region(
            name="A",
            neighbors=["B", "C", "D"],
            owner="FactionA",
            resources=2,
            terrain_tags=["riverland", "plains"],
            climate="temperate",
        )
        poor_region = Region(
            name="B",
            neighbors=["A", "C", "D"],
            owner="FactionA",
            resources=2,
            terrain_tags=["highland"],
            climate="cold",
        )
        seed_region_resource_profile(fertile_region)
        seed_region_resource_profile(poor_region)

        fertile_population = estimate_region_population_from_resource_profile(fertile_region)
        poor_population = estimate_region_population_from_resource_profile(poor_region)

        self.assertGreater(fertile_population, poor_population)

    def test_grain_and_horses_persist_after_conquest(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=3,
            terrain_tags=["plains", "steppe"],
            climate="temperate",
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_GRAIN] = 0.8
        region.resource_established[RESOURCE_HORSES] = 0.45

        handle_region_owner_change(region, "FactionB")

        self.assertEqual(region.owner, "FactionB")
        self.assertAlmostEqual(region.resource_established[RESOURCE_GRAIN], 0.8)
        self.assertAlmostEqual(region.resource_established[RESOURCE_HORSES], 0.45)

    def test_invest_can_introduce_grain_into_suitable_owned_neighbor(self):
        source = Region(
            name="A",
            neighbors=["B"],
            owner="FactionA",
            resources=2,
            population=140,
            terrain_tags=["plains"],
            climate="temperate",
        )
        target = Region(
            name="B",
            neighbors=["A"],
            owner="FactionA",
            resources=2,
            population=120,
            terrain_tags=["plains"],
            climate="temperate",
        )
        seed_region_resource_profile(source)
        seed_region_resource_profile(target)
        target.resource_established[RESOURCE_GRAIN] = 0.0
        target.resource_established[RESOURCE_HORSES] = 0.0

        world = WorldState(
            regions={"A": source, "B": target},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        components = get_invest_target_score_components("B", "FactionA", world)

        self.assertEqual(components["project_type"], "introduce_grain")
        self.assertTrue(invest("FactionA", "B", world))
        self.assertGreater(world.regions["B"].resource_established[RESOURCE_GRAIN], 0.0)
        self.assertEqual(world.events[-1].details["project_type"], "introduce_grain")

    def test_resource_economy_populates_access_capacities_and_shortages(self):
        world = create_world(map_name="seven_region_ring", num_factions=3)

        update_faction_resource_economy(world)
        faction = next(iter(world.factions.values()))

        self.assertIn(RESOURCE_GRAIN, faction.resource_access)
        self.assertIn("food_security", faction.derived_capacity)
        self.assertIn("metal_capacity", faction.resource_shortages)
        self.assertGreaterEqual(faction.derived_capacity["food_security"], 0.0)

    def test_isolated_frontier_output_is_lower_than_gross_output(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=180,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=1.5,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.0,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 1.0

        update_faction_resource_economy(world)
        faction = world.factions["FactionA"]

        self.assertGreater(faction.resource_gross_output[RESOURCE_COPPER], 0.0)
        self.assertLess(
            faction.resource_effective_access[RESOURCE_COPPER],
            faction.resource_gross_output[RESOURCE_COPPER],
        )
        self.assertGreater(world.regions["C"].resource_isolation_factor, 0.0)
        self.assertEqual(world.regions["C"].resource_route_anchor, "A")
        self.assertEqual(world.regions["C"].resource_route_depth, 2)
        self.assertLess(world.regions["C"].resource_route_bottleneck, 1.0)

    def test_domestic_resources_decay_under_crisis_and_neglect(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=35,
            terrain_tags=["plains", "steppe"],
            climate="temperate",
            unrest=8.8,
            unrest_event_level="crisis",
            integration_score=1.0,
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_GRAIN] = 0.7
        region.resource_established[RESOURCE_HORSES] = 0.4
        region.agriculture_level = 0.0
        region.pastoral_level = 0.0

        advance_region_domesticable_resources(region)

        self.assertLess(region.resource_established[RESOURCE_GRAIN], 0.7)
        self.assertLess(region.resource_established[RESOURCE_HORSES], 0.4)

    def test_introduction_requires_connected_owned_source(self):
        source = Region(
            name="A",
            neighbors=["B"],
            owner="FactionA",
            resources=2,
            population=140,
            terrain_tags=["plains"],
            climate="temperate",
        )
        blocker = Region(
            name="B",
            neighbors=["A", "C"],
            owner=None,
            resources=2,
            population=0,
            terrain_tags=["plains"],
            climate="temperate",
        )
        target = Region(
            name="C",
            neighbors=["B"],
            owner="FactionA",
            resources=2,
            population=120,
            terrain_tags=["plains"],
            climate="temperate",
        )
        for region in (source, blocker, target):
            seed_region_resource_profile(region)
        target.resource_established[RESOURCE_GRAIN] = 0.0

        world = WorldState(
            regions={"A": source, "B": blocker, "C": target},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        components = get_invest_target_score_components("C", "FactionA", world)

        self.assertNotEqual(components["project_type"], "introduce_grain")

    def test_route_quality_changes_distribution_efficiency(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B", "E"],
                    owner="FactionA",
                    resources=2,
                    population=180,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.2,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=160,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=7.0,
                    settlement_level="town",
                    infrastructure_level=1.4,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["hills"],
                    climate="temperate",
                    integration_score=2.0,
                    settlement_level="rural",
                ),
                "E": Region(
                    name="E",
                    neighbors=["A", "D"],
                    owner="FactionA",
                    resources=2,
                    population=55,
                    terrain_tags=["forest"],
                    climate="cold",
                    integration_score=1.5,
                    settlement_level="wild",
                    unrest=6.0,
                ),
                "D": Region(
                    name="D",
                    neighbors=["E"],
                    owner="FactionA",
                    resources=2,
                    population=110,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.0,
                    settlement_level="wild",
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)

        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 0.9
        world.regions["D"].resource_fixed_endowments[RESOURCE_COPPER] = 0.9

        update_faction_resource_economy(world)

        connected_region = world.regions["C"]
        degraded_region = world.regions["D"]

        self.assertLess(connected_region.resource_route_cost, degraded_region.resource_route_cost)
        self.assertLess(connected_region.resource_isolation_factor, degraded_region.resource_isolation_factor)
        self.assertGreater(connected_region.resource_route_bottleneck, degraded_region.resource_route_bottleneck)
        self.assertGreater(
            connected_region.resource_effective_output[RESOURCE_COPPER],
            degraded_region.resource_effective_output[RESOURCE_COPPER],
        )

    def test_bottlenecked_corridor_prefers_infrastructure_investment(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=180,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.3,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=45,
                    terrain_tags=["forest"],
                    climate="cold",
                    integration_score=1.2,
                    settlement_level="wild",
                    unrest=7.0,
                    infrastructure_level=0.0,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    integration_score=2.0,
                    settlement_level="rural",
                    infrastructure_level=0.0,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)

        world.regions["C"].resource_established[RESOURCE_GRAIN] = 0.0
        world.regions["C"].resource_established[RESOURCE_HORSES] = 0.0

        update_faction_resource_economy(world)
        components = get_invest_target_score_components("B", "FactionA", world)

        self.assertEqual(components["project_type"], "improve_infrastructure")
        self.assertLess(world.regions["B"].resource_route_bottleneck, 0.7)


if __name__ == "__main__":
    unittest.main()
