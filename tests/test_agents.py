import unittest

from src.actions import get_expand_target_score_components
from src.agents import choose_action, choose_actions, evaluate_action_diagnostics, get_available_tracks
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
    def test_expansion_score_rewards_gateway_to_deep_unclaimed_component(self):
        regions = {
            "A": Region(
                name="A",
                neighbors=["Gateway"],
                owner="FactionA",
                resources=3,
                population=220,
                terrain_tags=["plains"],
                climate="temperate",
                homeland_faction_id="FactionA",
                integration_score=10.0,
            ),
            "Gateway": Region(
                name="Gateway",
                neighbors=["A", "U1"],
                owner=None,
                resources=1,
                population=80,
                terrain_tags=["plains"],
                climate="temperate",
            ),
        }
        previous = "Gateway"
        for index in range(1, 9):
            name = f"U{index}"
            next_name = f"U{index + 1}" if index < 8 else None
            neighbors = [previous] + ([next_name] if next_name is not None else [])
            regions[name] = Region(
                name=name,
                neighbors=neighbors,
                owner=None,
                resources=1,
                population=60,
                terrain_tags=["plains"],
                climate="temperate",
            )
            previous = name
        world = WorldState(
            regions=regions,
            factions={"FactionA": Faction(name="FactionA", treasury=5)},
        )
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["plains"])

        components = get_expand_target_score_components(
            "Gateway",
            world,
            faction_name="FactionA",
        )

        self.assertEqual(components["unclaimed_neighbors"], 1)
        self.assertEqual(components["frontier_component_size"], 9)
        self.assertEqual(components["frontier_depth_regions"], 7)
        self.assertGreater(components["frontier_unlock_bonus"], 0)

    def test_deep_frontier_gateway_can_displace_border_attack(self):
        regions = {
            "A": Region(
                name="A",
                neighbors=["Gateway", "EnemyHub"],
                owner="FactionA",
                resources=4,
                population=280,
                terrain_tags=["plains"],
                climate="temperate",
                settlement_level="town",
                homeland_faction_id="FactionA",
                integration_score=10.0,
            ),
            "Gateway": Region(
                name="Gateway",
                neighbors=["A", "U1"],
                owner=None,
                resources=1,
                population=80,
                terrain_tags=["plains"],
                climate="temperate",
            ),
            "EnemyHub": Region(
                name="EnemyHub",
                neighbors=["A"],
                owner="Enemy",
                resources=5,
                population=180,
                terrain_tags=["plains"],
                climate="temperate",
                trade_route_role="hub",
                trade_served_regions=4,
                trade_throughput=40.0,
                trade_hub_value=10.0,
            ),
        }
        previous = "Gateway"
        for index in range(1, 13):
            name = f"U{index}"
            next_name = f"U{index + 1}" if index < 12 else None
            neighbors = [previous] + ([next_name] if next_name is not None else [])
            regions[name] = Region(
                name=name,
                neighbors=neighbors,
                owner=None,
                resources=1,
                population=60,
                terrain_tags=["plains"],
                climate="temperate",
            )
            previous = name
        world = WorldState(
            regions=regions,
            factions={
                "FactionA": Faction(
                    name="FactionA",
                    treasury=8,
                    faction_traits=["military_expansion"],
                ),
                "Enemy": Faction(name="Enemy", treasury=0),
            },
            turn=130,
        )
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["plains"])

        diagnostics = evaluate_action_diagnostics("FactionA", world)

        self.assertEqual(choose_action("FactionA", world), ("expand", "Gateway"))
        self.assertGreater(diagnostics["utilities"]["expand"], diagnostics["utilities"]["attack"])
        self.assertEqual(diagnostics["components"]["expand"]["frontier_component_size"], 13)

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

    def test_dual_track_faction_can_pair_military_and_development_actions(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B", "E"],
                    owner="FactionA",
                    resources=5,
                    population=320,
                    terrain_tags=["riverland", "plains"],
                    climate="temperate",
                    settlement_level="town",
                    market_level=0.4,
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                ),
                "B": Region(name="B", neighbors=["A", "C"], owner="FactionA", resources=3, population=180),
                "C": Region(name="C", neighbors=["B", "D"], owner="FactionA", resources=3, population=180),
                "D": Region(name="D", neighbors=["C"], owner="FactionA", resources=3, population=180),
                "E": Region(name="E", neighbors=["A"], owner=None, resources=4, population=130),
            },
            factions={"FactionA": Faction(name="FactionA", treasury=8)},
        )
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["riverland", "plains"])
        world.factions["FactionA"].administrative_efficiency = 0.8

        military_available, admin_available = get_available_tracks("FactionA", world)
        actions = choose_actions("FactionA", world)

        self.assertTrue(military_available)
        self.assertTrue(admin_available)
        self.assertEqual(len(actions), 2)
        self.assertIn(actions[0][0], {"attack", "expand"})
        self.assertEqual(actions[1][0], "develop")

    def test_dual_track_faction_can_pair_exploration_and_development_actions(self):
        world = WorldState(
            regions={
                "R0": Region(
                    name="R0",
                    neighbors=["Scout"],
                    owner="FactionA",
                    resources=5,
                    population=260,
                    terrain_tags=["plains"],
                    climate="temperate",
                    settlement_level="town",
                    homeland_faction_id="FactionA",
                    integration_score=10.0,
                ),
                "R1": Region(name="R1", neighbors=[], owner="FactionA", resources=3, population=180),
                "R2": Region(name="R2", neighbors=[], owner="FactionA", resources=3, population=180),
                "R3": Region(name="R3", neighbors=[], owner="FactionA", resources=3, population=180),
                "Scout": Region(
                    name="Scout",
                    neighbors=["R0", "Hidden"],
                    owner=None,
                    resources=2,
                    population=90,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
                "Hidden": Region(
                    name="Hidden",
                    neighbors=["Scout"],
                    owner=None,
                    resources=2,
                    population=80,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
            },
            factions={"FactionA": Faction(name="FactionA", treasury=0)},
        )
        faction = world.factions["FactionA"]
        faction.known_regions = ["R0", "R1", "R2", "R3", "Scout"]
        faction.visible_regions = ["R0", "R1", "R2", "R3", "Scout"]
        faction.known_factions = ["FactionA"]
        faction.administrative_efficiency = 0.8
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["plains"])

        actions = choose_actions("FactionA", world)

        self.assertIn(("explore", "Scout"), actions)
        self.assertTrue(any(action_name == "develop" for action_name, _target in actions))

    def test_dual_track_requires_admin_efficiency_gate(self):
        world = WorldState(
            regions={
                f"R{index}": Region(
                    name=f"R{index}",
                    neighbors=["E"] if index == 0 else [],
                    owner="FactionA",
                    resources=3,
                    population=160,
                    terrain_tags=["plains"],
                    climate="temperate",
                )
                for index in range(4)
            }
            | {
                "E": Region(
                    name="E",
                    neighbors=["R0"],
                    owner=None,
                    resources=4,
                    population=120,
                    terrain_tags=["plains"],
                    climate="temperate",
                )
            },
            factions={"FactionA": Faction(name="FactionA", treasury=8)},
        )
        _seed_resources(world)
        _set_homeland_doctrine(world, "FactionA", ["plains"])
        world.factions["FactionA"].administrative_efficiency = 0.3

        self.assertEqual(get_available_tracks("FactionA", world), (True, False))
        self.assertLessEqual(len(choose_actions("FactionA", world)), 1)


if __name__ == "__main__":
    unittest.main()
