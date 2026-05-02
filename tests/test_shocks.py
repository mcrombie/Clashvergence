import unittest
from unittest.mock import patch

from src.metrics import build_turn_metrics
from src.models import Faction, Region, RelationshipState, WorldState
from src.resource_economy import apply_turn_food_economy, update_faction_resource_economy
from src.resources import RESOURCE_COPPER, RESOURCE_GRAIN, RESOURCE_WILD_FOOD, seed_region_resource_profile
from src.shocks import (
    SHOCK_CLIMATE_ANOMALY,
    SHOCK_FAMINE,
    SHOCK_TRADE_COLLAPSE,
    apply_shock_population_losses,
    get_region_active_shock_intensity,
    refresh_long_cycle_shocks,
    resolve_food_and_disease_shocks,
    resolve_trade_network_shocks,
    start_shock,
    update_shock_rollups,
)


class ShockEcologyTests(unittest.TestCase):
    def _single_region_world(self):
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=220,
            terrain_tags=["riverland", "plains"],
            climate="temperate",
            settlement_level="town",
            agriculture_level=1.0,
            granary_level=0.4,
        )
        seed_region_resource_profile(region)
        region.resource_established[RESOURCE_GRAIN] = 0.9
        return WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )

    def test_climate_anomaly_reduces_food_output(self):
        world = self._single_region_world()
        update_faction_resource_economy(world)
        baseline_grain = world.regions["A"].resource_output[RESOURCE_GRAIN]

        start_shock(
            world,
            SHOCK_CLIMATE_ANOMALY,
            "A",
            intensity=0.75,
            emit_event=False,
        )
        update_faction_resource_economy(world)

        self.assertLess(world.regions["A"].resource_output[RESOURCE_GRAIN], baseline_grain)
        self.assertGreater(get_region_active_shock_intensity(world, world.regions["A"], SHOCK_CLIMATE_ANOMALY), 0.0)

    def test_food_deficit_escalates_to_famine_and_population_loss(self):
        world = self._single_region_world()
        region = world.regions["A"]
        update_faction_resource_economy(world)
        region.food_consumption = 3.0
        region.food_deficit = 2.4
        region.food_balance = -2.4
        region.food_stress_turns = 3

        with patch("src.shocks.random.random", return_value=0.99):
            resolve_food_and_disease_shocks(world)

        self.assertTrue(any(event.type == "shock_famine" for event in world.events))
        self.assertGreater(get_region_active_shock_intensity(world, region, SHOCK_FAMINE), 0.0)
        population_before = region.population

        apply_shock_population_losses(world)

        self.assertLess(region.population, population_before)
        self.assertTrue(any(event.type == "shock_population_loss" for event in world.events))

    def test_shock_rollups_reach_metrics(self):
        world = self._single_region_world()
        update_faction_resource_economy(world)
        start_shock(world, SHOCK_FAMINE, "A", intensity=0.6, emit_event=False)
        update_shock_rollups(world)

        metrics = build_turn_metrics(world)["factions"]["FactionA"]

        self.assertGreater(metrics["shock_exposure"], 0.0)
        self.assertGreater(metrics["shock_resilience"], 0.0)
        self.assertGreater(metrics["famine_pressure"], 0.0)

    def test_trade_collapse_reduces_trade_income(self):
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
                    population=150,
                    terrain_tags=["highland"],
                    climate="temperate",
                    copper_mine_level=1.5,
                ),
            },
            factions={"FactionA": Faction(name="FactionA")},
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["B"].resource_fixed_endowments[RESOURCE_COPPER] = 1.3
        update_faction_resource_economy(world)
        baseline_trade = world.factions["FactionA"].trade_income

        start_shock(world, SHOCK_TRADE_COLLAPSE, "A", intensity=0.85, emit_event=False)
        update_faction_resource_economy(world)

        self.assertLess(world.factions["FactionA"].trade_income, baseline_trade)
        self.assertGreater(world.regions["A"].trade_disruption_risk, 0.0)

    def test_refresh_long_cycle_shocks_detects_slow_ecological_damage(self):
        world = self._single_region_world()
        region = world.regions["A"]
        region.soil_health = 0.42
        region.ecological_integrity = 0.43
        update_faction_resource_economy(world)

        with patch("src.shocks.random.random", return_value=0.99):
            refresh_long_cycle_shocks(world)

        shock_types = {event.type for event in world.events}
        self.assertIn("shock_soil_exhaustion", shock_types)
        self.assertIn("shock_ecological_degradation", shock_types)

    def test_trade_network_shock_can_emerge_from_disruption(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=3,
                    population=240,
                    terrain_tags=["coast", "plains"],
                    climate="oceanic",
                    settlement_level="town",
                    market_level=1.2,
                    road_level=0.8,
                    trade_disruption_risk=0.8,
                    trade_import_reliance=0.8,
                    trade_warfare_pressure=0.6,
                    trade_route_role="hub",
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=2,
                    population=180,
                    terrain_tags=["coast"],
                    climate="oceanic",
                    settlement_level="town",
                    market_level=0.8,
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
            relationships={
                ("FactionA", "FactionB"): RelationshipState(status="alliance", trust=10.0)
            },
        )
        for region in world.regions.values():
            seed_region_resource_profile(region)
        world.regions["A"].resource_fixed_endowments[RESOURCE_COPPER] = 1.2
        world.regions["B"].resource_wild_endowments[RESOURCE_WILD_FOOD] = 0.8

        resolve_trade_network_shocks(world)

        self.assertTrue(any(event.type == "shock_trade_collapse" for event in world.events))


if __name__ == "__main__":
    unittest.main()
