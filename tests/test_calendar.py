import unittest
from unittest.mock import patch

import main as clash_main
from src.calendar import (
    format_snapshot_date,
    format_turn_date,
    format_turn_span,
    get_snapshot_season_name,
    get_snapshot_year,
    is_year_end,
)
from src.models import Event
from src.simulation import run_turn
from src.simulation_ui import build_simulation_snapshots
from src.world import create_world


class CalendarHelpersTests(unittest.TestCase):
    def test_turn_dates_follow_seasonal_cycle(self):
        self.assertEqual(format_turn_date(0), "Year 1, Spring")
        self.assertEqual(format_turn_date(1), "Year 1, Summer")
        self.assertEqual(format_turn_date(2), "Year 1, Autumn")
        self.assertEqual(format_turn_date(3), "Year 1, Winter")
        self.assertEqual(format_turn_date(4), "Year 2, Spring")
        self.assertTrue(is_year_end(3))
        self.assertFalse(is_year_end(2))

    def test_snapshot_helpers_and_duration_text(self):
        self.assertEqual(get_snapshot_year(1), 1)
        self.assertEqual(get_snapshot_season_name(1), "Spring")
        self.assertEqual(format_snapshot_date(4), "Year 1, Winter")
        self.assertEqual(format_turn_span(9), "2 years and 1 season")


class SeasonalCadenceTests(unittest.TestCase):
    def test_slow_systems_only_resolve_at_year_end(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="calendar-cadence")

        with patch("src.simulation.choose_action", return_value=("skip", None)), \
            patch("src.simulation.update_religious_legitimacy") as religious_mock, \
            patch("src.simulation.resolve_dynastic_succession") as succession_mock, \
            patch("src.simulation.update_region_populations") as population_mock, \
            patch("src.simulation.update_region_settlement_levels") as settlement_mock, \
            patch("src.simulation.update_rebel_faction_status") as rebel_mock, \
            patch("src.simulation.update_faction_polity_tiers") as polity_mock:
            for _ in range(4):
                run_turn(world, randomize_order=False, verbose=False)

        self.assertEqual(religious_mock.call_count, 1)
        self.assertEqual(succession_mock.call_count, 1)
        self.assertEqual(population_mock.call_count, 1)
        self.assertEqual(settlement_mock.call_count, 1)
        self.assertEqual(rebel_mock.call_count, 1)
        self.assertEqual(polity_mock.call_count, 1)

    def test_snapshots_and_event_format_include_calendar_labels(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4, seed="calendar-ui")
        with patch("src.simulation.choose_action", return_value=("skip", None)):
            for _ in range(4):
                run_turn(world, randomize_order=False, verbose=False)

        snapshots = build_simulation_snapshots(world)
        self.assertEqual(snapshots[1]["date_label"], "Year 1, Spring")
        self.assertEqual(snapshots[4]["date_label"], "Year 1, Winter")

        event = Event(turn=0, type="expand", faction=next(iter(world.factions)), region="M")
        formatted = clash_main.format_event(event, world)
        self.assertIn("Year 1, Spring", formatted)


if __name__ == "__main__":
    unittest.main()
