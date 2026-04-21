import unittest

from src.actions import (
    develop,
    get_developable_regions,
    get_development_target_score_components,
    get_invest_target_score_components,
    invest,
)
from src.resource_economy import (
    advance_region_domesticable_resources,
    apply_turn_food_economy,
    get_faction_food_storage_capacity,
    get_region_food_storage_capacity,
    get_region_taxable_value,
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
    RESOURCE_TIMBER,
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

    def test_develop_can_introduce_grain_into_suitable_owned_neighbor(self):
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

        components = get_development_target_score_components("B", "FactionA", world)

        self.assertEqual(components["project_type"], "introduce_grain")
        self.assertTrue(develop("FactionA", "B", world))
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

    def test_granary_increases_faction_food_storage_capacity(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=140,
            terrain_tags=["plains"],
            climate="temperate",
            settlement_level="town",
        )
        seed_region_resource_profile(region)
        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )

        base_capacity = get_faction_food_storage_capacity(world, "FactionA")
        region.granary_level = 0.8
        region.infrastructure_level = 0.6
        region.agriculture_level = 0.5
        expanded_capacity = get_faction_food_storage_capacity(world, "FactionA")

        self.assertGreater(expanded_capacity, base_capacity)
        self.assertGreater(get_region_food_storage_capacity(region), 0.0)

    def test_develop_can_build_granary_when_food_storage_is_tight(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=190,
            terrain_tags=["plains"],
            climate="temperate",
            settlement_level="town",
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_GRAIN] = 0.55
        region.agriculture_level = 1.8

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)
        world.factions["FactionA"].food_consumption = 3.0
        world.factions["FactionA"].food_storage_capacity = 0.0
        world.factions["FactionA"].food_overflow = 0.4

        components = get_development_target_score_components("A", "FactionA", world)

        self.assertEqual(components["project_type"], "build_granary")
        self.assertTrue(develop("FactionA", "A", world))
        self.assertGreater(world.regions["A"].granary_level, 0.0)
        self.assertEqual(world.events[-1].details["project_type"], "build_granary")

    def test_region_food_deficits_are_local_not_faction_shared(self):
        abundant = Region(
            name="A",
            neighbors=["B"],
            owner="FactionA",
            resources=2,
            population=80,
            terrain_tags=["riverland"],
            climate="temperate",
            settlement_level="town",
        )
        hungry = Region(
            name="B",
            neighbors=["A"],
            owner="FactionA",
            resources=2,
            population=320,
            terrain_tags=["highland"],
            climate="cold",
            settlement_level="rural",
        )
        for region in (abundant, hungry):
            seed_region_resource_profile(region)
        abundant.resource_established[RESOURCE_GRAIN] = 0.8
        abundant.agriculture_level = 1.2
        abundant.granary_level = 1.0

        world = WorldState(
            regions={"A": abundant, "B": hungry},
            factions={"FactionA": Faction(name="FactionA")},
        )

        update_faction_resource_economy(world)
        apply_turn_food_economy(world)

        self.assertGreater(world.regions["A"].food_stored, 0.0)
        self.assertGreater(world.regions["B"].food_deficit, 0.0)
        self.assertGreater(world.factions["FactionA"].food_deficit, 0.0)

    def test_development_aliases_match_invest_flow(self):
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

        world = WorldState(
            regions={"A": source, "B": target},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        self.assertEqual(get_developable_regions("FactionA", world), ["A", "B"])
        self.assertEqual(
            get_development_target_score_components("B", "FactionA", world)["project_type"],
            get_invest_target_score_components("B", "FactionA", world)["project_type"],
        )
        self.assertTrue(develop("FactionA", "B", world))

    def test_develop_can_build_copper_mine_on_copper_deposit(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=140,
            terrain_tags=["highland"],
            climate="temperate",
        )
        seed_region_resource_profile(region)
        region.resource_fixed_endowments[RESOURCE_COPPER] = 1.2
        region.resource_fixed_endowments[RESOURCE_STONE] = 0.2

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        components = get_development_target_score_components("A", "FactionA", world)

        self.assertEqual(components["project_type"], "build_copper_mine")
        self.assertTrue(develop("FactionA", "A", world))
        self.assertGreater(world.regions["A"].copper_mine_level, 0.0)
        self.assertEqual(world.events[-1].details["project_type"], "build_copper_mine")

    def test_copper_mine_significantly_improves_copper_output(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=160,
            terrain_tags=["highland"],
            climate="temperate",
        )
        seed_region_resource_profile(region)
        region.resource_fixed_endowments[RESOURCE_COPPER] = 1.3

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)
        baseline_output = world.regions["A"].resource_output[RESOURCE_COPPER]

        world.regions["A"].copper_mine_level = 1.0
        update_faction_resource_economy(world)
        mined_output = world.regions["A"].resource_output[RESOURCE_COPPER]

        self.assertGreater(mined_output, baseline_output * 2)

    def test_develop_can_build_logging_camp_on_timber_region(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=150,
            terrain_tags=["forest"],
            climate="temperate",
        )
        seed_region_resource_profile(region)
        region.resource_wild_endowments[RESOURCE_TIMBER] = 1.1

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        components = get_development_target_score_components("A", "FactionA", world)

        self.assertEqual(components["project_type"], "build_logging_camp")
        self.assertTrue(develop("FactionA", "A", world))
        self.assertGreater(world.regions["A"].logging_camp_level, 0.0)

    def test_irrigation_significantly_improves_grain_output(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=160,
            terrain_tags=["riverland"],
            climate="temperate",
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_GRAIN] = 0.8

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)
        baseline_output = world.regions["A"].resource_output[RESOURCE_GRAIN]

        world.regions["A"].irrigation_level = 1.0
        update_faction_resource_economy(world)
        irrigated_output = world.regions["A"].resource_output[RESOURCE_GRAIN]

        self.assertGreater(irrigated_output, baseline_output * 1.4)

    def test_pasture_significantly_improves_horse_output(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=160,
            terrain_tags=["steppe"],
            climate="temperate",
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_HORSES] = 0.7

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)
        baseline_output = world.regions["A"].resource_output[RESOURCE_HORSES]

        world.regions["A"].pasture_level = 1.0
        update_faction_resource_economy(world)
        pastured_output = world.regions["A"].resource_output[RESOURCE_HORSES]

        self.assertGreater(pastured_output, baseline_output * 1.4)

    def test_road_level_improves_frontier_distribution(self):
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
                    population=110,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=1.2,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=110,
                    terrain_tags=["forest"],
                    climate="temperate",
                    integration_score=1.0,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["C"].resource_wild_endowments[RESOURCE_TIMBER] = 1.1

        update_faction_resource_economy(world)
        baseline_effective = world.regions["C"].resource_effective_output[RESOURCE_TIMBER]
        baseline_cost = world.regions["C"].resource_route_cost

        world.regions["B"].road_level = 1.0
        world.regions["C"].road_level = 1.0
        update_faction_resource_economy(world)

        self.assertGreater(world.regions["C"].resource_effective_output[RESOURCE_TIMBER], baseline_effective)
        self.assertLess(world.regions["C"].resource_route_cost, baseline_cost)

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

    def test_resource_pipeline_tracks_raw_retained_routed_and_monetized_stages(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=210,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.2,
                    market_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["highland", "forest"],
                    climate="cold",
                    integration_score=1.3,
                    settlement_level="rural",
                    copper_mine_level=1.2,
                    logging_camp_level=1.0,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 1.2
        world.regions["B"].resource_wild_endowments[RESOURCE_TIMBER] = 1.1

        update_faction_resource_economy(world)
        frontier = world.regions["B"]

        raw_total = sum(frontier.resource_output.values())
        retained_total = sum(frontier.resource_retained_output.values())
        routed_total = sum(frontier.resource_routed_output.values())

        self.assertGreater(raw_total, retained_total)
        self.assertGreater(retained_total, routed_total)
        self.assertGreater(frontier.resource_monetized_value, 0.0)

    def test_storehouse_improves_retained_output_for_material_region(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=150,
            terrain_tags=["highland", "forest"],
            climate="temperate",
            settlement_level="rural",
            copper_mine_level=1.4,
            logging_camp_level=1.2,
        )
        seed_region_resource_profile(region)
        region.resource_fixed_endowments[RESOURCE_COPPER] = 1.1
        region.resource_wild_endowments[RESOURCE_TIMBER] = 1.0

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)
        baseline_retained = (
            world.regions["A"].resource_retained_output[RESOURCE_COPPER]
            + world.regions["A"].resource_retained_output[RESOURCE_TIMBER]
        )

        world.regions["A"].storehouse_level = 1.0
        update_faction_resource_economy(world)
        stored_retained = (
            world.regions["A"].resource_retained_output[RESOURCE_COPPER]
            + world.regions["A"].resource_retained_output[RESOURCE_TIMBER]
        )

        self.assertGreater(stored_retained, baseline_retained)

    def test_market_improves_monetized_value_without_changing_routed_output(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=220,
            terrain_tags=["highland", "forest"],
            climate="temperate",
            settlement_level="town",
            infrastructure_level=1.1,
            road_level=1.0,
            storehouse_level=1.0,
            copper_mine_level=1.8,
            logging_camp_level=1.4,
        )
        seed_region_resource_profile(region)
        region.resource_fixed_endowments[RESOURCE_COPPER] = 1.2
        region.resource_wild_endowments[RESOURCE_TIMBER] = 1.0

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)
        baseline_routed = dict(world.regions["A"].resource_routed_output)
        baseline_taxable = get_region_taxable_value(world.regions["A"], world)

        world.regions["A"].market_level = 1.0
        update_faction_resource_economy(world)

        self.assertEqual(world.regions["A"].resource_routed_output, baseline_routed)
        self.assertGreater(get_region_taxable_value(world.regions["A"], world), baseline_taxable)

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

        components = get_development_target_score_components("C", "FactionA", world)

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

    def test_bottlenecked_corridor_prefers_road_development(self):
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
        components = get_development_target_score_components("B", "FactionA", world)

        self.assertEqual(components["project_type"], "build_road_station")
        self.assertLess(world.regions["B"].resource_route_bottleneck, 0.7)

    def test_develop_can_build_storehouse_for_material_frontier(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=140,
            terrain_tags=["highland", "forest"],
            climate="cold",
            settlement_level="rural",
            infrastructure_level=0.5,
            copper_mine_level=1.8,
            stone_quarry_level=1.8,
            logging_camp_level=1.8,
        )
        seed_region_resource_profile(region)
        region.resource_fixed_endowments[RESOURCE_COPPER] = 1.2
        region.resource_fixed_endowments[RESOURCE_STONE] = 1.0
        region.resource_wild_endowments[RESOURCE_TIMBER] = 1.0

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        components = get_development_target_score_components("A", "FactionA", world)

        self.assertEqual(components["project_type"], "build_storehouse")
        self.assertTrue(develop("FactionA", "A", world))
        self.assertGreater(world.regions["A"].storehouse_level, 0.0)

    def test_develop_can_build_market_in_connected_town(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=240,
            terrain_tags=["highland", "forest"],
            climate="temperate",
            settlement_level="town",
            infrastructure_level=1.2,
            road_level=1.0,
            storehouse_level=1.0,
            copper_mine_level=1.8,
            stone_quarry_level=1.8,
            logging_camp_level=1.6,
        )
        seed_region_resource_profile(region)
        region.resource_fixed_endowments[RESOURCE_COPPER] = 1.2
        region.resource_fixed_endowments[RESOURCE_STONE] = 1.0
        region.resource_wild_endowments[RESOURCE_TIMBER] = 1.0

        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        components = get_development_target_score_components("A", "FactionA", world)

        self.assertEqual(components["project_type"], "build_market")
        taxable_before = get_region_taxable_value(world.regions["A"], world)
        self.assertTrue(develop("FactionA", "A", world))
        self.assertGreater(world.regions["A"].market_level, 0.0)
        self.assertGreater(get_region_taxable_value(world.regions["A"], world), taxable_before)


if __name__ == "__main__":
    unittest.main()
