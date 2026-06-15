import unittest

from src.actions import attack, expand, get_attackable_regions, get_expandable_regions
from src.metrics import build_turn_metrics
from src.player_view import build_observer_snapshot
from src.simulation_ui import build_simulation_view_model, render_simulation_html
from src.social_forms import (
    BAND_MIGRATION_COST,
    get_band_camp_region_name,
    update_nomadic_social_forms,
)
from src.world import create_world


def _owned_region_names(world, faction_name):
    return sorted(
        region.name
        for region in world.regions.values()
        if region.owner == faction_name
    )


class SocialFormTests(unittest.TestCase):
    def test_generated_factions_start_as_single_region_bands(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-start")

        for faction_name, faction in world.factions.items():
            self.assertEqual(faction.polity_tier, "band")
            self.assertEqual(faction.government_form, "leader")
            self.assertEqual(faction.government_type, "Band")
            self.assertEqual(len(_owned_region_names(world, faction_name)), 1)
            self.assertIsNotNone(get_band_camp_region_name(world, faction_name))

    def test_band_expansion_relocates_camp_instead_of_adding_region(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-migration")
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        old_camp = get_band_camp_region_name(world, faction_name)
        target_region = get_expandable_regions(faction_name, world)[0]
        old_population = world.regions[old_camp].population
        faction.treasury = BAND_MIGRATION_COST

        self.assertTrue(expand(faction_name, target_region, world))

        self.assertEqual(_owned_region_names(world, faction_name), [target_region])
        self.assertIsNone(world.regions[old_camp].owner)
        self.assertGreater(world.regions[target_region].population, 0)
        self.assertLess(world.regions[old_camp].population, old_population)
        self.assertEqual(world.events[-1].type, "band_migration")
        self.assertEqual(world.events[-1].details["previous_camp_region"], old_camp)
        self.assertIn(old_camp, world.events[-1].details["abandoned_regions"])
        self.assertEqual(world.events[-1].impact["regions_gained"], 0)

    def test_bands_do_not_have_normal_attack_targets(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-attack")
        faction_name = next(iter(world.factions))
        defender_name = next(name for name in world.factions if name != faction_name)
        target_region = _owned_region_names(world, defender_name)[0]
        world.factions[faction_name].treasury = 20

        self.assertEqual(get_attackable_regions(faction_name, world), [])
        self.assertFalse(attack(faction_name, target_region, world))

    def test_stable_band_can_tribalize_after_continuity_threshold(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-tribalize")
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        camp_region = world.regions[get_band_camp_region_name(world, faction_name)]
        camp_region.population = 260
        camp_region.settlement_level = "rural"
        camp_region.food_deficit = 0.0
        camp_region.unrest = 0.0
        faction.tribalization_progress = 0.95
        faction.band_settled_turns = 3

        events = update_nomadic_social_forms(world)

        self.assertEqual(faction.polity_tier, "tribe")
        self.assertEqual(faction.government_form, "council")
        self.assertTrue(any(event.type == "social_form_transition" for event in events))
        self.assertEqual(world.events[-1].details["from"], "band")
        self.assertEqual(world.events[-1].details["to"], "tribe")

    def test_band_state_is_exposed_in_metrics_observer_and_html(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-visibility")
        faction_name = next(iter(world.factions))

        metrics = build_turn_metrics(world)
        faction_metrics = metrics["factions"][faction_name]
        self.assertIn("camp_region", faction_metrics)
        self.assertIn("tribalization_progress", faction_metrics)
        self.assertIn("migration_pressure", faction_metrics)

        observer_faction = next(
            faction
            for faction in build_observer_snapshot(world)["factions"]
            if faction["name"] == faction_name
        )
        self.assertIn("camp_region", observer_faction)
        self.assertIn("tribalization_progress", observer_faction)

        view_model = build_simulation_view_model(world)
        view_faction = next(
            faction
            for faction in view_model["factions"]
            if faction["name"] == faction_name
        )
        self.assertIn("camp_region", view_faction)
        self.assertIn("migration_pressure", view_faction)

        html = render_simulation_html(world)
        self.assertIn("Band Mobility", html)
        self.assertIn("Tribalization", html)


if __name__ == "__main__":
    unittest.main()
