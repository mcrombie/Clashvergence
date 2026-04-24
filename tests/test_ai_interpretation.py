import unittest

from src.ai_interpretation import build_ai_interpretation_summary
from src.models import (
    Event,
    Faction,
    FactionIdentity,
    Region,
    Religion,
    WorldState,
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
            }
            for faction_name, (treasury, regions) in entries.items()
        },
    }


class AIInterpretationSummaryTests(unittest.TestCase):
    def _build_world(self) -> WorldState:
        factions = {
            "A": Faction(
                name="A",
                treasury=20,
                starting_treasury=8,
                identity=_identity("A", "Aruangos", "Aruangos State"),
                primary_ethnicity="Aruangos",
            ),
            "B": Faction(
                name="B",
                treasury=12,
                starting_treasury=8,
                identity=_identity("B", "Saklian", "Saklian Chiefdom"),
                primary_ethnicity="Saklian",
            ),
            "C": Faction(
                name="C",
                treasury=6,
                starting_treasury=2,
                identity=_identity("C", "Ivory", "Ivory Reach Rebels 2"),
                primary_ethnicity="Ivory",
                is_rebel=True,
                origin_faction="B",
                rebel_conflict_type="civil_war",
            ),
        }

        factions["A"].succession.dynasty_name = "House Aru"
        factions["A"].succession.ruler_name = "Teren"
        factions["A"].succession.heir_name = "Meral"
        factions["A"].succession.legitimacy = 0.74
        factions["A"].religion.official_religion = "Farorentan"
        factions["A"].religion.religious_legitimacy = 0.68
        factions["A"].religion.clergy_support = 0.62
        factions["A"].religion.religious_tolerance = 0.39
        factions["A"].religion.religious_zeal = 0.71
        factions["A"].religion.state_cult_strength = 0.66
        factions["A"].religion.sacred_sites_controlled = 2
        factions["A"].religion.total_sacred_sites = 3
        factions["A"].doctrine_profile.dominant_behavior = "developmental"
        factions["A"].doctrine_profile.terrain_identity = "Forest Plains"

        factions["B"].succession.dynasty_name = "House Saka"
        factions["B"].succession.ruler_name = "Velor"
        factions["B"].succession.heir_name = "Iven"
        factions["B"].succession.legitimacy = 0.42
        factions["B"].succession.claimant_pressure = 0.44
        factions["B"].religion.official_religion = "Araerarrite"
        factions["B"].doctrine_profile.dominant_behavior = "martial"
        factions["B"].doctrine_profile.terrain_identity = "Highlands"

        factions["C"].succession.dynasty_name = "House Saka"
        factions["C"].succession.ruler_name = "Neral"
        factions["C"].religion.official_religion = "Araerarrite"
        factions["C"].doctrine_profile.dominant_behavior = "frontier"
        factions["C"].doctrine_profile.terrain_identity = "Marches"

        regions = {
            "I6": Region("I6", ["I7"], "C", 2, display_name="Ivory Ford", population=80),
            "I7": Region("I7", ["I6", "O2"], "B", 2, display_name="Willow March", population=75),
            "O2": Region("O2", ["I7"], "A", 2, display_name="Ash Reach", population=95),
        }
        regions["I6"].religious_composition = {"Araerarrite": 80}
        regions["I7"].religious_composition = {"Araerarrite": 70, "Farorentan": 5}
        regions["O2"].religious_composition = {"Farorentan": 95}
        regions["O2"].sacred_religion = "Farorentan"

        world = WorldState(
            regions=regions,
            factions=factions,
            religions={
                "Araerarrite": Religion(
                    name="Araerarrite",
                    founding_faction="B",
                    doctrine="Ancestor Rite",
                    sacred_terrain_tags=["highland"],
                    sacred_climate="temperate",
                ),
                "Farorentan": Religion(
                    name="Farorentan",
                    founding_faction="A",
                    parent_religion="Araerarrite",
                    doctrine="Reformed River Rite",
                    sacred_terrain_tags=["plains"],
                    sacred_climate="temperate",
                    reform_origin_turn=4,
                ),
            },
            map_name="thirty_seven_region_ring",
        )
        world.turn = 6
        world.metrics = [
            _snapshot(1, {"A": (8, 1), "B": (8, 2)}),
            _snapshot(2, {"A": (10, 1), "B": (8, 2)}),
            _snapshot(3, {"A": (12, 1), "B": (7, 1), "C": (3, 1)}),
            _snapshot(4, {"A": (14, 1), "B": (7, 1), "C": (4, 1)}),
            _snapshot(5, {"A": (18, 1), "B": (8, 1), "C": (5, 1)}),
            _snapshot(6, {"A": (20, 1), "B": (12, 1), "C": (6, 1)}),
        ]
        world.events = [
            Event(
                turn=1,
                type="succession",
                faction="A",
                details={
                    "old_ruler": "Heren",
                    "new_ruler": "Teren",
                    "dynasty_name": "House Aru",
                    "old_dynasty": "House Aru",
                    "succession_type": "orderly",
                    "legitimacy": 0.74,
                },
                tags=["politics", "succession"],
                significance=2.0,
            ),
            Event(
                turn=2,
                type="succession_crisis",
                faction="B",
                region="I6",
                details={
                    "claimant_faction": "C",
                    "claimant_region": "I6",
                    "claimant_pressure": 0.44,
                },
                tags=["politics", "succession", "crisis", "claimant"],
                significance=3.2,
            ),
            Event(
                turn=3,
                type="unrest_secession",
                faction="B",
                region="I6",
                details={
                    "rebel_faction": "C",
                    "conflict_type": "civil_war",
                    "region_display_name": "Ivory Ford",
                },
                tags=["unrest", "civil_war", "collapse"],
                significance=8.5,
            ),
            Event(
                turn=4,
                type="religious_reform",
                faction="A",
                region="O2",
                details={
                    "old_religion": "Araerarrite",
                    "new_religion": "Farorentan",
                },
                tags=["religion", "reform", "legitimacy"],
                significance=2.8,
            ),
            Event(
                turn=5,
                type="migration_wave",
                faction="C",
                region="I6",
                details={
                    "population_moved": 41,
                    "top_destination": "O2",
                },
                tags=["migration"],
                significance=2.4,
            ),
        ]
        return world

    def test_summary_uses_world_identity_calendar_and_display_names(self):
        summary = build_ai_interpretation_summary(self._build_world())

        self.assertTrue(summary["world_identity"]["world_name"].startswith("The "))
        self.assertIn("calendar_name", summary["chronology"])
        self.assertIn("Year", summary["chronology"]["current_year_label"])

        secession_row = next(
            row for row in summary["key_event_digest"] if row["type"] == "unrest_secession"
        )
        self.assertEqual(secession_row["region_display_name"], "Ivory Ford")
        self.assertIn("Ivory Ford", secession_row["brief"])
        self.assertNotIn("I6 broke away", secession_row["brief"])

    def test_summary_includes_religion_succession_vignettes_and_narrative_aliases(self):
        summary = build_ai_interpretation_summary(self._build_world())

        self.assertEqual(summary["religion_digest"]["reforms"][0]["new_religion"], "Farorentan")
        self.assertEqual(summary["succession_digest"]["current_houses"][0]["dynasty_name"], "House Aru")
        self.assertTrue(summary["vignette_prompts"])

        rebel_entry = next(entry for entry in summary["factions"] if entry["name"] == "C")
        self.assertIn("rising", rebel_entry["narrative_name"])
        self.assertNotEqual(rebel_entry["doctrine_gloss"], rebel_entry["doctrine"])


if __name__ == "__main__":
    unittest.main()
