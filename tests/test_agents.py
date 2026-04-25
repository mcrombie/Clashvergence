import unittest

from src.agents import choose_action
from src.doctrine import HOMELAND_IMPRINT_WEIGHT, compute_faction_doctrine_profile
from src.models import Faction, Region, WorldState
from src.resource_economy import update_faction_resource_economy
from src.resources import CAPACITY_FOOD_SECURITY, RESOURCE_GRAIN, seed_region_resource_profile


def _seed_resources(world):
    for region in world.regions.values():
        seed_region_resource_profile(region)
    update_faction_resource_economy(world)


def _set_homeland_doctrine(world, faction_name, terrain_tags, climate="temperate"):
    faction = world.factions[faction_name]
    faction.doctrine_state.homeland_terrain_tags = list(terrain_tags)
    faction.doctrine_state.homeland_climate = climate
    faction.doctrine_state.terrain_experience = {
        tag: HOMELAND_IMPRINT_WEIGHT
        for tag in terrain_tags
    }
    faction.doctrine_state.climate_experience = {climate: HOMELAND_IMPRINT_WEIGHT}
    faction.doctrine_state.starting_regions = 1
    faction.doctrine_state.last_region_count = 1
    faction.doctrine_state.peak_regions = 1
    faction.doctrine_state.cumulative_regions_held = 1
    faction.doctrine_profile = compute_faction_doctrine_profile(
        faction,
        total_regions=len(world.regions),
    )


class AgentActionChoiceTests(unittest.TestCase):
    def test_affordable_high_value_frontier_can_beat_local_development_loop(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=5,
                    population=300,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    settlement_level="town",
                    market_level=0.8,
                    granary_level=1.2,
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C", "D", "E"],
                    owner=None,
                    resources=5,
                    population=160,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                ),
                "C": Region(name="C", neighbors=["B"], owner=None, resources=2),
                "D": Region(name="D", neighbors=["B"], owner=None, resources=2),
                "E": Region(name="E", neighbors=["B"], owner=None, resources=2),
            },
            factions={"FactionA": Faction(name="FactionA", treasury=3)},
        )
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["riverland", "plains"])

        self.assertEqual(choose_action("FactionA", world), ("expand", "B"))

    def test_rough_homeland_people_do_not_get_same_frontier_push(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=5,
                    population=300,
                    terrain_tags=["highland", "forest"],
                    climate="cold",
                    settlement_level="town",
                    market_level=0.8,
                    granary_level=1.2,
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C", "D", "E"],
                    owner=None,
                    resources=5,
                    population=160,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                ),
                "C": Region(name="C", neighbors=["B"], owner=None, resources=2),
                "D": Region(name="D", neighbors=["B"], owner=None, resources=2),
                "E": Region(name="E", neighbors=["B"], owner=None, resources=2),
            },
            factions={"FactionA": Faction(name="FactionA", treasury=3)},
        )
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["highland", "forest"], climate="cold")

        self.assertEqual(choose_action("FactionA", world), ("develop", "A"))

    def test_acute_food_shortage_still_keeps_development_priority(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=4,
                    population=360,
                    terrain_tags=["plains"],
                    climate="temperate",
                    settlement_level="town",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C", "D"],
                    owner=None,
                    resources=4,
                    population=120,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
                "C": Region(name="C", neighbors=["B"], owner=None, resources=2),
                "D": Region(name="D", neighbors=["B"], owner=None, resources=2),
            },
            factions={"FactionA": Faction(name="FactionA", treasury=3)},
        )
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["plains"])
        faction = world.factions["FactionA"]
        faction.resource_shortages[CAPACITY_FOOD_SECURITY] = 3.0
        faction.food_deficit = 2.0
        world.regions["A"].food_deficit = 2.0
        world.regions["A"].resource_established[RESOURCE_GRAIN] = 0.7

        action_name, target_region = choose_action("FactionA", world)

        self.assertEqual(action_name, "develop")
        self.assertEqual(target_region, "A")


if __name__ == "__main__":
    unittest.main()
