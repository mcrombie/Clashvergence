import unittest

from src.actions import (
    expand,
    get_attack_target_score_components,
    get_attackable_regions,
    get_expand_target_score_components,
    get_expandable_regions,
)
from src.config import (
    SEAFARING_ATTACK_THRESHOLD,
    SEAFARING_CONTACT_THRESHOLD,
    SEAFARING_EXPANSION_THRESHOLD,
)
from src.models import Faction, Region, WorldState
from src.technology import TECH_SEAFARING, apply_development_technology_experience
from src.visibility import refresh_faction_visibility


def _make_maritime_world() -> WorldState:
    return WorldState(
        regions={
            "Main": Region(
                name="Main",
                neighbors=[],
                owner="FactionA",
                resources=5,
                population=300,
                ethnic_composition={"Aeth": 300},
                terrain_tags=["coast", "plains"],
                climate="Cfb",
                market_level=0.6,
                infrastructure_level=0.4,
            ),
            "Island": Region(
                name="Island",
                neighbors=[],
                owner=None,
                resources=4,
                population=90,
                ethnic_composition={"Islanders": 90},
                terrain_tags=["coast", "forest"],
                climate="Cfb",
            ),
            "EnemyIsland": Region(
                name="EnemyIsland",
                neighbors=[],
                owner="FactionB",
                resources=4,
                population=110,
                ethnic_composition={"Beth": 110},
                terrain_tags=["coast", "hills"],
                climate="Cfb",
            ),
        },
        factions={
            "FactionA": Faction(name="FactionA", treasury=10, primary_ethnicity="Aeth"),
            "FactionB": Faction(name="FactionB", treasury=8, primary_ethnicity="Beth"),
        },
        sea_links=[
            ("Main", "Island"),
            ("Main", "EnemyIsland"),
        ],
    )


class MaritimeMovementTests(unittest.TestCase):
    def test_seafaring_gates_maritime_expansion(self):
        world = _make_maritime_world()

        self.assertNotIn("Island", get_expandable_regions("FactionA", world))

        world.factions["FactionA"].institutional_technologies[TECH_SEAFARING] = SEAFARING_EXPANSION_THRESHOLD
        self.assertIn("Island", get_expandable_regions("FactionA", world))

        components = get_expand_target_score_components("Island", world, faction_name="FactionA")
        self.assertEqual(components["connection_mode"], "sea")
        self.assertEqual(components["maritime_route_source"], "Main")
        self.assertTrue(components["maritime_operation"])
        self.assertLess(components["maritime_expansion_modifier"], 0)

    def test_maritime_expansion_event_records_route(self):
        world = _make_maritime_world()
        world.factions["FactionA"].institutional_technologies[TECH_SEAFARING] = SEAFARING_EXPANSION_THRESHOLD

        self.assertTrue(expand("FactionA", "Island", world))

        event = next(event for event in world.events if event.type == "expand")
        self.assertIn("sea_expansion", event.tags)
        self.assertEqual(event.details["connection_mode"], "sea")
        self.assertEqual(event.details["maritime_route_source"], "Main")
        self.assertEqual(event.details["population_source_region"], "Main")
        self.assertGreater(event.details["population_transfer"], 0)

    def test_seafaring_attack_threshold_is_higher_than_expansion_threshold(self):
        world = _make_maritime_world()
        world.factions["FactionA"].institutional_technologies[TECH_SEAFARING] = SEAFARING_EXPANSION_THRESHOLD

        self.assertNotIn("EnemyIsland", get_attackable_regions("FactionA", world))

        world.factions["FactionA"].institutional_technologies[TECH_SEAFARING] = SEAFARING_ATTACK_THRESHOLD
        self.assertIn("EnemyIsland", get_attackable_regions("FactionA", world))

        components = get_attack_target_score_components("EnemyIsland", "FactionA", world)
        self.assertEqual(components["connection_mode"], "sea")
        self.assertEqual(components["maritime_route_source"], "Main")
        self.assertTrue(components["maritime_operation"])
        self.assertGreater(components["maritime_attack_penalty"], 0)

    def test_contact_threshold_reveals_direct_sea_links(self):
        world = _make_maritime_world()
        faction = world.factions["FactionA"]
        faction.known_regions = ["Main"]
        faction.visible_regions = ["Main"]
        faction.known_factions = ["FactionA"]
        faction.institutional_technologies[TECH_SEAFARING] = SEAFARING_CONTACT_THRESHOLD

        refresh_faction_visibility(world, "FactionA")

        self.assertIn("Island", faction.known_regions)
        self.assertIn("EnemyIsland", faction.known_regions)

    def test_coastal_port_development_raises_seafaring(self):
        world = _make_maritime_world()
        region = world.regions["Main"]
        before = region.technology_adoption.get(TECH_SEAFARING, 0.0)

        apply_development_technology_experience(region, "build_market", "trade")

        self.assertGreater(region.technology_adoption[TECH_SEAFARING], before)


if __name__ == "__main__":
    unittest.main()
