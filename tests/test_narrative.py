import unittest

from src.models import Event, Faction, FactionIdentity, Region, WorldState
from src.narrative import (
    build_chronicle,
    summarize_final_standings,
    summarize_phases,
    summarize_strategic_interpretation,
    summarize_victor_history,
)


def _identity(internal_id: str, culture_name: str, display_name: str) -> FactionIdentity:
    return FactionIdentity(
        internal_id=internal_id,
        culture_name=culture_name,
        display_name=display_name,
    )


def _snapshot(turn: int, entries: dict[str, tuple[int, int]]) -> dict:
    return {
        "turn": turn,
        "factions": {
            faction_name: {
                "treasury": treasury,
                "regions": regions,
                "administrative_overextension": 0.0,
                "trade_warfare_damage": 0.0,
                "trade_blockade_losses": 0.0,
                "trade_income": 0.0,
                "tribute_income": 0.0,
                "migration_inflow": 0,
                "migration_outflow": 0,
                "refugee_inflow": 0,
                "refugee_outflow": 0,
            }
            for faction_name, (treasury, regions) in entries.items()
        },
    }


class NarrativeTests(unittest.TestCase):
    def _build_fracture_world(self) -> WorldState:
        factions = {
            "A": Faction(
                name="A",
                treasury=16,
                starting_treasury=6,
                identity=_identity("A", "Auric", "Auric Kingdom"),
                primary_ethnicity="Auric",
            ),
            "B": Faction(
                name="B",
                treasury=7,
                starting_treasury=6,
                identity=_identity("B", "Boreal", "Boreal Realm"),
                primary_ethnicity="Boreal",
            ),
            "C": Faction(
                name="C",
                treasury=10,
                starting_treasury=2,
                identity=_identity("C", "Cinder", "Cinder League"),
                primary_ethnicity="Cinder",
                is_rebel=True,
                origin_faction="B",
                rebel_conflict_type="civil_war",
            ),
        }

        regions = {
            "A1": Region("A1", ["A2"], "A", 2),
            "A2": Region("A2", ["A1", "B1"], "A", 2),
            "A3": Region("A3", ["A2", "B2"], "A", 2),
            "B1": Region("B1", ["A2", "B2"], "B", 2),
            "B2": Region("B2", ["A3", "B1"], "C", 2),
        }

        world = WorldState(
            regions=regions,
            factions=factions,
            map_name="test_fracture_map",
        )
        world.turn = 8
        world.region_history = [
            {
                "A1": {"owner": "A"},
                "A2": {"owner": "A"},
                "A3": {"owner": None},
                "B1": {"owner": "B"},
                "B2": {"owner": "B"},
            }
        ]
        world.metrics = [
            _snapshot(1, {"A": (7, 2), "B": (7, 2)}),
            _snapshot(2, {"A": (8, 3), "B": (7, 2)}),
            _snapshot(3, {"A": (9, 3), "B": (6, 2)}),
            _snapshot(4, {"A": (10, 3), "B": (5, 1), "C": (3, 1)}),
            _snapshot(5, {"A": (12, 3), "B": (5, 1), "C": (5, 1)}),
            _snapshot(6, {"A": (13, 3), "B": (6, 1), "C": (7, 1)}),
            _snapshot(7, {"A": (15, 3), "B": (7, 1), "C": (9, 1)}),
            _snapshot(8, {"A": (16, 3), "B": (7, 1), "C": (10, 1)}),
        ]
        world.events = [
            Event(
                turn=1,
                type="war_declared",
                faction="A",
                region="B1",
                details={
                    "defender": "B",
                    "counterpart": "B",
                    "war_objective_label": "territorial conquest",
                },
                tags=["diplomacy", "war", "declaration"],
                significance=1.0,
            ),
            Event(
                turn=2,
                type="succession_crisis",
                faction="B",
                region="B2",
                details={
                    "claimant_faction": "C",
                    "claimant_region": "B2",
                },
                tags=["politics", "succession", "crisis", "claimant"],
                significance=1.2,
            ),
            Event(
                turn=3,
                type="unrest_secession",
                faction="B",
                region="B2",
                details={
                    "rebel_faction": "C",
                    "conflict_type": "civil_war",
                    "joined_region_count": 0,
                },
                impact={"owner_after": "C", "joined_region_count": 0},
                tags=["unrest", "civil_war", "collapse"],
                significance=9.9,
            ),
            Event(
                turn=4,
                type="rebel_independence",
                faction="C",
                details={
                    "origin_faction": "B",
                    "conflict_type": "civil_war",
                    "successor_ethnicity": "Cinder",
                },
                tags=["rebel", "independence", "statehood", "civil_war"],
                significance=4.4,
            ),
            Event(
                turn=5,
                type="religious_reform",
                faction="A",
                region="A1",
                details={
                    "old_religion": "Old Rite",
                    "new_religion": "Sun Rite",
                },
                tags=["religion", "reform", "legitimacy"],
                significance=0.7,
            ),
            Event(
                turn=6,
                type="war_peace",
                faction="A",
                region="B1",
                details={
                    "winner": "A",
                    "loser": "B",
                    "counterpart": "B",
                    "peace_term": "tributary_settlement",
                },
                tags=["diplomacy", "war", "peace", "tributary"],
                significance=2.3,
            ),
        ]
        return world

    def _build_economic_win_world(self) -> WorldState:
        factions = {
            "A": Faction(
                name="A",
                treasury=18,
                starting_treasury=6,
                identity=_identity("A", "Amber", "Amber Republic"),
                primary_ethnicity="Amber",
            ),
            "B": Faction(
                name="B",
                treasury=14,
                starting_treasury=6,
                identity=_identity("B", "Bluewater", "Bluewater Kingdom"),
                primary_ethnicity="Bluewater",
            ),
        }

        regions = {
            "R1": Region("R1", ["R2"], "A", 2),
            "R2": Region("R2", ["R1", "R3"], "A", 2),
            "R3": Region("R3", ["R2", "R4"], "B", 2),
            "R4": Region("R4", ["R3", "R5"], "B", 2),
            "R5": Region("R5", ["R4"], "B", 2),
        }

        world = WorldState(
            regions=regions,
            factions=factions,
            map_name="test_economic_map",
        )
        world.turn = 6
        world.region_history = [
            {
                "R1": {"owner": "A"},
                "R2": {"owner": "A"},
                "R3": {"owner": "B"},
                "R4": {"owner": "B"},
                "R5": {"owner": "B"},
            }
        ]
        world.metrics = [
            _snapshot(1, {"A": (7, 2), "B": (7, 3)}),
            _snapshot(2, {"A": (9, 2), "B": (8, 3)}),
            _snapshot(3, {"A": (11, 2), "B": (10, 3)}),
            _snapshot(4, {"A": (14, 2), "B": (11, 3)}),
            _snapshot(5, {"A": (16, 2), "B": (13, 3)}),
            _snapshot(6, {"A": (18, 2), "B": (14, 3)}),
        ]
        world.events = [
            Event(
                turn=1,
                type="develop",
                faction="A",
                region="R1",
                details={"project_type": "market_build", "taxable_change": 1.2},
                impact={"taxable_change": 1.2, "importance_score": 2.0},
                tags=["development", "investment", "market_build"],
                significance=1.2,
            ),
            Event(
                turn=2,
                type="develop",
                faction="A",
                region="R2",
                details={"project_type": "road_build", "taxable_change": 1.0},
                impact={"taxable_change": 1.0, "importance_score": 1.8},
                tags=["development", "investment", "road_build"],
                significance=1.0,
            ),
            Event(
                turn=4,
                type="diplomacy_alliance",
                faction="A",
                details={"counterpart": "B"},
                tags=["diplomacy", "alliance"],
                significance=0.8,
            ),
        ]
        world.metrics[-1]["factions"]["A"]["trade_income"] = 1.6
        world.metrics[-1]["factions"]["A"]["tribute_income"] = 0.6
        return world

    def _build_tied_finish_world(self) -> WorldState:
        factions = {
            "A": Faction(
                name="A",
                treasury=12,
                starting_treasury=6,
                identity=_identity("A", "Ashen", "Ashen Republic"),
                primary_ethnicity="Ashen",
            ),
            "B": Faction(
                name="B",
                treasury=12,
                starting_treasury=6,
                identity=_identity("B", "Brightwater", "Brightwater Kingdom"),
                primary_ethnicity="Brightwater",
            ),
        }

        regions = {
            "R1": Region("R1", ["R2"], "A", 2),
            "R2": Region("R2", ["R1", "R3"], "A", 2),
            "R3": Region("R3", ["R2", "R4"], "B", 2),
            "R4": Region("R4", ["R3"], "B", 2),
        }

        world = WorldState(
            regions=regions,
            factions=factions,
            map_name="test_tied_finish_map",
        )
        world.turn = 5
        world.region_history = [
            {
                "R1": {"owner": "A"},
                "R2": {"owner": "A"},
                "R3": {"owner": "B"},
                "R4": {"owner": "B"},
            }
        ]
        world.metrics = [
            _snapshot(1, {"A": (7, 2), "B": (7, 2)}),
            _snapshot(2, {"A": (8, 2), "B": (8, 2)}),
            _snapshot(3, {"A": (9, 2), "B": (9, 2)}),
            _snapshot(4, {"A": (11, 2), "B": (11, 2)}),
            _snapshot(5, {"A": (12, 2), "B": (12, 2)}),
        ]
        world.events = [
            Event(
                turn=1,
                type="develop",
                faction="A",
                region="R1",
                details={"project_type": "market_build", "taxable_change": 1.0},
                impact={"taxable_change": 1.0},
                tags=["development", "investment", "market_build"],
                significance=1.0,
            ),
            Event(
                turn=2,
                type="develop",
                faction="B",
                region="R3",
                details={"project_type": "road_build", "taxable_change": 1.0},
                impact={"taxable_change": 1.0},
                tags=["development", "investment", "road_build"],
                significance=1.0,
            ),
            Event(
                turn=3,
                type="diplomacy_alliance",
                faction="A",
                details={"counterpart": "B"},
                tags=["diplomacy", "alliance"],
                significance=0.7,
            ),
        ]
        return world

    def test_build_chronicle_surfaces_new_sections_and_major_shocks(self):
        world = self._build_fracture_world()

        chronicle = build_chronicle(world)

        self.assertIn("Outcome Explanation", chronicle)
        self.assertIn("Structural Drivers", chronicle)
        self.assertIn("Faction Epilogues", chronicle)
        self.assertIn("succession crisis", chronicle.lower())
        self.assertIn("civil war", chronicle.lower())
        self.assertIn("sun rite", chronicle.lower())

    def test_strategic_interpretation_recognizes_fractured_order(self):
        world = self._build_fracture_world()

        lines = summarize_strategic_interpretation(world)
        combined = " ".join(lines).lower()

        self.assertIn("fractured order", combined)
        self.assertIn("internal fracture", combined)

    def test_phase_summaries_cover_early_mid_and_late_game(self):
        world = self._build_fracture_world()

        analyses, summaries = summarize_phases(world)

        self.assertEqual([analysis.name for analysis in analyses], ["Early", "Mid", "Late"])
        self.assertEqual(len(summaries), 3)
        self.assertTrue(summaries[0].startswith("Early"))
        self.assertTrue(summaries[1].startswith("Mid"))
        self.assertTrue(summaries[2].startswith("Late"))

    def test_economic_win_is_called_out_explicitly(self):
        world = self._build_economic_win_world()

        lines = summarize_strategic_interpretation(world)
        combined = " ".join(lines).lower()

        self.assertIn("fewer regions", combined)
        self.assertIn("economic conversion", combined)

    def test_victor_history_names_winner_and_rival(self):
        world = self._build_fracture_world()

        lines = summarize_victor_history(world)
        combined = " ".join(lines)

        self.assertIn("Auric Kingdom", combined)
        self.assertIn("Cinder League", combined)
        self.assertIn("tributary settlement", combined.lower())

    def test_tied_finish_gets_dead_heat_language(self):
        world = self._build_tied_finish_world()

        lines = summarize_strategic_interpretation(world)
        final_lines = summarize_final_standings(world)
        victor_lines = summarize_victor_history(world)
        combined = " ".join(lines).lower()
        standings = " ".join(final_lines).lower()
        victor_text = " ".join(victor_lines).lower()

        self.assertIn("dead heat", combined)
        self.assertIn("tie-break", combined)
        self.assertIn("tied on both measures", standings)
        self.assertIn("matched them measure for measure", victor_text)
        self.assertNotIn("final treasury edge", victor_text)

    def test_build_chronicle_honors_turning_point_limit(self):
        world = self._build_fracture_world()

        chronicle = build_chronicle(world, max_key_events=1)
        turning_points_section = chronicle.split("Turning Points", 1)[1].split("Structural Drivers", 1)[0]

        self.assertEqual(turning_points_section.count("On turn"), 1)


if __name__ == "__main__":
    unittest.main()
