import unittest
from unittest.mock import patch

from src.actions import get_attack_target_score_components
from src.climate import (
    classify_koppen_climate,
    format_climate_code_label,
    get_climate_similarity,
    get_climate_food_spoilage_modifier,
    get_seasonal_climate_food_production_multiplier,
    get_seasonal_climate_unrest_multiplier,
    normalize_climate,
)
from src.doctrine import (
    get_faction_climate_affinity,
    get_faction_region_alignment,
    update_faction_doctrines,
)
from src.models import Faction, Region, WorldState
from src.region_state import get_region_attack_projection_modifier
from src.resource_economy import (
    apply_turn_food_economy,
    get_region_effective_income,
    get_region_food_spoilage_rate,
    get_region_maintenance_cost,
)
from src.resources import (
    RESOURCE_GRAIN,
    RESOURCE_HORSES,
    seed_region_resource_profile,
)
from src.shocks import (
    SHOCK_CLIMATE_ANOMALY,
    get_region_active_shock_intensity,
    refresh_long_cycle_shocks,
)
from src.heartland import (
    update_region_integration,
)
from src.world import create_world


class ClimateSystemTests(unittest.TestCase):
    def _food_test_world(self, climate: str) -> WorldState:
        region = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=2,
            population=120,
            terrain_tags=["plains"],
            climate=climate,
            food_stored=0.0,
        )
        region.resource_output[RESOURCE_GRAIN] = 4.0
        return WorldState(
            regions={"A": region},
            factions={"FactionA": Faction(name="FactionA")},
        )

    def test_world_loads_climate_data_for_thirty_seven_region_ring(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)

        self.assertEqual(world.regions["O1"].climate, "Cfb")
        self.assertEqual(world.regions["M1"].climate, "Cfb")
        self.assertEqual(world.regions["I1"].climate, "Dfb")
        self.assertEqual(world.regions["C"].climate, "Cfb")

    def test_homeland_climate_initializes_from_starting_region(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)

        for faction in world.factions.values():
            homeland_region = faction.doctrine_state.homeland_region
            self.assertIsNotNone(homeland_region)
            self.assertEqual(
                faction.doctrine_state.homeland_climate,
                world.regions[homeland_region].climate,
            )
            self.assertEqual(faction.doctrine_profile.climate_identity, "Oceanic")

    def test_legacy_climate_aliases_normalize_to_koppen_codes(self):
        self.assertEqual(normalize_climate("temperate"), "Cfb")
        self.assertEqual(normalize_climate("oceanic"), "Cfb")
        self.assertEqual(normalize_climate("cold"), "Dfb")
        self.assertEqual(normalize_climate("arid"), "BWh")
        self.assertEqual(normalize_climate("steppe"), "BSk")
        self.assertEqual(normalize_climate("tropical"), "Aw")
        self.assertEqual(format_climate_code_label("cold"), "Dfb Warm-Summer Humid Continental")

    def test_climate_similarity_transfers_across_related_koppen_types(self):
        self.assertGreater(
            get_climate_similarity("Cfb", "Cfa"),
            get_climate_similarity("Cfb", "BWh"),
        )
        self.assertGreater(
            get_climate_similarity("Dfb", "Dfc"),
            get_climate_similarity("Dfb", "Af"),
        )

    def test_matching_climate_improves_region_alignment(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        adapted = world.factions[faction_names[0]]
        unadapted = world.factions[faction_names[1]]

        adapted.doctrine_state.homeland_climate = "cold"
        adapted.doctrine_state.climate_experience = {"cold": 16.0}
        unadapted.doctrine_state.homeland_climate = "temperate"
        unadapted.doctrine_state.climate_experience = {"temperate": 16.0}

        adapted_alignment = get_faction_region_alignment(adapted, ["highland", "forest"], "cold")
        unadapted_alignment = get_faction_region_alignment(unadapted, ["highland", "forest"], "cold")

        self.assertGreater(adapted_alignment["climate_affinity"], unadapted_alignment["climate_affinity"])
        self.assertGreaterEqual(adapted_alignment["combat_modifier"], unadapted_alignment["combat_modifier"])
        self.assertTrue(adapted_alignment["climate_match"])
        self.assertFalse(unadapted_alignment["climate_match"])

    def test_climate_affinity_grows_through_exposure_over_time(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        target_region = world.regions["B"]
        target_region.owner = faction_name
        target_region.integrated_owner = faction_name
        target_region.homeland_faction_id = "OtherFaction"
        target_region.climate = "cold"

        initial_affinity = get_faction_climate_affinity(faction, "cold")
        for _ in range(3):
            update_faction_doctrines(world)
        adapted_affinity = get_faction_climate_affinity(faction, "cold")

        self.assertGreater(adapted_affinity, initial_affinity)

    def test_matching_climate_integrates_faster_than_foreign_climate(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))

        temperate_region = world.regions["B"]
        cold_region = world.regions["C"]

        for region, climate in ((temperate_region, "temperate"), (cold_region, "cold")):
            region.owner = faction_name
            region.integrated_owner = faction_name
            region.homeland_faction_id = "SomeoneElse"
            region.integration_score = 1.0
            region.core_status = "frontier"
            region.ownership_turns = 1
            region.climate = climate

        update_region_integration(world)

        self.assertGreater(temperate_region.integration_score, cold_region.integration_score)

    def test_attack_projection_penalizes_foreign_climate_staging(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        region = world.regions["M"]
        region.owner = faction_name
        region.integrated_owner = faction_name
        region.integration_score = 1.0
        region.core_status = "frontier"

        region.climate = "temperate"
        matching_projection = get_region_attack_projection_modifier(
            region,
            world=world,
            faction_name=faction_name,
        )

        region.climate = "BWh"
        mismatched_projection = get_region_attack_projection_modifier(
            region,
            world=world,
            faction_name=faction_name,
        )

        self.assertEqual(matching_projection, -1)
        self.assertEqual(mismatched_projection, -3)

    def test_climate_affinity_improves_income_and_reduces_maintenance(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]

        matched_region = world.regions["B"]
        matched_region.owner = faction_name
        matched_region.integrated_owner = faction_name
        matched_region.homeland_faction_id = "OtherFaction"
        matched_region.core_status = "frontier"
        matched_region.integration_score = 1.0
        matched_region.resources = 4
        matched_region.climate = faction.doctrine_state.homeland_climate

        foreign_region = world.regions["C"]
        foreign_region.owner = faction_name
        foreign_region.integrated_owner = faction_name
        foreign_region.homeland_faction_id = "OtherFaction"
        foreign_region.core_status = "frontier"
        foreign_region.integration_score = 1.0
        foreign_region.resources = 4
        foreign_region.climate = "cold" if faction.doctrine_state.homeland_climate != "cold" else "arid"

        self.assertGreaterEqual(
            get_region_effective_income(matched_region, world),
            get_region_effective_income(foreign_region, world),
        )
        self.assertLessEqual(
            get_region_maintenance_cost(matched_region, world),
            get_region_maintenance_cost(foreign_region, world),
        )

    def test_attack_score_exposes_climate_sensitive_alignment(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 8
        world.factions[defender_name].treasury = 8
        world.regions["D"].owner = defender_name
        world.regions["D"].climate = "cold"

        score = get_attack_target_score_components("D", attacker_name, world)

        self.assertIn("doctrine_combat_modifier", score)
        self.assertIn("terrain_affinity", score)
        self.assertGreaterEqual(score["success_chance"], 0.2)

    def test_climate_profiles_expose_seasonal_pressure(self):
        self.assertGreater(
            get_seasonal_climate_food_production_multiplier("Dfb", "Summer"),
            get_seasonal_climate_food_production_multiplier("Dfb", "Winter"),
        )
        self.assertGreater(
            get_climate_food_spoilage_modifier("Af"),
            get_climate_food_spoilage_modifier("BWh"),
        )
        self.assertGreater(
            get_seasonal_climate_unrest_multiplier("BWh", "Summer"),
            get_seasonal_climate_unrest_multiplier("BWh", "Spring"),
        )

    def test_koppen_classifier_recognizes_representative_monthly_climates(self):
        self.assertEqual(
            classify_koppen_climate(
                [26.0] * 12,
                [210.0, 205.0, 215.0, 220.0, 210.0, 205.0, 215.0, 220.0, 210.0, 205.0, 215.0, 220.0],
            ),
            "Af",
        )
        self.assertEqual(
            classify_koppen_climate(
                [3.0, 4.0, 7.0, 11.0, 15.0, 18.0, 19.0, 18.0, 15.0, 11.0, 7.0, 4.0],
                [60.0] * 12,
            ),
            "Cfb",
        )
        self.assertEqual(
            classify_koppen_climate(
                [-10.0, -8.0, -2.0, 6.0, 12.0, 16.0, 18.0, 16.0, 10.0, 4.0, -2.0, -8.0],
                [45.0] * 12,
            ),
            "Dfb",
        )
        self.assertEqual(
            classify_koppen_climate(
                [18.0, 20.0, 24.0, 29.0, 33.0, 36.0, 38.0, 37.0, 33.0, 28.0, 23.0, 19.0],
                [4.0] * 12,
            ),
            "BWh",
        )

    def test_climate_seasonality_changes_food_output(self):
        summer_world = self._food_test_world("cold")
        winter_world = self._food_test_world("cold")

        apply_turn_food_economy(summer_world, season_name="Summer")
        apply_turn_food_economy(winter_world, season_name="Winter")

        self.assertGreater(
            summer_world.regions["A"].food_produced,
            winter_world.regions["A"].food_produced,
        )

    def test_climate_spoilage_rate_reflects_local_climate(self):
        tropical = Region(
            name="T",
            neighbors=[],
            owner="FactionA",
            resources=1,
            terrain_tags=["forest"],
            climate="tropical",
        )
        arid = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=1,
            terrain_tags=["plains"],
            climate="arid",
        )

        self.assertGreater(
            get_region_food_spoilage_rate(tropical),
            get_region_food_spoilage_rate(arid),
        )

    def test_arid_and_steppe_resource_profiles_are_distinct(self):
        temperate = Region(
            name="T",
            neighbors=[],
            owner="FactionA",
            resources=1,
            terrain_tags=["plains"],
            climate="temperate",
        )
        arid = Region(
            name="A",
            neighbors=[],
            owner="FactionA",
            resources=1,
            terrain_tags=["plains"],
            climate="arid",
        )
        steppe = Region(
            name="S",
            neighbors=[],
            owner="FactionA",
            resources=1,
            terrain_tags=["plains"],
            climate="steppe",
        )

        for region in (temperate, arid, steppe):
            seed_region_resource_profile(region)

        self.assertLess(
            arid.resource_suitability[RESOURCE_GRAIN],
            temperate.resource_suitability[RESOURCE_GRAIN],
        )
        self.assertGreater(
            steppe.resource_suitability[RESOURCE_HORSES],
            temperate.resource_suitability[RESOURCE_HORSES],
        )

    def test_climate_anomaly_vulnerability_affects_shock_generation(self):
        def build_world(climate: str) -> WorldState:
            region = Region(
                name="A",
                neighbors=[],
                owner="FactionA",
                resources=2,
                population=180,
                terrain_tags=["plains"],
                climate=climate,
                food_stored=2.0,
                food_consumption=1.0,
                infrastructure_level=1.0,
                granary_level=1.0,
                storehouse_level=1.0,
                market_level=1.0,
                road_level=1.0,
            )
            region.soil_health = 1.0
            region.ecological_integrity = 1.0
            return WorldState(
                regions={"A": region},
                factions={"FactionA": Faction(name="FactionA")},
            )

        arid_world = build_world("arid")
        oceanic_world = build_world("oceanic")

        with patch("src.shocks.random.random", return_value=0.08):
            refresh_long_cycle_shocks(arid_world)
            refresh_long_cycle_shocks(oceanic_world)

        self.assertGreater(
            get_region_active_shock_intensity(
                arid_world,
                arid_world.regions["A"],
                SHOCK_CLIMATE_ANOMALY,
            ),
            0.0,
        )
        self.assertEqual(
            get_region_active_shock_intensity(
                oceanic_world,
                oceanic_world.regions["A"],
                SHOCK_CLIMATE_ANOMALY,
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
