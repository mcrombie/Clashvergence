import unittest
from unittest.mock import patch

import main as clash_main
from src.actions import get_attack_target_score_components
from src.agents import choose_action
from src.calendar import (
    format_snapshot_date,
    format_turn_date,
    format_turn_span,
    get_annual_campaign_modifier,
    get_annual_dominant_season,
    get_annual_food_variance,
    get_snapshot_season_name,
    get_snapshot_year,
    is_year_end,
)
from src.models import Event
from src.simulation import run_turn
from src.simulation_ui import build_simulation_snapshots
from src.world import create_world


class CalendarHelpersTests(unittest.TestCase):
    def test_turn_dates_follow_annual_cycle(self):
        self.assertEqual(format_turn_date(0), "Year 1")
        self.assertEqual(format_turn_date(1), "Year 2")
        self.assertEqual(format_turn_date(2), "Year 3")
        self.assertEqual(format_turn_date(3), "Year 4")
        self.assertEqual(format_turn_date(4), "Year 5")
        self.assertTrue(is_year_end(0))
        self.assertTrue(is_year_end(2))

    def test_snapshot_helpers_and_duration_text(self):
        self.assertEqual(get_snapshot_year(1), 1)
        self.assertEqual(get_snapshot_season_name(1), "Spring")
        self.assertEqual(format_snapshot_date(4), "Year 4")
        self.assertEqual(format_turn_span(9), "9 years")
        self.assertGreater(get_annual_campaign_modifier("Summer"), get_annual_campaign_modifier("Winter"))
        self.assertGreater(get_annual_food_variance("Autumn"), get_annual_food_variance("Winter"))
        self.assertEqual(
            get_annual_dominant_season(None, None, turn=3),
            get_annual_dominant_season(None, None, turn=3),
        )


class SeasonalCadenceTests(unittest.TestCase):
    def test_slow_systems_resolve_once_per_annual_turn(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="calendar-cadence")

        with patch("src.simulation.choose_actions", return_value=[]), \
            patch("src.simulation.update_religious_legitimacy") as religious_mock, \
            patch("src.simulation.resolve_dynastic_succession") as succession_mock, \
            patch("src.simulation.update_region_populations") as population_mock, \
            patch("src.simulation.update_region_settlement_levels") as settlement_mock, \
            patch("src.simulation.update_rebel_faction_status") as rebel_mock, \
            patch("src.simulation.update_faction_polity_tiers") as polity_mock:
            for _ in range(4):
                run_turn(world, randomize_order=False, verbose=False)

        self.assertEqual(religious_mock.call_count, 4)
        self.assertEqual(succession_mock.call_count, 4)
        self.assertEqual(population_mock.call_count, 4)
        self.assertEqual(settlement_mock.call_count, 4)
        self.assertEqual(rebel_mock.call_count, 4)
        self.assertEqual(polity_mock.call_count, 4)

    def test_snapshots_and_event_format_include_calendar_labels(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="calendar-ui")
        world.regions["M"].terrain_tags = ["highland", "forest"]
        with patch("src.simulation.choose_actions", return_value=[]):
            for _ in range(4):
                run_turn(world, randomize_order=False, verbose=False)

        snapshots = build_simulation_snapshots(world)
        self.assertEqual(snapshots[1]["date_label"], "Year 1")
        self.assertEqual(snapshots[4]["date_label"], "Year 4")
        self.assertIsInstance(snapshots[4]["regions"]["M"]["seasonal_terrain_note"], str)

        event = Event(turn=0, type="expand", faction=next(iter(world.factions)), region="M")
        formatted = clash_main.format_event(event, world)
        self.assertIn("Year 1", formatted)

        attack_event = Event(turn=3, type="attack", faction=next(iter(world.factions)), region="M")
        attack_formatted = clash_main.format_event(attack_event, world)
        self.assertIn("Year 4", attack_formatted)

    def test_winter_attack_projection_is_harsher_than_summer(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="seasonal-combat")
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.regions["D"].owner = defender_name
        world.regions["D"].integrated_owner = defender_name
        world.factions[attacker_name].treasury = 6
        world.factions[defender_name].treasury = 6

        with patch("src.actions.get_annual_dominant_season", return_value="Summer"):
            summer_score = get_attack_target_score_components("D", attacker_name, world)
        with patch("src.actions.get_annual_dominant_season", return_value="Winter"):
            winter_score = get_attack_target_score_components("D", attacker_name, world)

        self.assertGreater(summer_score["success_chance"], winter_score["success_chance"])
        self.assertGreater(summer_score["score"], winter_score["score"])
        self.assertEqual(summer_score["season"], "Summer")
        self.assertEqual(winter_score["season"], "Winter")

    def test_choose_action_shifts_toward_development_in_winter(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="seasonal-agents")
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]
        faction.doctrine_profile.war_posture = 0.35
        faction.doctrine_profile.expansion_posture = 0.35
        faction.doctrine_profile.development_posture = 0.8
        faction.doctrine_profile.insularity = 0.75
        faction.treasury = 10

        with patch("src.agents.get_attackable_regions", return_value=["D"]), \
            patch("src.agents.get_expandable_regions", return_value=[]), \
            patch("src.agents.get_developable_regions", return_value=["A"]), \
            patch("src.agents.choose_attack_target", return_value="D"), \
            patch("src.agents.choose_develop_target", return_value="A"), \
            patch("src.agents.score_attack_target", return_value=68), \
            patch("src.agents.get_attack_target_score_components", return_value={"diplomacy_status": "neutral", "score": 68}), \
            patch("src.agents.get_development_target_score_components", return_value={"score": 4.0}):
            with patch("src.agents.get_annual_dominant_season", return_value="Summer"):
                summer_action = choose_action(faction_name, world)
            with patch("src.agents.get_annual_dominant_season", return_value="Winter"):
                winter_action = choose_action(faction_name, world)

        self.assertEqual(summer_action, ("attack", "D"))
        self.assertEqual(winter_action, ("develop", "A"))


if __name__ == "__main__":
    unittest.main()
