import unittest

from src.actions import attack, expand, get_attackable_regions, get_expandable_regions
from src.integration import handle_region_owner_change
from src.metrics import build_turn_metrics
from src.player_view import build_observer_snapshot
from src.simulation_ui import build_simulation_view_model, render_simulation_html
from src.social_forms import (
    BAND_HOMELAND_MIN_ROAMING_TURNS,
    BAND_MIGRATION_COST,
    get_band_camp_region_name,
    is_nomadic_tribe,
    update_nomadic_social_forms,
    _unique_nomadic_splinter_band_name,
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
        camp_region.population = 13000
        camp_region.settlement_level = "rural"
        camp_region.food_deficit = 0.0
        camp_region.unrest = 0.0
        faction.tribalization_progress = 0.95
        faction.band_settled_turns = 3

        events = update_nomadic_social_forms(world)

        self.assertEqual(faction.polity_tier, "tribe")
        self.assertEqual(faction.government_form, "council")
        transition = next(
            event
            for event in events
            if event.type == "social_form_transition" and event.faction == faction_name
        )
        self.assertEqual(transition.details["from"], "band")
        self.assertEqual(transition.details["to"], "tribe")

    def test_unsettled_bands_roam_without_treasury_action(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-roaming")
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        old_camp = get_band_camp_region_name(world, faction_name)
        faction.treasury = 0

        events = update_nomadic_social_forms(world)

        new_camp = get_band_camp_region_name(world, faction_name)
        self.assertNotEqual(new_camp, old_camp)
        self.assertEqual(faction.social_form, "nomadic_band")
        self.assertIn(old_camp, faction.band_explored_regions)
        self.assertIn(new_camp, faction.band_explored_regions)
        self.assertIsNone(world.regions[old_camp].owner)
        self.assertIsNone(world.regions[new_camp].homeland_faction_id)
        self.assertTrue(
            any(
                event.type == "band_migration"
                and event.faction == faction_name
                and event.details["reason"] == "seasonal_roaming"
                for event in events
            )
        )

    def test_band_chooses_homeland_from_appealing_camp_name_root(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-homeland")
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        camp_name = get_band_camp_region_name(world, faction_name)
        camp_region = world.regions[camp_name]
        camp_region.display_name = "Ganesh Plains"
        camp_region.population = 13000
        camp_region.settlement_level = "rural"
        faction.social_form = "nomadic_band"
        faction.band_roaming_turns = BAND_HOMELAND_MIN_ROAMING_TURNS
        faction.best_homeland_candidate = camp_name
        faction.best_homeland_appeal = 25.0
        for neighbor_name in list(camp_region.neighbors):
            if world.regions[neighbor_name].owner is None:
                handle_region_owner_change(world.regions[neighbor_name], "Faction2")

        update_nomadic_social_forms(world)

        self.assertEqual(faction.social_form, "sedentary_band")
        self.assertEqual(faction.chosen_homeland_region, camp_name)
        self.assertEqual(camp_region.homeland_faction_id, faction_name)
        self.assertEqual(faction.culture_name, "Ganesh")
        self.assertEqual(faction.display_name, "Ganesh Band")

        faction.tribalization_progress = 0.95
        faction.band_settled_turns = 3
        update_nomadic_social_forms(world)

        self.assertEqual(faction.polity_tier, "tribe")
        self.assertEqual(faction.social_form, "sedentary_tribe")
        self.assertEqual(faction.display_name, "Ganesh Tribe")

    def test_nomadic_tribes_have_no_homeland_and_fragment_under_pressure(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="nomadic-tribe")
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        second_region = get_expandable_regions(faction_name, world)[0]
        handle_region_owner_change(world.regions[second_region], faction_name)
        faction.identity.set_government_structure("tribe", "council", update_display_name=True)
        faction.social_form = "nomadic_tribe"
        faction.chosen_homeland_region = None
        faction.faction_traits.append("chaos_pioneers")
        faction.treasury = 20
        for region in world.regions.values():
            if region.owner == faction_name:
                region.homeland_faction_id = None
                region.core_status = "frontier"
                region.unrest = 16.0

        events = update_nomadic_social_forms(world)

        self.assertTrue(is_nomadic_tribe(faction))
        self.assertIsNone(faction.chosen_homeland_region)
        self.assertGreaterEqual(faction.nomadic_fragmentation_pressure, 0.62)
        split_event = next(
            event
            for event in events
            if event.type == "nomadic_tribe_fragmentation" and event.faction == faction_name
        )
        splinter_name = split_event.details["splinter_faction"]
        self.assertIn(splinter_name, world.factions)
        self.assertEqual(world.factions[splinter_name].polity_tier, "band")
        self.assertEqual(world.factions[splinter_name].social_form, "nomadic_band")
        self.assertNotRegex(splinter_name, r"\d+$")

    def test_nomadic_splinter_band_names_use_distinct_epithets(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="nomadic-splinter-names")
        prototype = next(iter(world.factions.values()))

        first_name = _unique_nomadic_splinter_band_name(world, "Mithala")
        world.factions[first_name] = prototype
        second_name = _unique_nomadic_splinter_band_name(world, "Mithala")

        self.assertNotEqual(first_name, second_name)
        self.assertTrue(first_name.startswith("Mithala "))
        self.assertTrue(second_name.startswith("Mithala "))
        self.assertTrue(first_name.endswith(" Band"))
        self.assertTrue(second_name.endswith(" Band"))
        self.assertNotRegex(first_name, r"\d")
        self.assertNotRegex(second_name, r"\d")

    def test_band_state_is_exposed_in_metrics_observer_and_html(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="band-visibility")
        faction_name = next(iter(world.factions))

        metrics = build_turn_metrics(world)
        faction_metrics = metrics["factions"][faction_name]
        self.assertIn("camp_region", faction_metrics)
        self.assertIn("social_form", faction_metrics)
        self.assertIn("homeland_region", faction_metrics)
        self.assertIn("band_explored_regions", faction_metrics)
        self.assertIn("nomadic_fragmentation_pressure", faction_metrics)
        self.assertIn("tribalization_progress", faction_metrics)
        self.assertIn("migration_pressure", faction_metrics)

        observer_faction = next(
            faction
            for faction in build_observer_snapshot(world)["factions"]
            if faction["name"] == faction_name
        )
        self.assertIn("camp_region", observer_faction)
        self.assertIn("social_form", observer_faction)
        self.assertIn("homeland_region", observer_faction)
        self.assertIn("band_explored_regions", observer_faction)
        self.assertIn("tribalization_progress", observer_faction)

        view_model = build_simulation_view_model(world)
        view_faction = next(
            faction
            for faction in view_model["factions"]
            if faction["name"] == faction_name
        )
        self.assertIn("camp_region", view_faction)
        self.assertIn("social_form", view_faction)
        self.assertIn("homeland_region", view_faction)
        self.assertIn("migration_pressure", view_faction)

        html = render_simulation_html(world)
        self.assertIn("Band Mobility", html)
        self.assertIn("Social Form", html)
        self.assertIn("Homeland Search", html)
        self.assertIn("Tribalization", html)


if __name__ == "__main__":
    unittest.main()
