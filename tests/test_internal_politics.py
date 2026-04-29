import unittest

from src.internal_politics import (
    BLOC_GUILDS,
    BLOC_MERCHANT_HOUSES,
    BLOC_NOBLES,
    BLOC_PRIESTHOOD,
    BLOC_PROVINCIAL_GOVERNORS,
    BLOC_URBAN_COMMONS,
    get_bloc,
    get_faction_elite_effects,
    initialize_elite_blocs,
    update_elite_blocs,
)
from src.metrics import build_turn_metrics
from src.models import EliteBloc, Faction, Region, WorldState
from src.resource_economy import update_faction_resource_economy
from src.resources import RESOURCE_COPPER, RESOURCE_TIMBER
from src.urban import URBAN_CRAFT_CENTER, URBAN_PORT_CITY, URBAN_TEMPLE_CITY


class InternalPoliticsTests(unittest.TestCase):
    def test_trade_and_urban_network_create_merchant_and_commons_blocs(self):
        port = Region(
            name="Port",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=360,
            settlement_level="city",
            urban_specialization=URBAN_PORT_CITY,
            market_level=1.2,
            trade_foreign_value=3.0,
            trade_value_bonus=2.5,
        )
        faction = Faction(name="FactionA", trade_income=8.0, urban_network_value=2.0)
        world = WorldState(regions={"Port": port}, factions={"FactionA": faction})

        initialize_elite_blocs(world)

        self.assertIsNotNone(get_bloc(faction, BLOC_MERCHANT_HOUSES))
        self.assertIsNotNone(get_bloc(faction, BLOC_URBAN_COMMONS))
        self.assertGreater(get_bloc(faction, BLOC_MERCHANT_HOUSES).influence, 0.2)

    def test_temple_city_and_clergy_create_priesthood_bloc(self):
        temple = Region(
            name="Temple",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=240,
            settlement_level="town",
            urban_specialization=URBAN_TEMPLE_CITY,
            sacred_religion="Ash Rite",
            shrine_level=1.2,
            pilgrimage_value=1.0,
        )
        faction = Faction(name="FactionA")
        faction.religion.official_religion = "Ash Rite"
        faction.religion.clergy_support = 0.72
        world = WorldState(regions={"Temple": temple}, factions={"FactionA": faction})

        initialize_elite_blocs(world)

        priesthood = get_bloc(faction, BLOC_PRIESTHOOD)
        self.assertIsNotNone(priesthood)
        self.assertGreater(priesthood.influence, 0.3)
        self.assertGreater(
            get_faction_elite_effects(faction)["religious_legitimacy_factor"],
            0.0,
        )

    def test_overextension_strengthens_governors_and_can_alienate_them(self):
        regions = {
            f"R{index}": Region(
                name=f"R{index}",
                neighbors=[],
                owner="FactionA",
                resources=2,
                population=160,
                settlement_level="rural",
                core_status="frontier",
                administrative_autonomy=0.6,
            )
            for index in range(6)
        }
        faction = Faction(name="FactionA")
        faction.administrative_overextension = 0.8
        faction.administrative_efficiency = 0.55
        world = WorldState(regions=regions, factions={"FactionA": faction})

        initialize_elite_blocs(world)
        update_elite_blocs(world, emit_events=False)

        governors = get_bloc(faction, BLOC_PROVINCIAL_GOVERNORS)
        self.assertIsNotNone(governors)
        self.assertGreater(governors.influence, 0.3)
        self.assertGreaterEqual(faction.elite_unrest_pressure, 0.0)

    def test_alienated_nobles_create_claimant_pressure_effect(self):
        faction = Faction(name="FactionA")
        faction.elite_blocs = [
            EliteBloc(
                bloc_type=BLOC_NOBLES,
                name="FactionA Nobles",
                influence=0.75,
                loyalty=0.25,
                militarization=0.35,
            )
        ]

        effects = get_faction_elite_effects(faction)

        self.assertGreater(effects["claimant_pressure"], 0.0)
        self.assertGreater(effects["unrest_pressure"], 0.0)

    def test_loyal_guilds_boost_tools_output(self):
        workshop = Region(
            name="Workshop",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=260,
            settlement_level="town",
            urban_specialization=URBAN_CRAFT_CENTER,
            infrastructure_level=0.8,
            market_level=0.8,
            storehouse_level=0.6,
            copper_mine_level=1.1,
            logging_camp_level=1.0,
            resource_fixed_endowments={RESOURCE_COPPER: 1.2},
            resource_wild_endowments={RESOURCE_TIMBER: 1.2},
        )
        faction = Faction(name="FactionA")
        world = WorldState(regions={"Workshop": workshop}, factions={"FactionA": faction})

        update_faction_resource_economy(world)
        baseline_tools = faction.produced_goods["tools"]

        faction.elite_blocs = [
            EliteBloc(
                bloc_type=BLOC_GUILDS,
                name="FactionA Guilds",
                influence=0.8,
                loyalty=0.85,
            )
        ]
        update_faction_resource_economy(world)
        boosted_tools = faction.produced_goods["tools"]

        self.assertGreater(boosted_tools, baseline_tools)

    def test_metrics_expose_elite_bloc_state(self):
        faction = Faction(name="FactionA")
        faction.elite_blocs = [
            EliteBloc(
                bloc_type=BLOC_NOBLES,
                name="FactionA Nobles",
                influence=0.7,
                loyalty=0.6,
            )
        ]
        region = Region(name="A", neighbors=[], owner="FactionA", resources=2, population=120)
        world = WorldState(regions={"A": region}, factions={"FactionA": faction})
        update_elite_blocs(world, emit_events=False)

        metrics = build_turn_metrics(world)["factions"]["FactionA"]

        self.assertIn("strongest_elite_bloc", metrics)
        self.assertIn("nobles_influence", metrics)


if __name__ == "__main__":
    unittest.main()
