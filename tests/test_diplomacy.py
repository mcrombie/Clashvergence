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
from src.models import Event, Faction, FactionIdentity, Region, RelationshipState, WorldState
from src.simulation_ui import _serialize_event
from src.visibility import establish_faction_contact, initialize_faction_visibility, refresh_faction_visibility
from src.world import create_world


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

    def test_mature_civil_war_claimant_generates_regime_legitimacy_pressure(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="Parent",
                    resources=4,
                    population=100,
                    ethnic_composition={"Valeri": 100},
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="Claimant",
                    resources=4,
                    population=100,
                    ethnic_composition={"Valeri": 100},
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
            },
            factions={
                "Parent": Faction(
                    name="Parent",
                    treasury=8,
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction1",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="monarchy",
                    ),
                ),
                "Claimant": Faction(
                    name="Claimant",
                    treasury=8,
                    primary_ethnicity="Valeri",
                    is_rebel=True,
                    origin_faction="Parent",
                    rebel_conflict_type="civil_war",
                    proto_state=False,
                    identity=FactionIdentity(
                        internal_id="Faction2",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="republic",
                    ),
                ),
            },
        )
        initialize_relationships(world)

        update_relationships(world)
        summary = get_faction_diplomacy_summary(world, "Parent")
        state = get_relationship_state(world, "Parent", "Claimant")

        self.assertLess(state.score, 0.0)
        self.assertEqual(summary["top_regime_tension"], "Claimant")
        self.assertEqual(summary["top_regime_tension_reason"], "civil_war_legitimacy")
        self.assertEqual(summary["regime_tension_count"], 1)

    def test_same_ethnicity_regime_difference_without_claimant_reports_regime_split(self):
        world = WorldState(
            regions={},
            factions={
                "Council": Faction(
                    name="Council",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction1",
                        culture_name="Valeri",
                        polity_tier="tribe",
                        government_form="council",
                    ),
                ),
                "Assembly": Faction(
                    name="Assembly",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction2",
                        culture_name="Valeri",
                        polity_tier="tribe",
                        government_form="assembly",
                    ),
                ),
            },
        )
        initialize_relationships(world)

        summary = get_faction_diplomacy_summary(world, "Council")

        self.assertEqual(summary["top_regime_tension"], "Assembly")
        self.assertEqual(summary["top_regime_tension_reason"], "regime_difference")

    def test_same_ethnicity_calm_regimes_gain_accommodation_bonus(self):
        calm_world = WorldState(
            regions={},
            factions={
                "Council": Faction(
                    name="Council",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction1",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="council",
                    ),
                ),
                "Republic": Faction(
                    name="Republic",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction2",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="republic",
                    ),
                ),
            },
        )
        initialize_relationships(calm_world)

        harsh_world = WorldState(
            regions={},
            factions={
                "Monarchy": Faction(
                    name="Monarchy",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction3",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="monarchy",
                    ),
                ),
                "Oligarchy": Faction(
                    name="Oligarchy",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction4",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="oligarchy",
                    ),
                ),
            },
        )
        initialize_relationships(harsh_world)

        update_relationships(calm_world)
        update_relationships(harsh_world)

        calm_summary = get_faction_diplomacy_summary(calm_world, "Council")
        calm_state = get_relationship_state(calm_world, "Council", "Republic")
        harsh_state = get_relationship_state(harsh_world, "Monarchy", "Oligarchy")

        self.assertEqual(calm_summary["top_regime_accommodation"], "Republic")
        self.assertEqual(calm_summary["top_regime_accommodation_reason"], "diplomatic_restraint")
        self.assertEqual(calm_summary["regime_accommodation_count"], 1)
        self.assertGreater(calm_state.score, harsh_state.score)

    def test_same_form_calm_regimes_report_same_people_accord(self):
        world = WorldState(
            regions={},
            factions={
                "CouncilA": Faction(
                    name="CouncilA",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction1",
                        culture_name="Valeri",
                        polity_tier="tribe",
                        government_form="council",
                    ),
                ),
                "CouncilB": Faction(
                    name="CouncilB",
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction2",
                        culture_name="Valeri",
                        polity_tier="tribe",
                        government_form="council",
                    ),
                ),
            },
        )
        initialize_relationships(world)

        update_relationships(world)
        summary = get_faction_diplomacy_summary(world, "CouncilA")

        self.assertEqual(summary["top_regime_accommodation"], "CouncilB")
        self.assertEqual(summary["top_regime_accommodation_reason"], "same_people_accord")
        self.assertEqual(summary["regime_accommodation_count"], 1)

    def test_civil_war_claimant_gets_attack_priority_on_shared_core_region(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="Claimant",
                    resources=4,
                    population=100,
                    ethnic_composition={"Valeri": 100},
                    terrain_tags=["plains"],
                    climate="temperate",
                    core_status="core",
                    integration_score=6.5,
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="Parent",
                    resources=4,
                    population=100,
                    ethnic_composition={"Valeri": 100},
                    terrain_tags=["plains"],
                    climate="temperate",
                    core_status="core",
                    integration_score=6.5,
                ),
            },
            factions={
                "Parent": Faction(
                    name="Parent",
                    treasury=8,
                    primary_ethnicity="Valeri",
                    identity=FactionIdentity(
                        internal_id="Faction1",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="monarchy",
                    ),
                ),
                "Claimant": Faction(
                    name="Claimant",
                    treasury=8,
                    primary_ethnicity="Valeri",
                    is_rebel=True,
                    origin_faction="Parent",
                    rebel_conflict_type="civil_war",
                    proto_state=False,
                    identity=FactionIdentity(
                        internal_id="Faction2",
                        culture_name="Valeri",
                        polity_tier="state",
                        government_form="republic",
                    ),
                ),
            },
        )
        initialize_relationships(world)

        score = get_attack_target_score_components("B", "Claimant", world)

        self.assertGreater(score["regime_target_bonus"], 0)
        self.assertEqual(score["regime_target_reason"], "civil_war_claim")

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

    def test_serialized_secession_event_mentions_civil_war(self):
        world = self._make_two_faction_border_world()
        event = Event(
            turn=0,
            type="unrest_secession",
            faction="FactionB",
            region="B",
            details={
                "rebel_faction": "FactionA",
                "conflict_type": "civil_war",
                "civil_war": True,
            },
        )

        serialized = _serialize_event(event, world)

        self.assertIn("civil war", serialized["title"].lower())
        self.assertIn("civil war", serialized["summary"].lower())

    def test_serialized_rebel_independence_event_mentions_rival_regime(self):
        world = self._make_two_faction_border_world()
        event = Event(
            turn=0,
            type="rebel_independence",
            faction="FactionA",
            details={
                "origin_faction": "FactionB",
                "conflict_type": "civil_war",
                "government_type": "Republic",
            },
        )

        serialized = _serialize_event(event, world)

        self.assertIn("rival regime", serialized["title"].lower())
        self.assertIn("rival republic", serialized["summary"].lower())

    def test_serialized_regime_agitation_event_mentions_sponsor(self):
        world = self._make_two_faction_border_world()
        event = Event(
            turn=0,
            type="regime_agitation",
            faction="FactionB",
            region="B",
            details={
                "sponsors": ["FactionA"],
                "lead_sponsor": "FactionA",
                "claimant_sponsors": ["FactionA"],
                "event_level": "crisis",
            },
        )

        serialized = _serialize_event(event, world)

        self.assertIn("stirred unrest", serialized["title"].lower())
        self.assertIn("backing same-people unrest", serialized["summary"].lower())

    def test_uncontacted_factions_start_with_unknown_relationship_status(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)

        self.assertEqual(get_relationship_status(world, faction_names[0], faction_names[1]), "unknown")
        self.assertEqual(world.relationships, {})

    def test_visible_border_discovers_faction_and_creates_relationship_entry(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
                "B": Region(
                    name="B",
                    neighbors=["A"],
                    owner="FactionB",
                    resources=2,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
        )

        initialize_faction_visibility(world)
        initialize_relationships(world)

        self.assertIn("FactionB", world.factions["FactionA"].known_factions)
        self.assertIn(("FactionA", "FactionB"), world.relationships)
        self.assertEqual(get_relationship_status(world, "FactionA", "FactionB"), "neutral")

    def test_diplomacy_summary_ignores_unknown_factions(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))

        summary = get_faction_diplomacy_summary(world, faction_name)

        self.assertEqual(summary["top_ally"], None)
        self.assertEqual(summary["top_rival"], None)
        self.assertEqual(summary["alliance_count"], 0)
        self.assertEqual(summary["pact_count"], 0)
        self.assertEqual(summary["rival_count"], 0)

    def test_expansion_contact_refresh_can_discover_new_faction(self):
        world = WorldState(
            regions={
                "A": Region(
                    name="A",
                    neighbors=["B"],
                    owner="FactionA",
                    resources=2,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
                "B": Region(
                    name="B",
                    neighbors=["A", "C"],
                    owner=None,
                    resources=2,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
                "C": Region(
                    name="C",
                    neighbors=["B"],
                    owner="FactionB",
                    resources=2,
                    terrain_tags=["plains"],
                    climate="temperate",
                ),
            },
            factions={
                "FactionA": Faction(name="FactionA"),
                "FactionB": Faction(name="FactionB"),
            },
        )

        initialize_faction_visibility(world)
        initialize_relationships(world)

        self.assertEqual(get_relationship_status(world, "FactionA", "FactionB"), "unknown")

        world.regions["B"].owner = "FactionA"
        refresh_faction_visibility(world, "FactionA")
        update_relationships(world)

        self.assertIn("FactionB", world.factions["FactionA"].known_factions)
        self.assertEqual(get_relationship_status(world, "FactionA", "FactionB"), "neutral")


if __name__ == "__main__":
    unittest.main()
