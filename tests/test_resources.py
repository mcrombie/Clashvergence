import unittest
from unittest.mock import patch

from src.actions import (
    attack,
    develop,
    get_attack_target_score_components,
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
from src.metrics import build_turn_metrics
from src.models import Faction, Region, RelationshipState, WorldState
from src.resources import (
    CAPACITY_CONSTRUCTION,
    CAPACITY_METAL,
    PRODUCED_GOOD_TOOLS,
    PRODUCED_GOOD_URBAN_SURPLUS,
    RESOURCE_COPPER,
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    RESOURCE_LIVESTOCK,
    RESOURCE_SALT,
    RESOURCE_STONE,
    RESOURCE_TIMBER,
    RESOURCE_TEXTILES,
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

    def test_region_profiles_seed_livestock_salt_and_textiles_by_geography(self):
        plains_region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            terrain_tags=["plains"],
            climate="temperate",
        )
        coastal_region = Region(
            name="B",
            neighbors=[],
            owner="FactionA",
            resources=2,
            terrain_tags=["coast"],
            climate="oceanic",
        )
        highland_region = Region(
            name="C",
            neighbors=[],
            owner="FactionA",
            resources=2,
            terrain_tags=["highland"],
            climate="cold",
        )
        for region in (plains_region, coastal_region, highland_region):
            seed_region_resource_profile(region)

        self.assertGreater(
            plains_region.resource_suitability[RESOURCE_LIVESTOCK],
            highland_region.resource_suitability[RESOURCE_LIVESTOCK],
        )
        self.assertGreater(
            coastal_region.resource_fixed_endowments[RESOURCE_SALT],
            plains_region.resource_fixed_endowments[RESOURCE_SALT],
        )
        self.assertGreater(
            coastal_region.resource_suitability[RESOURCE_TEXTILES],
            highland_region.resource_suitability[RESOURCE_TEXTILES],
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

    def test_develop_can_introduce_livestock_into_suitable_owned_neighbor(self):
        source = Region(
            name="A",
            neighbors=["B"],
            owner="FactionA",
            resources=2,
            population=140,
            terrain_tags=["plains", "steppe"],
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
        target.resource_established[RESOURCE_LIVESTOCK] = 0.0
        target.resource_established[RESOURCE_HORSES] = 0.0

        world = WorldState(
            regions={"A": source, "B": target},
            factions={"FactionA": Faction(name="FactionA")},
        )
        update_faction_resource_economy(world)

        components = get_development_target_score_components("B", "FactionA", world)

        self.assertIn(
            components["project_type"],
            {"introduce_grain", "introduce_livestock"},
        )
        if components["project_type"] == "introduce_livestock":
            self.assertTrue(develop("FactionA", "B", world))
            self.assertGreater(world.regions["B"].resource_established[RESOURCE_LIVESTOCK], 0.0)
            self.assertEqual(world.events[-1].details["project_type"], "introduce_livestock")

    def test_resource_economy_populates_access_capacities_and_shortages(self):
        world = create_world(map_name="seven_region_ring", num_factions=3)

        update_faction_resource_economy(world)
        faction = next(iter(world.factions.values()))

        self.assertIn(RESOURCE_GRAIN, faction.resource_access)
        self.assertIn("food_security", faction.derived_capacity)
        self.assertIn("metal_capacity", faction.resource_shortages)
        self.assertGreaterEqual(faction.derived_capacity["food_security"], 0.0)

    def test_tools_chain_uses_copper_and_material_inputs(self):
        copper_region = Region(
            name="A",
            neighbors=["B"],
            owner="FactionA",
            resources=2,
            population=220,
            terrain_tags=["highland"],
            climate="temperate",
            settlement_level="town",
            infrastructure_level=1.1,
            market_level=0.9,
            road_level=0.6,
            copper_mine_level=1.6,
        )
        timber_region = Region(
            name="B",
            neighbors=["A"],
            owner="FactionA",
            resources=2,
            population=140,
            terrain_tags=["forest"],
            climate="temperate",
            settlement_level="rural",
            logging_camp_level=1.4,
        )
        world = WorldState(
            regions={"A": copper_region, "B": timber_region},
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["A"].resource_fixed_endowments[RESOURCE_COPPER] = 1.4
        world.regions["B"].resource_wild_endowments[RESOURCE_TIMBER] = 1.1

        update_faction_resource_economy(world)

        faction = world.factions["FactionA"]
        self.assertGreater(faction.produced_goods[PRODUCED_GOOD_TOOLS], 0.0)
        self.assertGreater(
            faction.derived_capacity[CAPACITY_CONSTRUCTION],
            faction.resource_effective_access[RESOURCE_TIMBER]
            + faction.resource_effective_access[RESOURCE_STONE],
        )
        self.assertGreater(
            faction.derived_capacity[CAPACITY_METAL],
            faction.resource_effective_access[RESOURCE_COPPER],
        )

    def test_urban_surplus_chain_uses_food_salt_and_town_population(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=180,
            terrain_tags=["coast", "riverland"],
            climate="oceanic",
            settlement_level="town",
            infrastructure_level=1.0,
            market_level=1.1,
            storehouse_level=0.8,
            road_level=0.5,
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_GRAIN] = 0.85
        region.resource_established[RESOURCE_LIVESTOCK] = 0.55
        region.resource_fixed_endowments[RESOURCE_SALT] = 1.1
        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )

        update_faction_resource_economy(world)

        faction = world.factions["FactionA"]
        self.assertGreater(faction.produced_goods[PRODUCED_GOOD_URBAN_SURPLUS], 0.0)
        self.assertIn(PRODUCED_GOOD_URBAN_SURPLUS, faction.production_chain_shortages)

    def test_production_chain_shortages_track_missing_inputs(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=260,
            terrain_tags=["highland"],
            climate="cold",
            settlement_level="city",
            infrastructure_level=0.8,
            market_level=0.8,
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_GRAIN] = 0.0
        region.resource_established[RESOURCE_LIVESTOCK] = 0.0
        region.resource_fixed_endowments[RESOURCE_COPPER] = 0.0
        region.resource_wild_endowments[RESOURCE_TIMBER] = 0.0
        world = WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )

        update_faction_resource_economy(world)

        faction = world.factions["FactionA"]
        self.assertGreater(
            faction.production_chain_shortages[PRODUCED_GOOD_URBAN_SURPLUS],
            0.0,
        )
        self.assertGreater(
            faction.production_chain_shortages[PRODUCED_GOOD_TOOLS],
            0.0,
        )

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
            population=70,
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

    def test_internal_trade_routes_classify_hub_corridor_and_terminal_regions(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.2,
                    market_level=1.0,
                    road_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=150,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    integration_score=5.5,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    road_level=0.9,
                    market_level=0.4,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.4,
                    settlement_level="rural",
                    copper_mine_level=1.4,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 1.15

        update_faction_resource_economy(world)

        self.assertEqual(world.regions["A"].trade_route_role, "hub")
        self.assertEqual(world.regions["B"].trade_route_role, "corridor")
        self.assertEqual(world.regions["C"].trade_route_role, "terminal")
        self.assertGreater(world.regions["B"].trade_throughput, sum(world.regions["B"].resource_routed_output.values()))
        self.assertGreater(world.regions["B"].trade_transit_flow, 0.0)
        self.assertGreater(world.regions["A"].trade_hub_value, 0.0)

    def test_trade_bonus_and_imports_drop_when_corridor_breaks_down(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.2,
                    market_level=1.0,
                    road_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=150,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    integration_score=5.0,
                    settlement_level="town",
                    infrastructure_level=0.9,
                    road_level=0.8,
                    market_level=0.5,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=140,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.1,
                    settlement_level="rural",
                    copper_mine_level=1.5,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 1.2

        update_faction_resource_economy(world)
        baseline_import_value = world.regions["C"].trade_import_value
        baseline_trade_bonus = world.regions["C"].trade_value_bonus
        baseline_income = world.factions["FactionA"].trade_income

        world.regions["B"].unrest = 8.2
        world.regions["B"].unrest_event_level = "crisis"
        world.regions["B"].resource_damage[RESOURCE_TIMBER] = 0.65
        world.regions["B"].resource_damage[RESOURCE_COPPER] = 0.65
        update_faction_resource_economy(world)

        self.assertLess(world.regions["C"].trade_import_value, baseline_import_value)
        self.assertLess(world.regions["C"].trade_value_bonus, baseline_trade_bonus)
        self.assertLess(world.factions["FactionA"].trade_income, baseline_income)
        self.assertGreater(world.regions["C"].trade_disruption_risk, 0.0)

    def test_contested_border_pressure_degrades_internal_trade_corridors(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.2,
                    market_level=0.8,
                    road_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C", "D"],
                    owner="FactionA",
                    resources=2,
                    population=130,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=2.2,
                    settlement_level="rural",
                    infrastructure_level=0.6,
                    road_level=0.5,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.2,
                    settlement_level="rural",
                    copper_mine_level=1.5,
                ),
                "D": Region(
                    name="D",
                    neighbors=["B"],
                    owner="FactionB",
                    resources=2,
                    population=150,
                    terrain_tags=["plains"],
                    climate="temperate",
                    settlement_level="town",
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 1.2

        update_faction_resource_economy(world)
        baseline_cost = world.regions["C"].resource_route_cost
        baseline_bottleneck = world.regions["C"].resource_route_bottleneck
        baseline_risk = world.regions["C"].trade_disruption_risk

        world.turn = 5
        world.relationships = {
            ("FactionA", "FactionB"): RelationshipState(
                status="rival",
                border_friction=9.0,
                grievance=5.0,
                trust=-2.0,
                last_conflict_turn=4,
            )
        }
        update_faction_resource_economy(world)

        self.assertGreater(world.regions["C"].resource_route_cost, baseline_cost)
        self.assertLess(world.regions["C"].resource_route_bottleneck, baseline_bottleneck)
        self.assertGreater(world.regions["C"].trade_disruption_risk, baseline_risk)
        self.assertGreater(world.factions["FactionA"].trade_corridor_exposure, 0.0)

    def test_contested_crisis_port_blocks_maritime_trade_route(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.8,
                    road_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=120,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=2.2,
                    settlement_level="rural",
                ),
                "C": Region(
                    name="C",
                    neighbors=["B", "D"],
                    owner="FactionA",
                    resources=2,
                    population=105,
                    terrain_tags=["forest"],
                    climate="temperate",
                    integration_score=1.8,
                    settlement_level="rural",
                ),
                "D": Region(
                    name="D",
                    neighbors=["C", "E"],
                    owner="FactionA",
                    resources=2,
                    population=180,
                    terrain_tags=["coast", "forest"],
                    climate="oceanic",
                    integration_score=4.6,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.7,
                    road_level=0.6,
                    copper_mine_level=1.4,
                ),
                "E": Region(
                    name="E",
                    neighbors=["D"],
                    owner="FactionB",
                    resources=2,
                    population=150,
                    terrain_tags=["plains"],
                    climate="temperate",
                    settlement_level="town",
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
            sea_links=[("A", "D")],
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["D"].resource_fixed_endowments[RESOURCE_COPPER] = 1.15

        update_faction_resource_economy(world)
        self.assertEqual(world.regions["D"].resource_route_mode, "sea")

        world.turn = 7
        world.regions["D"].unrest = 8.1
        world.regions["D"].unrest_event_level = "crisis"
        world.relationships = {
            ("FactionA", "FactionB"): RelationshipState(
                status="rival",
                border_friction=12.0,
                grievance=6.0,
                last_conflict_turn=6,
            )
        }
        update_faction_resource_economy(world)

        self.assertEqual(world.regions["D"].resource_route_mode, "land")
        self.assertGreater(world.regions["D"].resource_route_cost, 2.0)
        self.assertGreater(world.regions["D"].trade_disruption_risk, 0.2)

    def test_alliance_border_trade_improves_foreign_resource_access(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.7,
                    road_level=0.7,
                    copper_mine_level=1.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=2,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=0.8,
                    market_level=0.6,
                    road_level=0.6,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["A"].resource_fixed_endowments[RESOURCE_COPPER] = 1.35
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 0.0

        update_faction_resource_economy(world)
        baseline_access = world.factions["FactionB"].resource_effective_access[RESOURCE_COPPER]
        baseline_shortage = world.factions["FactionB"].resource_shortages[RESOURCE_COPPER]
        baseline_trade_income = world.factions["FactionA"].trade_income

        world.relationships = {
            ("FactionA", "FactionB"): RelationshipState(
                status="alliance",
                trust=9.0,
            )
        }
        update_faction_resource_economy(world)

        self.assertGreater(
            world.factions["FactionB"].resource_effective_access[RESOURCE_COPPER],
            baseline_access,
        )
        self.assertLess(
            world.factions["FactionB"].resource_shortages[RESOURCE_COPPER],
            baseline_shortage,
        )
        self.assertGreater(world.factions["FactionA"].trade_income, baseline_trade_income)
        self.assertEqual(world.regions["A"].trade_gateway_role, "border_gateway")
        self.assertEqual(world.regions["B"].trade_gateway_role, "border_gateway")
        self.assertEqual(world.regions["A"].trade_foreign_partner, "FactionB")
        self.assertEqual(world.regions["A"].trade_foreign_partner_region, "B")
        self.assertGreater(world.regions["A"].trade_foreign_flow, 0.0)
        self.assertGreater(world.factions["FactionA"].trade_foreign_income, 0.0)

    def test_pact_based_maritime_foreign_trade_ends_when_relations_turn_rival(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=[],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.8,
                    road_level=0.6,
                    copper_mine_level=1.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=[],
                    owner="FactionB",
                    resources=2,
                    population=210,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.8,
                    road_level=0.6,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
            sea_links=[("A", "B")],
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["A"].resource_fixed_endowments[RESOURCE_COPPER] = 1.3
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 0.0
        world.relationships = {
            ("FactionA", "FactionB"): RelationshipState(
                status="non_aggression_pact",
                trust=5.0,
            )
        }

        update_faction_resource_economy(world)
        pact_access = world.factions["FactionB"].resource_effective_access[RESOURCE_COPPER]
        self.assertGreater(pact_access, 0.0)
        self.assertEqual(world.regions["A"].trade_gateway_role, "sea_gateway")
        self.assertEqual(world.regions["B"].trade_gateway_role, "sea_gateway")
        self.assertEqual(world.regions["A"].trade_foreign_partner_region, "B")
        self.assertGreater(world.regions["B"].trade_foreign_value, 0.0)

        world.turn = 6
        world.relationships = {
            ("FactionA", "FactionB"): RelationshipState(
                status="rival",
                border_friction=8.0,
                grievance=5.0,
                last_conflict_turn=5,
            )
        }
        update_faction_resource_economy(world)

        self.assertLess(
            world.factions["FactionB"].resource_effective_access[RESOURCE_COPPER],
            pact_access,
        )
        self.assertEqual(world.regions["A"].trade_gateway_role, "none")
        self.assertEqual(world.regions["B"].trade_gateway_role, "none")

    def test_attack_scoring_values_foreign_trade_gateway_regions(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B", "D"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.7,
                    road_level=0.7,
                    copper_mine_level=1.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionB",
                    resources=2,
                    population=210,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=0.9,
                    market_level=0.7,
                    road_level=0.7,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionB",
                    resources=2,
                    population=140,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.2,
                    settlement_level="rural",
                ),
                "D": Region(
                    name="D",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=2,
                    population=170,
                    terrain_tags=["plains"],
                    climate="temperate",
                    settlement_level="town",
                    infrastructure_level=0.8,
                    market_level=0.3,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=8),
                "FactionB": Faction(name="FactionB", treasury=8),
            },
            sea_links=[("A", "B")],
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["A"].resource_fixed_endowments[RESOURCE_COPPER] = 1.35
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 0.0
        world.relationships = {
            ("FactionA", "FactionB"): RelationshipState(
                status="alliance",
                trust=8.0,
            )
        }

        update_faction_resource_economy(world)
        gateway_target = get_attack_target_score_components("B", "FactionA", world)
        non_gateway_target = get_attack_target_score_components("D", "FactionA", world)

        self.assertGreater(gateway_target["foreign_gateway_bonus"], non_gateway_target["foreign_gateway_bonus"])
        self.assertGreater(gateway_target["score"], non_gateway_target["score"])

    def test_foreign_trade_gateway_feeds_inland_corridor_throughput(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.8,
                    road_level=0.8,
                    copper_mine_level=1.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C", "D"],
                    owner="FactionA",
                    resources=2,
                    population=150,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    integration_score=5.0,
                    settlement_level="town",
                    infrastructure_level=0.9,
                    road_level=0.8,
                    market_level=0.5,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=140,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.1,
                    settlement_level="rural",
                ),
                "D": Region(
                    name="D",
                    neighbors=["B"],
                    owner="FactionB",
                    resources=2,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=0.8,
                    market_level=0.6,
                    road_level=0.6,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["A"].resource_fixed_endowments[RESOURCE_COPPER] = 1.35
        world.regions["D"].resource_fixed_endowments[RESOURCE_COPPER] = 0.0

        update_faction_resource_economy(world)
        baseline_a_throughput = world.regions["A"].trade_throughput
        baseline_a_value = world.regions["A"].trade_value_bonus

        world.relationships = {
            ("FactionA", "FactionB"): RelationshipState(
                status="alliance",
                trust=8.0,
            )
        }
        update_faction_resource_economy(world)

        self.assertEqual(world.regions["B"].trade_gateway_role, "border_gateway")
        self.assertGreater(world.regions["B"].trade_foreign_flow, 0.0)
        self.assertGreater(world.regions["A"].trade_throughput, baseline_a_throughput)
        self.assertGreater(world.regions["A"].trade_value_bonus, baseline_a_value)

    def test_failed_attack_can_trigger_trade_warfare_on_enemy_corridor(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.7,
                    road_level=0.7,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C", "D"],
                    owner="FactionB",
                    resources=2,
                    population=150,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionB",
                    integration_score=5.0,
                    settlement_level="town",
                    infrastructure_level=0.9,
                    market_level=0.6,
                    road_level=0.8,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionB",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.8,
                    road_level=0.7,
                ),
                "D": Region(
                    name="D",
                    neighbors=["B"],
                    owner="FactionB",
                    resources=2,
                    population=135,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.2,
                    settlement_level="rural",
                    copper_mine_level=1.6,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=10),
                "FactionB": Faction(name="FactionB", treasury=10),
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["D"].resource_fixed_endowments[RESOURCE_COPPER] = 1.25

        update_faction_resource_economy(world)
        baseline_income = world.factions["FactionB"].trade_income

        with patch("src.actions.random.random", return_value=0.999):
            succeeded = attack("FactionA", "B", world)

        self.assertFalse(succeeded)
        update_faction_resource_economy(world)

        self.assertGreater(world.regions["B"].trade_warfare_pressure, 0.0)
        self.assertGreater(world.regions["B"].trade_warfare_turns, 0)
        self.assertGreater(world.regions["B"].trade_value_denied, 0.0)
        self.assertGreater(world.factions["FactionB"].trade_warfare_damage, 0.0)
        self.assertLess(world.factions["FactionB"].trade_income, baseline_income)

    def test_attack_on_port_can_blockade_maritime_foreign_trade(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.7,
                    road_level=0.7,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=3,
                    population=220,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.8,
                    road_level=0.6,
                    copper_mine_level=1.7,
                ),
                "C": Region(
                    name="C",
                    neighbors=[],
                    owner="FactionC",
                    resources=2,
                    population=210,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionC",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.8,
                    road_level=0.6,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=10),
                "FactionB": Faction(name="FactionB", treasury=10),
                "FactionC": Faction(name="FactionC", treasury=10),
            },
            sea_links=[("B", "C")],
            relationships={
                ("FactionB", "FactionC"): RelationshipState(
                    status="non_aggression_pact",
                    trust=5.0,
                )
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 1.3
        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 0.0

        update_faction_resource_economy(world)
        baseline_copper_access = world.factions["FactionC"].resource_effective_access[RESOURCE_COPPER]
        self.assertEqual(world.regions["B"].trade_gateway_role, "sea_gateway")

        with patch("src.actions.random.random", return_value=0.999):
            succeeded = attack("FactionA", "B", world)

        self.assertFalse(succeeded)
        update_faction_resource_economy(world)

        self.assertGreater(world.regions["B"].trade_blockade_strength, 0.0)
        self.assertGreater(world.regions["B"].trade_blockade_turns, 0)
        self.assertEqual(world.regions["B"].trade_gateway_role, "none")
        self.assertEqual(world.regions["C"].trade_gateway_role, "none")
        self.assertLess(
            world.factions["FactionC"].resource_effective_access[RESOURCE_COPPER],
            baseline_copper_access,
        )
        self.assertGreater(world.factions["FactionB"].trade_blockade_losses, 0.0)

    def test_metrics_include_trade_warfare_and_blockade_losses(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.7,
                    road_level=0.7,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=3,
                    population=220,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.8,
                    road_level=0.6,
                    copper_mine_level=1.7,
                ),
                "C": Region(
                    name="C",
                    neighbors=[],
                    owner="FactionC",
                    resources=2,
                    population=210,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionC",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.8,
                    road_level=0.6,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=10),
                "FactionB": Faction(name="FactionB", treasury=10),
                "FactionC": Faction(name="FactionC", treasury=10),
            },
            sea_links=[("B", "C")],
            relationships={
                ("FactionB", "FactionC"): RelationshipState(
                    status="alliance",
                    trust=7.0,
                )
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 1.3
        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 0.0

        update_faction_resource_economy(world)
        with patch("src.actions.random.random", return_value=0.999):
            attack("FactionA", "B", world)
        update_faction_resource_economy(world)

        metrics = build_turn_metrics(world)
        faction_metrics = metrics["factions"]["FactionB"]
        self.assertIn("trade_warfare_damage", faction_metrics)
        self.assertIn("trade_blockade_losses", faction_metrics)
        self.assertGreater(faction_metrics["trade_warfare_damage"], 0.0)
        self.assertGreater(faction_metrics["trade_blockade_losses"], 0.0)

    def test_metrics_include_trade_fields_from_internal_routes(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.2,
                    market_level=1.0,
                    road_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionA",
                    resources=2,
                    population=140,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.2,
                    settlement_level="rural",
                    copper_mine_level=1.5,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 1.2

        update_faction_resource_economy(world)
        metrics = build_turn_metrics(world)
        faction_metrics = metrics["factions"]["FactionA"]

        self.assertIn("trade_income", faction_metrics)
        self.assertIn("trade_import_dependency", faction_metrics)
        self.assertIn("trade_corridor_exposure", faction_metrics)
        self.assertIn("trade_foreign_income", faction_metrics)
        self.assertIn("trade_foreign_imported_flow", faction_metrics)
        self.assertGreater(world.factions["FactionA"].trade_income, 0.0)
        self.assertGreaterEqual(faction_metrics["trade_import_dependency"], 0.0)

    def test_attack_scoring_values_enemy_trade_chokepoints(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B", "E"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.2,
                    market_level=0.9,
                    road_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionB",
                    resources=2,
                    population=150,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.7,
                    road_level=0.8,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B", "D"],
                    owner="FactionB",
                    resources=2,
                    population=130,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=2.3,
                    settlement_level="rural",
                    infrastructure_level=0.5,
                    road_level=0.4,
                ),
                "D": Region(
                    name="D",
                    neighbors=["C"],
                    owner="FactionB",
                    resources=2,
                    population=140,
                    terrain_tags=["highland"],
                    climate="cold",
                    integration_score=1.1,
                    settlement_level="rural",
                    copper_mine_level=1.5,
                ),
                "E": Region(
                    name="E",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=2,
                    population=150,
                    terrain_tags=["plains"],
                    climate="temperate",
                    homeland_faction_id="FactionB",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.7,
                    road_level=0.8,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=8),
                "FactionB": Faction(name="FactionB", treasury=8),
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["D"].resource_fixed_endowments[RESOURCE_COPPER] = 1.2

        update_faction_resource_economy(world)
        corridor_target = get_attack_target_score_components("B", "FactionA", world)
        local_target = get_attack_target_score_components("E", "FactionA", world)

        self.assertGreater(corridor_target["trade_chokepoint_bonus"], local_target["trade_chokepoint_bonus"])
        self.assertGreater(corridor_target["score"], local_target["score"])

    def test_coastal_ports_can_use_sea_links_for_internal_trade_routes(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=220,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=1.1,
                    market_level=0.8,
                    road_level=0.8,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=110,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=2.4,
                    settlement_level="rural",
                ),
                "C": Region(
                    name="C",
                    neighbors=["B", "D"],
                    owner="FactionA",
                    resources=2,
                    population=105,
                    terrain_tags=["forest"],
                    climate="temperate",
                    integration_score=1.8,
                    settlement_level="rural",
                ),
                "D": Region(
                    name="D",
                    neighbors=["C"],
                    owner="FactionA",
                    resources=2,
                    population=180,
                    terrain_tags=["coast", "forest"],
                    climate="oceanic",
                    integration_score=4.6,
                    settlement_level="town",
                    infrastructure_level=1.0,
                    market_level=0.7,
                    road_level=0.6,
                    copper_mine_level=1.4,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
            sea_links=[("A", "D")],
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["D"].resource_fixed_endowments[RESOURCE_COPPER] = 1.15

        update_faction_resource_economy(world)

        self.assertEqual(world.regions["D"].resource_route_mode, "sea")
        self.assertLess(world.regions["D"].resource_route_cost, 2.3)
        self.assertGreater(world.regions["A"].trade_hub_value, 0.0)
        self.assertGreater(world.factions["FactionA"].trade_income, 0.0)

    def test_river_ports_can_use_river_links_for_internal_trade_routes(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=170,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                    settlement_level="town",
                    infrastructure_level=0.9,
                    market_level=0.5,
                    road_level=0.5,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner="FactionA",
                    resources=2,
                    population=130,
                    terrain_tags=["plains"],
                    climate="temperate",
                    integration_score=4.2,
                    settlement_level="town",
                    infrastructure_level=0.4,
                    market_level=0.25,
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    population=160,
                    terrain_tags=["riverland", "forest"],
                    climate="temperate",
                    integration_score=3.4,
                    settlement_level="town",
                    infrastructure_level=0.8,
                    market_level=0.45,
                    copper_mine_level=1.3,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
            river_links=[("A", "B"), ("B", "C")],
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["C"].resource_fixed_endowments[RESOURCE_COPPER] = 1.1

        update_faction_resource_economy(world)

        self.assertEqual(world.regions["C"].resource_route_mode, "river")
        self.assertLess(world.regions["C"].resource_route_cost, 1.8)
        self.assertGreater(world.regions["A"].trade_hub_value, 0.0)
        self.assertGreater(world.factions["FactionA"].trade_income, 0.0)

    def test_world_creation_populates_coastal_sea_links_from_map_definition(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)

        self.assertTrue(world.sea_links)
        self.assertIn(("A", "E"), world.sea_links)
        self.assertIn(("E", "I"), world.sea_links)

    def test_world_creation_populates_river_links_from_map_definition(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)

        self.assertTrue(world.river_links)
        self.assertIn(("A", "M"), world.river_links)
        self.assertIn(("L", "M"), world.river_links)

    def test_pact_based_river_foreign_trade_uses_river_gateway(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=200,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    settlement_level="town",
                    infrastructure_level=0.9,
                    market_level=0.6,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=2,
                    population=180,
                    terrain_tags=["riverland", "forest"],
                    climate="temperate",
                    settlement_level="town",
                    infrastructure_level=0.8,
                    market_level=0.55,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
            river_links=[("A", "B")],
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["A"].resource_fixed_endowments[RESOURCE_COPPER] = 1.3
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 0.0
        world.relationships[("FactionA", "FactionB")] = RelationshipState(
            score=22.0,
            status="non_aggression_pact",
            years_at_peace=3,
            trust=18.0,
        )

        update_faction_resource_economy(world)

        self.assertEqual(world.regions["A"].trade_gateway_role, "river_gateway")
        self.assertEqual(world.regions["B"].trade_gateway_role, "river_gateway")
        self.assertGreater(world.factions["FactionB"].trade_foreign_imported_flow, 0.0)
        self.assertGreater(world.factions["FactionB"].trade_foreign_income, 0.0)

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
