import unittest

from src.actions import get_attack_target_score_components, get_attackable_regions
from src.diplomacy import (
    get_attack_diplomacy_modifier,
    get_faction_diplomacy_summary,
    get_relationship_state,
    get_relationship_status,
    initialize_relationships,
    seed_rebel_origin_relationship,
    update_relationships,
)
from src.models import Event, Faction, Region, RelationshipState, WorldState
from src.simulation_ui import _serialize_event


class DiplomacySystemTests(unittest.TestCase):
    def _make_two_faction_border_world(self) -> WorldState:
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=4,
                    population=100,
                    ethnic_composition={"Aeth": 100},
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=4,
                    population=100,
                    ethnic_composition={"Beth": 100},
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA", treasury=8, primary_ethnicity="Aeth"),
                "FactionB": Faction(name="FactionB", treasury=8, primary_ethnicity="Beth"),
            },
        )
        initialize_relationships(world)
        return world

    def test_initialize_relationships_starts_all_pairs_neutral(self):
        world = WorldState(
            regions={},
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
                "FactionC": Faction(name="FactionC"),
            },
        )

        initialize_relationships(world)

        self.assertEqual(len(world.relationships), 3)
        self.assertEqual(get_relationship_status(world, "FactionA", "FactionB"), "neutral")
        self.assertEqual(get_relationship_status(world, "FactionA", "FactionC"), "neutral")
        self.assertEqual(get_relationship_status(world, "FactionB", "FactionC"), "neutral")

    def test_attack_event_generates_grievance_and_negative_relation(self):
        world = self._make_two_faction_border_world()
        world.turn = 1
        world.events.append(Event(
            turn=1,
            type="attack",
            faction="FactionA",
            region="B",
            details={
                "defender": "FactionB",
                "success": True,
            },
        ))

        update_relationships(world)
        state = get_relationship_state(world, "FactionA", "FactionB")

        self.assertGreater(state.grievance, 0.0)
        self.assertEqual(state.years_at_peace, 0)
        self.assertEqual(state.last_conflict_turn, 1)
        self.assertLess(state.score, 0.0)

    def test_alliance_blocks_attackable_regions(self):
        world = self._make_two_faction_border_world()
        world.relationships[("FactionA", "FactionB")] = RelationshipState(
            score=82.0,
            status="alliance",
            years_at_peace=4,
            trust=20.0,
        )

        attackable = get_attackable_regions("FactionA", world)

        self.assertEqual(attackable, [])
        modifier, status = get_attack_diplomacy_modifier(world, "FactionA", "FactionB")
        self.assertEqual(status, "alliance")
        self.assertLess(modifier, -100)

    def test_truce_blocks_attackable_regions_and_then_expires(self):
        world = self._make_two_faction_border_world()
        world.relationships[("FactionA", "FactionB")] = RelationshipState(
            score=-6.0,
            status="truce",
            truce_turns_remaining=1,
            grievance=18.0,
            trust=4.0,
        )

        self.assertEqual(get_attackable_regions("FactionA", world), [])
        modifier, status = get_attack_diplomacy_modifier(world, "FactionA", "FactionB")
        self.assertEqual(status, "truce")
        self.assertLess(modifier, -100)

        world.turn = 1
        update_relationships(world)

        self.assertEqual(get_relationship_status(world, "FactionA", "FactionB"), "neutral")

    def test_non_aggression_pact_reduces_attack_score_vs_neutral(self):
        neutral_world = self._make_two_faction_border_world()
        neutral_score = get_attack_target_score_components("B", "FactionA", neutral_world)

        pact_world = self._make_two_faction_border_world()
        pact_world.relationships[("FactionA", "FactionB")] = RelationshipState(
            score=50.0,
            status="non_aggression_pact",
            years_at_peace=3,
            trust=18.0,
        )
        pact_score = get_attack_target_score_components("B", "FactionA", pact_world)

        self.assertEqual(pact_score["diplomacy_status"], "non_aggression_pact")
        self.assertEqual(pact_score["diplomacy_attack_modifier"], -45)
        self.assertLess(pact_score["score"], neutral_score["score"])

    def test_ethnic_claim_pressure_worsens_relations_when_claims_are_occupied(self):
        world = self._make_two_faction_border_world()
        world.regions["B"].ethnic_composition = {"Aeth": 100}
        world.turn = 1

        update_relationships(world)
        state = get_relationship_state(world, "FactionA", "FactionB")

        self.assertLess(state.score, 0.0)
        self.assertEqual(state.status, "neutral")

    def test_ethnic_claim_bonus_improves_attack_score_for_claimed_region(self):
        neutral_world = self._make_two_faction_border_world()
        neutral_score = get_attack_target_score_components("B", "FactionA", neutral_world)

        claim_world = self._make_two_faction_border_world()
        claim_world.regions["B"].ethnic_composition = {"Aeth": 100}
        claim_score = get_attack_target_score_components("B", "FactionA", claim_world)

        self.assertEqual(claim_score["ethnic_claim_bonus"], 4)
        self.assertGreater(claim_score["attacker_strength"], neutral_score["attacker_strength"])
        self.assertGreater(claim_score["score"], neutral_score["score"])

    def test_rebel_origin_relationship_starts_with_secession_truce(self):
        world = WorldState(
            regions={},
            factions={
                "Parent": Faction(name="Parent"),
                "Rebels": Faction(name="Rebels", is_rebel=True, origin_faction="Parent", proto_state=True),
            },
        )
        initialize_relationships(world)

        seed_rebel_origin_relationship(world, "Rebels", "Parent")
        state = get_relationship_state(world, "Rebels", "Parent")

        self.assertEqual(state.status, "truce")
        self.assertGreater(state.truce_turns_remaining, 0)
        self.assertGreater(state.trust, 0.0)
        self.assertGreater(state.grievance, 0.0)

    def test_diplomacy_summary_picks_top_ally_and_rival(self):
        world = WorldState(
            regions={},
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
                "FactionC": Faction(name="FactionC"),
                "FactionD": Faction(name="FactionD"),
            },
        )
        initialize_relationships(world)
        world.relationships[("FactionA", "FactionB")] = RelationshipState(
            score=78.0,
            status="alliance",
            years_at_peace=5,
            trust=24.0,
        )
        world.relationships[("FactionA", "FactionC")] = RelationshipState(
            score=46.0,
            status="non_aggression_pact",
            years_at_peace=3,
            trust=16.0,
        )
        world.relationships[("FactionA", "FactionD")] = RelationshipState(
            score=-58.0,
            status="rival",
            grievance=25.0,
        )

        summary = get_faction_diplomacy_summary(world, "FactionA")

        self.assertEqual(summary["top_ally"], "FactionB")
        self.assertEqual(summary["top_rival"], "FactionD")
        self.assertEqual(summary["alliance_count"], 1)
        self.assertEqual(summary["truce_count"], 0)
        self.assertEqual(summary["pact_count"], 1)
        self.assertEqual(summary["rival_count"], 1)

    def test_diplomacy_summary_reports_top_claim_dispute(self):
        world = self._make_two_faction_border_world()
        world.regions["B"].ethnic_composition = {"Aeth": 100}

        summary = get_faction_diplomacy_summary(world, "FactionA")

        self.assertEqual(summary["top_claim_dispute"], "FactionB")
        self.assertEqual(summary["top_claim_dispute_ethnicity"], "Aeth")
        self.assertEqual(summary["top_claim_dispute_regions"], 1)
        self.assertEqual(summary["claim_dispute_count"], 1)

    def test_serialized_attack_event_mentions_claim_offensive(self):
        world = self._make_two_faction_border_world()
        event = Event(
            turn=0,
            type="attack",
            faction="FactionA",
            region="B",
            details={
                "defender": "FactionB",
                "success": True,
                "success_chance": 0.61,
                "ethnic_claim_attack": True,
                "claim_ethnicity": "Aeth",
            },
        )

        serialized = _serialize_event(event, world)

        self.assertIn("claim offensive", serialized["title"].lower())
        self.assertIn("claim-driven", serialized["summary"].lower())

    def test_serialized_secession_event_mentions_restoration_revolt(self):
        world = self._make_two_faction_border_world()
        event = Event(
            turn=0,
            type="unrest_secession",
            faction="FactionB",
            region="B",
            details={
                "rebel_faction": "FactionA",
                "restoration": True,
                "restored_faction": "FactionA",
                "revived_ethnicity": "Aeth",
            },
        )

        serialized = _serialize_event(event, world)

        self.assertIn("restored", serialized["title"].lower())
        self.assertIn("restoration revolt", serialized["summary"].lower())


if __name__ == "__main__":
    unittest.main()
