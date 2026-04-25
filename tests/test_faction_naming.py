import os
import sys
import types
import unittest
from unittest.mock import patch

from src.faction_naming import REAL_NAME_BLOCKLIST, generate_faction_identities
from src.models import FactionIdentity
from src.simulation import run_simulation
from src.world import create_world


class _FakeResponse:
    def __init__(self, output_text):
        self.output_text = output_text


class _FakeResponsesAPI:
    def __init__(self, output_text):
        if isinstance(output_text, list):
            self._output_texts = list(output_text)
        else:
            self._output_texts = [output_text]

    def create(self, **kwargs):
        if len(self._output_texts) > 1:
            return _FakeResponse(self._output_texts.pop(0))
        return _FakeResponse(self._output_texts[0])


class _FakeOpenAIClient:
    def __init__(self, output_text):
        self.responses = _FakeResponsesAPI(output_text)


class FactionNamingTests(unittest.TestCase):
    def test_generation_is_deterministic_for_same_seed(self):
        first = [identity.display_name for identity in generate_faction_identities(4, naming_seed="multi_ring_symmetry")]
        second = [identity.display_name for identity in generate_faction_identities(4, naming_seed="multi_ring_symmetry")]
        self.assertEqual(first, second)

    def test_generation_varies_by_seed_and_remains_unique(self):
        first = generate_faction_identities(6, naming_seed="multi_ring_symmetry")
        second = generate_faction_identities(6, naming_seed="thirty_seven_region_ring")

        first_names = [identity.display_name for identity in first]
        second_names = [identity.display_name for identity in second]

        self.assertEqual(len(first_names), len(set(first_names)))
        self.assertEqual(len(second_names), len(set(second_names)))
        self.assertNotEqual(first_names, second_names)

    def test_world_creation_is_deterministic_for_same_explicit_seed(self):
        first = create_world(map_name="thirteen_region_ring", num_factions=4, seed="repeatable-seed")
        second = create_world(map_name="thirteen_region_ring", num_factions=4, seed="repeatable-seed")

        self.assertEqual(list(first.factions), list(second.factions))
        first_region_names = {name: region.display_name for name, region in first.regions.items()}
        second_region_names = {name: region.display_name for name, region in second.regions.items()}
        self.assertEqual(first_region_names, second_region_names)

    def test_world_creation_varies_for_different_explicit_seeds(self):
        first = create_world(map_name="thirteen_region_ring", num_factions=4, seed="seed-a")
        second = create_world(map_name="thirteen_region_ring", num_factions=4, seed="seed-b")

        self.assertNotEqual(list(first.factions), list(second.factions))

    def test_generated_schema_contains_future_facing_identity_fields(self):
        identities = generate_faction_identities(4, naming_seed="thirteen_region_ring")

        for index, identity in enumerate(identities, start=1):
            self.assertEqual(identity.internal_id, f"Faction{index}")
            self.assertTrue(identity.culture_name)
            self.assertTrue(identity.language_profile.family_name)
            self.assertEqual(identity.polity_tier, "tribe")
            self.assertEqual(identity.government_form, "council")
            self.assertEqual(identity.government_type, "Tribe")
            self.assertEqual(identity.display_name, f"{identity.culture_name} Tribe")
            self.assertTrue(identity.source_traditions)
            self.assertIn(identity.generation_method, {"curated_source_fusion", "ai_fused_sources"})
            self.assertTrue(identity.candidate_pool)
            self.assertIn("settlement", identity.language_profile.lexical_roots)
            self.assertTrue(identity.language_profile.lexical_roots["settlement"])
            self.assertIn("dynasty", identity.language_profile.lexical_roots)

    def test_world_specific_proto_language_families_are_shared_across_some_factions(self):
        identities = generate_faction_identities(6, naming_seed="proto_family_case")

        family_names = [identity.language_profile.family_name for identity in identities]
        unique_families = set(family_names)

        self.assertGreater(len(unique_families), 1)
        self.assertLess(len(unique_families), len(identities))
        for identity in identities:
            self.assertIn(identity.language_profile.family_name, family_names)
            self.assertTrue(identity.language_profile.onsets)
            self.assertTrue(identity.language_profile.suffixes)
            self.assertTrue(identity.language_profile.lexical_roots)

    def test_world_specific_proto_language_families_vary_by_seed(self):
        first = generate_faction_identities(6, naming_seed="proto_family_seed_a")
        second = generate_faction_identities(6, naming_seed="proto_family_seed_b")

        first_families = [identity.language_profile.family_name for identity in first]
        second_families = [identity.language_profile.family_name for identity in second]

        self.assertNotEqual(first_families, second_families)

    def test_legacy_government_labels_infer_structure(self):
        identity = FactionIdentity(
            internal_id="FactionX",
            culture_name="Valeri",
            government_type="Kingdom",
        )

        self.assertEqual(identity.polity_tier, "state")
        self.assertEqual(identity.government_form, "monarchy")
        self.assertEqual(identity.display_name, "Valeri Kingdom")

    def test_legacy_generic_state_label_resolves_to_specific_official_name(self):
        identity = FactionIdentity(
            internal_id="FactionX",
            culture_name="Valeri",
            government_type="State",
            display_name="Valeri State",
        )

        self.assertEqual(identity.polity_tier, "state")
        self.assertEqual(identity.government_form, "council")
        self.assertEqual(identity.government_type, "Council Realm")
        self.assertEqual(identity.display_name, "Valeri Council Realm")
        self.assertNotIn(" State", identity.display_name)

    def test_generated_culture_names_do_not_copy_blocked_historical_names(self):
        identities = generate_faction_identities(12, naming_seed="historical_guardrails")
        normalized_blocklist = {name.lower() for name in REAL_NAME_BLOCKLIST}

        for identity in identities:
            self.assertNotIn(identity.culture_name.lower(), normalized_blocklist)

    def test_world_translates_internal_map_owners_to_generated_names(self):
        world = create_world(map_name="thirty_seven_region_ring", num_factions=4)

        faction_names = set(world.factions)
        self.assertTrue(faction_names)

        for region in world.regions.values():
            if region.owner is None:
                continue
            self.assertIn(region.owner, faction_names)
            self.assertFalse(region.owner.startswith("Faction"))

    def test_simulation_events_keep_generated_faction_names(self):
        world = create_world(map_name="multi_ring_symmetry", num_factions=4)
        world = run_simulation(world, num_turns=4, verbose=False)

        self.assertTrue(world.events)
        for event in world.events:
            self.assertIn(event.faction, world.factions)
            self.assertFalse(event.faction.startswith("Faction"))

    def test_ai_candidate_is_used_when_valid(self):
        fake_openai_module = types.SimpleNamespace(
            OpenAI=lambda api_key=None: _FakeOpenAIClient("Altherand")
        )

        with patch("src.faction_naming.AI_FACTION_NAMING_ENABLED", True), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), \
                patch.dict(sys.modules, {"openai": fake_openai_module}):
            identity = generate_faction_identities(1, naming_seed="ai_case")[0]

        self.assertEqual(identity.culture_name, "Altherand")
        self.assertEqual(identity.display_name, "Altherand Tribe")
        self.assertTrue(identity.ai_generated)
        self.assertEqual(identity.generation_method, "ai_fused_sources")

    def test_ai_candidate_falls_back_when_invalid_or_historical(self):
        fake_openai_module = types.SimpleNamespace(
            OpenAI=lambda api_key=None: _FakeOpenAIClient("Qin")
        )

        with patch("src.faction_naming.AI_FACTION_NAMING_ENABLED", True), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), \
                patch.dict(sys.modules, {"openai": fake_openai_module}):
            identity = generate_faction_identities(1, naming_seed="ai_fallback_case")[0]

        self.assertFalse(identity.ai_generated)
        self.assertNotEqual(identity.culture_name, "Qin")
        self.assertEqual(identity.generation_method, "curated_source_fusion")

    def test_ai_candidate_retries_after_awkward_output(self):
        fake_openai_module = types.SimpleNamespace(
            OpenAI=lambda api_key=None: _FakeOpenAIClient(["Qiaxakaar", "Veloranthi"])
        )

        with patch("src.faction_naming.AI_FACTION_NAMING_ENABLED", True), \
                patch("src.faction_naming.AI_FACTION_NAMING_MAX_ATTEMPTS", 2), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), \
                patch.dict(sys.modules, {"openai": fake_openai_module}):
            identity = generate_faction_identities(1, naming_seed="ai_retry_case")[0]

        self.assertEqual(identity.culture_name, "Veloranthi")
        self.assertTrue(identity.ai_generated)
        self.assertEqual(identity.generation_method, "ai_fused_sources")

    def test_ai_candidate_falls_back_when_quality_gate_rejects_all_attempts(self):
        fake_openai_module = types.SimpleNamespace(
            OpenAI=lambda api_key=None: _FakeOpenAIClient(["Qiaxakaar", "Zhaoxnia", "Xazjion"])
        )

        with patch("src.faction_naming.AI_FACTION_NAMING_ENABLED", True), \
                patch("src.faction_naming.AI_FACTION_NAMING_MAX_ATTEMPTS", 3), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False), \
                patch.dict(sys.modules, {"openai": fake_openai_module}):
            identity = generate_faction_identities(1, naming_seed="ai_quality_fallback")[0]

        self.assertFalse(identity.ai_generated)
        self.assertEqual(identity.generation_method, "curated_source_fusion")


if __name__ == "__main__":
    unittest.main()
