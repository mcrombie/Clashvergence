import unittest

from src.actions import get_attack_target_score_components, get_expand_target_score_components
from src.doctrine import (
    HOMELAND_IMPRINT_WEIGHT,
    compute_faction_doctrine_profile,
    get_faction_region_alignment,
    update_faction_doctrines,
)
from src.models import Event
from src.simulation import run_turn
from src.simulation_ui import (
    build_simulation_snapshots,
    build_simulation_view_model,
    render_simulation_html,
)
from src.terrain import format_terrain_label
from src.world import create_world


class FactionDoctrineTests(unittest.TestCase):
    def test_world_initializes_homeland_doctrine_from_starting_region(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)

        for faction_name, faction in world.factions.items():
            homeland_region = faction.doctrine_state.homeland_region
            self.assertIsNotNone(homeland_region)
            self.assertEqual(
                faction.doctrine_state.homeland_terrain_tags,
                world.regions[homeland_region].terrain_tags,
            )
            self.assertEqual(
                faction.doctrine_profile.homeland_identity,
                format_terrain_label(world.regions[homeland_region].terrain_tags),
            )
            for terrain_tag in faction.doctrine_state.homeland_terrain_tags:
                self.assertEqual(
                    faction.doctrine_state.terrain_experience[terrain_tag],
                    HOMELAND_IMPRINT_WEIGHT,
                )

    def test_matching_terrain_doctrine_improves_region_alignment_scores(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        adapted_name = faction_names[0]
        unadapted_name = faction_names[1]

        target_region = world.regions["M"]
        target_region.terrain_tags = ["forest", "marsh"]

        adapted = world.factions[adapted_name]
        adapted.doctrine_state.homeland_terrain_tags = ["forest", "marsh"]
        adapted.doctrine_state.terrain_experience = {"forest": 20.0, "marsh": 16.0}
        adapted.doctrine_profile = compute_faction_doctrine_profile(
            adapted,
            total_regions=len(world.regions),
        )

        unadapted = world.factions[unadapted_name]
        unadapted.doctrine_state.homeland_terrain_tags = ["plains"]
        unadapted.doctrine_state.terrain_experience = {"plains": 20.0}
        unadapted.doctrine_profile = compute_faction_doctrine_profile(
            unadapted,
            total_regions=len(world.regions),
        )

        adapted_alignment = get_faction_region_alignment(adapted, target_region.terrain_tags)
        unadapted_alignment = get_faction_region_alignment(unadapted, target_region.terrain_tags)

        self.assertGreater(
            adapted_alignment["expansion_modifier"],
            unadapted_alignment["expansion_modifier"],
        )
        self.assertGreater(
            adapted_alignment["combat_modifier"],
            unadapted_alignment["combat_modifier"],
        )
        self.assertGreater(
            get_expand_target_score_components("M", world, faction_name=adapted_name)["score"],
            get_expand_target_score_components("M", world, faction_name=unadapted_name)["score"],
        )

    def test_doctrine_updates_from_turn_events_and_owned_terrain(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        homeland_region = faction.doctrine_state.homeland_region

        world.regions["M"].owner = faction_name
        world.regions["M"].terrain_tags = ["riverland", "plains"]
        world.events.append(Event(turn=0, type="expand", faction=faction_name, region="M"))
        world.events.append(Event(turn=0, type="invest", faction=faction_name, region=homeland_region))
        update_faction_doctrines(world)

        self.assertEqual(faction.doctrine_state.turns_observed, 1)
        self.assertEqual(faction.doctrine_state.expansions, 1)
        self.assertEqual(faction.doctrine_state.investments, 1)
        self.assertEqual(faction.doctrine_state.turns_with_growth, 1)
        self.assertEqual(faction.doctrine_state.turns_with_investment, 1)
        self.assertGreater(faction.doctrine_state.terrain_experience["riverland"], 0.0)
        self.assertGreaterEqual(faction.doctrine_profile.expansion_posture, 0.3)
        self.assertGreaterEqual(faction.doctrine_profile.development_posture, 0.3)

    def test_attack_score_includes_terrain_adaptation_bonus(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.regions["D"].owner = defender_name
        world.regions["D"].terrain_tags = ["highland", "forest"]
        world.factions[attacker_name].treasury = 6
        world.factions[defender_name].treasury = 6

        attacker = world.factions[attacker_name]
        attacker.doctrine_state.homeland_terrain_tags = ["highland", "forest"]
        attacker.doctrine_state.terrain_experience = {"highland": 24.0, "forest": 18.0}
        attacker.doctrine_profile = compute_faction_doctrine_profile(
            attacker,
            total_regions=len(world.regions),
        )

        score_components = get_attack_target_score_components("D", attacker_name, world)

        self.assertGreater(score_components["doctrine_combat_modifier"], 0)
        self.assertGreater(score_components["terrain_affinity"], 0.5)

    def test_metrics_and_snapshots_expose_doctrine_fields(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        run_turn(world, randomize_order=False, verbose=False)

        snapshots = build_simulation_snapshots(world)
        faction_name = next(iter(world.factions))
        metrics = snapshots[1]["metrics"]["factions"][faction_name]

        self.assertIn("doctrine_label", metrics)
        self.assertIn("terrain_identity", metrics)
        self.assertIn("homeland_identity", metrics)
        self.assertIn("expansion_posture", metrics)

    def test_view_model_exposes_faction_doctrine_metadata(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        view_model = build_simulation_view_model(world)
        faction = view_model["factions"][0]

        self.assertIn("doctrine_label", faction)
        self.assertIn("doctrine_summary", faction)
        self.assertIn("terrain_identity", faction)
        self.assertIn("homeland_identity", faction)

    def test_viewer_html_contains_doctrine_timeline_panel(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        html = render_simulation_html(world)

        self.assertIn('id="doctrine-timeline"', html)
        self.assertIn('id="doctrine-timeline-controls"', html)
        self.assertIn("Doctrine Timeline", html)

    def test_viewer_html_contains_atlas_symbol_layer(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)
        html = render_simulation_html(world)

        self.assertIn('id="atlas-symbol-layer"', html)
        self.assertIn("atlas-symbol", html)

    def test_viewer_html_contains_atlas_polity_label_mode(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)
        html = render_simulation_html(world)

        self.assertIn('id="atlas-polity-label-layer"', html)
        self.assertIn('data-terrain="labels"', html)
        self.assertIn('atlasLabelMode: "regions"', html)


if __name__ == "__main__":
    unittest.main()
