import unittest

from src.governance import get_faction_administrative_capacity_modifier
from src.ideology import (
    IDEOLOGY_ANTI_TAX_PROVINCIALISM,
    IDEOLOGY_LEGALISM,
    IDEOLOGY_MERCHANT_CONSTITUTIONALISM,
    IDEOLOGY_SACRED_KINGSHIP,
    get_faction_ideology_effects,
    initialize_ideologies,
    update_ideologies,
)
from src.internal_politics import (
    BLOC_GUILDS,
    BLOC_MERCHANT_HOUSES,
    BLOC_PRIESTHOOD,
    BLOC_PROVINCIAL_GOVERNORS,
    BLOC_TRIBAL_LINEAGES,
    BLOC_URBAN_COMMONS,
    initialize_elite_blocs,
)
from src.metrics import build_turn_metrics
from src.models import EliteBloc, Faction, FactionIdentity, FactionIdeologyState, Region, WorldState
from src.technology import TECH_MARKET_ACCOUNTING, TECH_ROAD_ADMINISTRATION, TECH_TEMPLE_RECORDKEEPING
from src.urban import URBAN_MARKET_TOWN, URBAN_PORT_CITY, URBAN_TEMPLE_CITY


class IdeologyTests(unittest.TestCase):
    def test_trade_urbanism_and_merchants_produce_merchant_constitutionalism(self):
        identity = FactionIdentity(
            internal_id="FactionA",
            culture_name="Harbor",
            polity_tier="state",
            government_form="republic",
        )
        faction = Faction(
            name="FactionA",
            identity=identity,
            trade_income=20.0,
            trade_foreign_income=7.0,
            urban_network_value=3.0,
        )
        faction.institutional_technologies[TECH_MARKET_ACCOUNTING] = 0.9
        regions = {
            "Port": Region(
                name="Port",
                neighbors=["Market"],
                owner="FactionA",
                resources=2,
                population=720,
                settlement_level="city",
                urban_specialization=URBAN_PORT_CITY,
                market_level=1.4,
                trade_foreign_value=5.0,
                trade_value_bonus=3.0,
            ),
            "Market": Region(
                name="Market",
                neighbors=["Port"],
                owner="FactionA",
                resources=2,
                population=460,
                settlement_level="town",
                urban_specialization=URBAN_MARKET_TOWN,
                market_level=1.2,
                trade_value_bonus=2.0,
            ),
        }
        world = WorldState(regions=regions, factions={"FactionA": faction})

        initialize_elite_blocs(world)
        initialize_ideologies(world)

        self.assertEqual(faction.ideology.dominant_ideology, IDEOLOGY_MERCHANT_CONSTITUTIONALISM)
        bloc_types = {bloc.bloc_type for bloc in faction.elite_blocs}
        self.assertIn(BLOC_MERCHANT_HOUSES, bloc_types)
        self.assertIn(BLOC_URBAN_COMMONS, bloc_types)
        self.assertGreater(faction.ideology.currents[IDEOLOGY_MERCHANT_CONSTITUTIONALISM], 0.5)

    def test_sacred_kingship_emerges_from_priesthood_state_cult_and_monarchy(self):
        identity = FactionIdentity(
            internal_id="FactionA",
            culture_name="Sunvale",
            polity_tier="chiefdom",
            government_form="monarchy",
        )
        faction = Faction(name="FactionA", identity=identity)
        faction.religion.official_religion = "Sun Rite"
        faction.religion.religious_legitimacy = 0.82
        faction.religion.clergy_support = 0.86
        faction.religion.state_cult_strength = 0.88
        temple = Region(
            name="Temple",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=380,
            settlement_level="town",
            urban_specialization=URBAN_TEMPLE_CITY,
            sacred_religion="Sun Rite",
            shrine_level=1.4,
            pilgrimage_value=1.2,
        )
        world = WorldState(regions={"Temple": temple}, factions={"FactionA": faction})

        initialize_elite_blocs(world)
        initialize_ideologies(world)

        self.assertEqual(faction.ideology.dominant_ideology, IDEOLOGY_SACRED_KINGSHIP)
        self.assertIn(BLOC_PRIESTHOOD, {bloc.bloc_type for bloc in faction.elite_blocs})
        self.assertEqual(faction.ideology.legitimacy_model, "sacred_dynastic")

    def test_alienated_governors_and_autonomous_frontiers_produce_anti_tax_provincialism(self):
        faction = Faction(name="FactionA")
        faction.administrative_overextension = 1.1
        faction.elite_blocs = [
            EliteBloc(
                bloc_type=BLOC_PROVINCIAL_GOVERNORS,
                name="FactionA Governors",
                influence=0.82,
                loyalty=0.2,
            ),
            EliteBloc(
                bloc_type=BLOC_TRIBAL_LINEAGES,
                name="FactionA Lineages",
                influence=0.7,
                loyalty=0.25,
            ),
        ]
        regions = {
            f"Frontier{index}": Region(
                name=f"Frontier{index}",
                neighbors=[],
                owner="FactionA",
                resources=2,
                population=180,
                core_status="frontier",
                administrative_autonomy=0.92,
                administrative_tax_capture=0.42,
            )
            for index in range(5)
        }
        world = WorldState(regions=regions, factions={"FactionA": faction})

        initialize_ideologies(world)

        self.assertEqual(faction.ideology.dominant_ideology, IDEOLOGY_ANTI_TAX_PROVINCIALISM)
        effects = get_faction_ideology_effects(faction)
        self.assertGreater(effects["unrest_pressure"], 0.0)
        self.assertLess(effects["administrative_capacity_factor"], 0.0)

    def test_legalism_boosts_administration_without_replacing_government_form(self):
        faction = Faction(name="FactionA")
        faction.ideology = FactionIdeologyState(
            dominant_ideology=IDEOLOGY_LEGALISM,
            dominant_label="Legalism",
            currents={IDEOLOGY_LEGALISM: 0.82},
            cohesion=0.72,
            institutionalism=0.76,
            legitimacy_model="administrative_universal",
        )
        baseline = get_faction_administrative_capacity_modifier(Faction(name="Baseline"))

        self.assertGreater(get_faction_administrative_capacity_modifier(faction), baseline)
        self.assertEqual(faction.government_form, "council")

    def test_ideology_shift_event_is_emitted_when_dominant_current_changes(self):
        identity = FactionIdentity(
            internal_id="FactionA",
            culture_name="Sunvale",
            polity_tier="chiefdom",
            government_form="monarchy",
        )
        faction = Faction(name="FactionA", identity=identity)
        faction.ideology = FactionIdeologyState()
        faction.religion.official_religion = "Sun Rite"
        faction.religion.religious_legitimacy = 0.9
        faction.religion.clergy_support = 0.9
        faction.religion.state_cult_strength = 0.9
        faction.elite_blocs = [
            EliteBloc(
                bloc_type=BLOC_PRIESTHOOD,
                name="Sunvale Priesthood",
                influence=0.86,
                loyalty=0.86,
            )
        ]
        world = WorldState(
            regions={
                "Temple": Region(
                    name="Temple",
                    neighbors=[],
                    owner="FactionA",
                    resources=2,
                    population=300,
                    settlement_level="town",
                    urban_specialization=URBAN_TEMPLE_CITY,
                )
            },
            factions={"FactionA": faction},
        )

        update_ideologies(world, emit_events=True)

        self.assertEqual(faction.ideology.dominant_ideology, IDEOLOGY_SACRED_KINGSHIP)
        self.assertEqual(world.events[-1].type, "ideology_shift")
        self.assertEqual(world.events[-1].get("new_ideology"), IDEOLOGY_SACRED_KINGSHIP)

    def test_metrics_expose_ideology_state_and_currents(self):
        faction = Faction(name="FactionA")
        faction.ideology = FactionIdeologyState(
            dominant_ideology=IDEOLOGY_LEGALISM,
            dominant_label="Legalism",
            currents={IDEOLOGY_LEGALISM: 0.7},
            cohesion=0.68,
            radicalism=0.12,
            institutionalism=0.72,
            reform_pressure=0.08,
            legitimacy_model="administrative_universal",
        )
        faction.institutional_technologies[TECH_ROAD_ADMINISTRATION] = 0.8
        faction.institutional_technologies[TECH_TEMPLE_RECORDKEEPING] = 0.7
        region = Region(name="A", neighbors=[], owner="FactionA", resources=2, population=120)
        world = WorldState(regions={"A": region}, factions={"FactionA": faction})

        metrics = build_turn_metrics(world)["factions"]["FactionA"]

        self.assertEqual(metrics["dominant_ideology"], IDEOLOGY_LEGALISM)
        self.assertEqual(metrics["dominant_ideology_label"], "Legalism")
        self.assertIn("legalism_current", metrics)


if __name__ == "__main__":
    unittest.main()
