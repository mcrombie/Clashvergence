import unittest

from src.metrics import build_turn_metrics
from src.models import Faction, Region, WorldState
from src.administration import get_region_administrative_support
from src.resource_economy import update_faction_resource_economy
from src.resources import RESOURCE_COPPER, RESOURCE_STONE, RESOURCE_TIMBER
from src.urban import (
    URBAN_CAPITAL,
    URBAN_CRAFT_CENTER,
    URBAN_FRONTIER_FORT,
    URBAN_MINING_TOWN,
    URBAN_NONE,
    URBAN_PORT_CITY,
    URBAN_TEMPLE_CITY,
    update_urban_specializations,
)


class UrbanSpecializationTests(unittest.TestCase):
    def test_capital_assignment_prefers_core_city(self):
        capital = Region(
            name="Capital",
            neighbors=["Port"],
            owner="FactionA",
            resources=2,
            population=520,
            settlement_level="city",
            core_status="homeland",
            administrative_support=0.85,
            infrastructure_level=0.7,
            road_level=0.6,
            market_level=0.5,
            integration_score=8.0,
        )
        port = Region(
            name="Port",
            neighbors=["Capital"],
            owner="FactionA",
            resources=2,
            population=180,
            settlement_level="town",
            core_status="core",
            terrain_tags=["coast"],
            market_level=1.1,
            storehouse_level=0.8,
            trade_gateway_role="sea_gateway",
            trade_foreign_flow=1.2,
            trade_foreign_value=1.5,
        )
        world = WorldState(
            regions={"Capital": capital, "Port": port},
            factions={"FactionA": Faction(name="FactionA")},
        )

        update_urban_specializations(world)

        self.assertEqual(world.factions["FactionA"].capital_region, "Capital")
        self.assertEqual(capital.urban_specialization, URBAN_CAPITAL)
        self.assertEqual(port.urban_specialization, URBAN_PORT_CITY)
        self.assertGreater(world.factions["FactionA"].urban_network_value, 0.0)

    def test_mining_town_detects_extractives(self):
        capital = Region(
            name="Capital",
            neighbors=["Mine"],
            owner="FactionA",
            resources=2,
            population=420,
            settlement_level="city",
            core_status="homeland",
            administrative_support=0.9,
        )
        mine = Region(
            name="Mine",
            neighbors=["Capital"],
            owner="FactionA",
            resources=2,
            population=190,
            settlement_level="town",
            core_status="core",
            copper_mine_level=1.4,
            stone_quarry_level=0.8,
            extractive_level=0.7,
            resource_fixed_endowments={RESOURCE_COPPER: 1.2, RESOURCE_STONE: 0.8},
            resource_wild_endowments={RESOURCE_TIMBER: 0.4},
            resource_effective_output={RESOURCE_COPPER: 1.6, RESOURCE_STONE: 0.9},
        )
        world = WorldState(
            regions={"Capital": capital, "Mine": mine},
            factions={"FactionA": Faction(name="FactionA")},
        )

        update_urban_specializations(world)

        self.assertEqual(mine.urban_specialization, URBAN_MINING_TOWN)
        self.assertGreater(mine.urban_specialization_score, 0.0)

    def test_temple_city_detects_shrine_and_sacred_site(self):
        capital = Region(
            name="Capital",
            neighbors=["Temple"],
            owner="FactionA",
            resources=2,
            population=420,
            settlement_level="city",
            core_status="homeland",
            administrative_support=0.9,
        )
        temple = Region(
            name="Temple",
            neighbors=["Capital"],
            owner="FactionA",
            resources=2,
            population=210,
            settlement_level="town",
            core_status="core",
            sacred_religion="Ash Rite",
            shrine_level=1.2,
            pilgrimage_value=1.1,
        )
        world = WorldState(
            regions={"Capital": capital, "Temple": temple},
            factions={"FactionA": Faction(name="FactionA")},
        )

        update_urban_specializations(world)

        self.assertEqual(temple.urban_specialization, URBAN_TEMPLE_CITY)

    def test_metrics_include_urban_network_counts(self):
        capital = Region(
            name="Capital",
            neighbors=["Port"],
            owner="FactionA",
            resources=2,
            population=520,
            settlement_level="city",
            core_status="homeland",
            administrative_support=0.85,
            infrastructure_level=0.7,
        )
        port = Region(
            name="Port",
            neighbors=["Capital"],
            owner="FactionA",
            resources=2,
            population=180,
            settlement_level="town",
            core_status="core",
            terrain_tags=["coast"],
            market_level=1.1,
            storehouse_level=0.8,
            trade_gateway_role="sea_gateway",
            trade_foreign_flow=1.2,
        )
        world = WorldState(
            regions={"Capital": capital, "Port": port},
            factions={"FactionA": Faction(name="FactionA")},
        )

        update_urban_specializations(world)
        metrics = build_turn_metrics(world)["factions"]["FactionA"]

        self.assertEqual(metrics["capital_region"], "Capital")
        self.assertEqual(metrics["capital_regions"], 1)
        self.assertEqual(metrics["port_city_regions"], 1)
        self.assertGreater(metrics["urban_network_value"], 0.0)

    def test_frontier_fort_improves_administrative_support(self):
        region = Region(
            name="Fort",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=180,
            settlement_level="town",
            core_status="frontier",
            road_level=0.5,
            infrastructure_level=0.4,
        )
        region.urban_specialization = URBAN_NONE
        baseline_support = get_region_administrative_support(region)

        region.urban_specialization = URBAN_FRONTIER_FORT
        region.urban_network_value = 1.2
        boosted_support = get_region_administrative_support(region)

        self.assertGreater(boosted_support, baseline_support)

    def test_craft_center_boosts_tools_chain_output(self):
        region = Region(
            name="Workshop",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=240,
            settlement_level="town",
            core_status="core",
            infrastructure_level=0.8,
            market_level=0.8,
            storehouse_level=0.6,
            copper_mine_level=1.2,
            logging_camp_level=1.0,
            resource_fixed_endowments={RESOURCE_COPPER: 1.2},
            resource_wild_endowments={RESOURCE_TIMBER: 1.2},
        )
        world = WorldState(
            regions={"Workshop": region},
            factions={"FactionA": Faction(name="FactionA")},
        )

        region.urban_specialization = URBAN_NONE
        update_faction_resource_economy(world)
        baseline_tools = world.factions["FactionA"].produced_goods["tools"]

        region.urban_specialization = URBAN_CRAFT_CENTER
        region.urban_network_value = 1.4
        update_faction_resource_economy(world)
        boosted_tools = world.factions["FactionA"].produced_goods["tools"]

        self.assertGreater(boosted_tools, baseline_tools)


if __name__ == "__main__":
    unittest.main()
