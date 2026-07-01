import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from src import ai_interpretation
from src.narrative_rag import (
    build_generation_queries,
    build_rag_index,
    retrieve_syncretic_style_context,
)


def _repeat_sentence(sentence: str, count: int = 90) -> str:
    return " ".join(sentence for _ in range(count))


class NarrativeRagTests(unittest.TestCase):
    def test_saved_summary_gets_boueni_narrator_origin_context(self):
        summary = {
            "chronology": {
                "early_phase_years": "Year 1 in the Grassic Annals to Year 149 in the Grassic Annals",
            },
            "factions": [
                {
                    "name": "Boueni Band",
                    "display_name": "Boueni Band",
                    "ethnicity": "Boueni",
                    "regions": 0,
                    "homeland_region": "Geueenalta Riesov",
                    "official_religion": "Mesuonrite",
                    "dynasty_name": "House Srelaem",
                    "ruler_name": "Brenoni",
                    "heir_name": "Kuvuun",
                },
                {
                    "name": "Boueni Rebels",
                    "display_name": "Riesov",
                    "ethnicity": "Boueanem",
                    "language_family": "Boueni",
                    "origin_faction": "Boueni Band",
                    "regions": 4,
                    "homeland_region": "Geueenalta Riesov",
                    "capital_region": "East Lond",
                },
            ],
            "key_event_digest": [
                {
                    "turn": 11,
                    "year_label": "Year 11 in the Grassic Annals",
                    "type": "unrest_secession",
                    "brief": "On Year 11 in the Grassic Annals, Geueenalta Riesov broke away from Boueni Band.",
                    "region_display_name": "Geueenalta Riesov",
                }
            ],
            "successor_lineages": [
                {
                    "parent": "Boueni Band",
                    "descendants": [
                        {
                            "state": "Riesov",
                            "ethnicity": "Boueanem",
                            "conflict_type": "secession",
                            "regions": 4,
                            "treasury": -1265,
                        }
                    ],
                }
            ],
        }

        enriched = ai_interpretation.enrich_summary_with_narrator_origin_context(summary)
        context = enriched["narrator_origin_context"]

        self.assertEqual(context["ancestral_faction"], "Boueni Band")
        self.assertEqual(context["first_arrival_region"], "Geueenalta Riesov")
        self.assertTrue(context["first_arrival_is_inferred"])
        self.assertEqual(context["narrator_residence_region"], "East Lond")
        self.assertEqual(context["narrator_residence_faction"], "Riesov")
        self.assertIn("Boueni-speaking Riesov", context["narrator_speech_community"])
        self.assertIn("Year 11", context["early_boueni_events"][0]["brief"])
        self.assertEqual(context["descendant_states"][0]["name"], "Riesov")

    def test_narrative_rag_enrichment_adds_causal_story_seeds(self):
        summary = {
            "chronology": {
                "early_phase_years": "Year 1 in the Grassic Annals to Year 149 in the Grassic Annals",
            },
            "factions": [
                {
                    "name": "Boueni Band",
                    "display_name": "Boueni Band",
                    "ethnicity": "Boueni",
                    "homeland_region": "Geueenalta Riesov",
                    "official_religion": "Mesuonrite",
                    "dynasty_name": "House Srelaem",
                    "ruler_name": "Brenoni",
                    "heir_name": "Kuvuun",
                    "regions": 0,
                    "treasury": -6,
                },
                {
                    "name": "Ibenal Rebels",
                    "display_name": "Ibenal",
                    "regions": 12,
                    "treasury": -176,
                    "homeland_region": "South Ibenwood",
                    "official_religion": "Thelaageilrite",
                    "government": "Council Realm",
                },
            ],
            "key_event_digest": [
                {
                    "turn": 11,
                    "year_label": "Year 11 in the Grassic Annals",
                    "type": "unrest_secession",
                    "actor": "Boueni Band",
                    "brief": "On Year 11 in the Grassic Annals, Geueenalta Riesov broke away from Boueni Band.",
                    "region_display_name": "Geueenalta Riesov",
                },
                {
                    "turn": 190,
                    "year_label": "Year 190 in the Grassic Annals",
                    "type": "attack",
                    "actor": "Ibenal",
                    "brief": "On Year 190, Ibenal captured Grasako Highlands.",
                    "region_display_name": "Grasako Highlands",
                },
                {
                    "turn": 218,
                    "year_label": "Year 218 in the Grassic Annals",
                    "type": "diplomacy_rivalry",
                    "actor": "Ibenal",
                    "counterpart": "Dinelv Highlands",
                    "brief": "On Year 218, Ibenal and Dinelv Highlands hardened into rivalry.",
                    "region_display_name": "Grasako Highlands",
                },
            ],
            "successor_lineages": [],
        }

        enriched = ai_interpretation.enrich_summary_for_narrative_rag(summary)
        seeds = enriched["story_seed_digest"]
        seed_text = " ".join(seed["interpretive_frame"] for seed in seeds)

        self.assertTrue(seeds)
        self.assertIn("Year 11", str(seeds[0]["anchoring_events"]))
        self.assertIn("forcing new people into obedience", seed_text)
        self.assertIn("overextension", seed_text)

    def test_generation_queries_route_simulation_event_types_and_places(self):
        summary = {
            "world_identity": {
                "world_name": "The Grassicibenrass Circuit",
                "era_name": "Age of Houses and Altars",
            },
            "event_type_counts": {
                "succession_crisis": 2,
                "religious_reform": 5,
                "diplomacy_tributary": 12,
            },
            "phase_summaries": [
                "The early phase was shaped by secession and claimant dynasties.",
            ],
            "turning_points": [
                "On Year 197, a naval trade war closed around a harbor crossing.",
            ],
            "structural_drivers": [
                "Diplomatic hierarchy shaped the finish through tributary settlements.",
            ],
            "centerpiece_episodes": [
                {
                    "type": "unrest_secession",
                    "brief": "A province broke away and raised a new banner.",
                    "region_display_name": "East Ibenwood",
                    "actor": "Marosh Tribe",
                }
            ],
            "key_event_digest": [
                {"region_display_name": "Gulawuudlen Thoth"},
            ],
            "narrator_origin_context": {
                "ancestral_faction": "Boueni Band",
                "ancestral_homeland": "Geueenalta Riesov",
                "ancestral_religion": "Mesuonrite",
                "early_boueni_events": [
                    {
                        "brief": "On Year 11, Geueenalta Riesov broke away from Boueni Band.",
                    }
                ],
            },
        }

        queries = build_generation_queries(summary)
        joined = " ".join(queries)

        self.assertIn("legitimacy disputed", joined)
        self.assertIn("priests reform cult", joined)
        self.assertIn("tribute envoys", joined)
        self.assertIn("East Ibenwood", joined)
        self.assertIn("Gulawuudlen Thoth", joined)
        self.assertIn("ancestral first arrival", joined)
        self.assertIn("Boueni Band", joined)

    def test_local_index_retrieval_blends_available_sources(self):
        corpus_dir = Path.cwd() / "tests" / ".tmp_narrative_rag"
        if corpus_dir.exists():
            shutil.rmtree(corpus_dir)
        corpus_dir.mkdir()
        try:
            (corpus_dir / "herodotus_histories.txt").write_text(
                _repeat_sentence(
                    "The king sent envoys with tribute across the river and recorded the customs of the people.",
                ),
                encoding="utf-8",
            )
            (corpus_dir / "dunsany_elfland_daughter.txt").write_text(
                _repeat_sentence(
                    "Beyond the fields the old names of hills and altars gathered a hush like evening.",
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                index = build_rag_index(corpus_dir)
                context = retrieve_syncretic_style_context(
                    index,
                    ["envoys tribute river customs old names altars"],
                    max_passages=4,
                )
                cached = build_rag_index(corpus_dir)

            combined = "\n".join(context)
            self.assertEqual(index.embedding_provider, "local-hash")
            self.assertEqual(cached.embedding_provider, "local-hash")
            self.assertTrue((corpus_dir / "embeddings" / "style_index.json").exists())
            self.assertIn("Herodotus, Histories", combined)
            self.assertIn("Lord Dunsany", combined)
        finally:
            shutil.rmtree(corpus_dir, ignore_errors=True)

    def test_rag_context_switches_ai_interpretation_to_boueni_remnant_prompt(self):
        with patch.object(ai_interpretation, "_generate_ai_paragraph", return_value="ok") as mocked:
            result = ai_interpretation.generate_ai_interpretation(
                {"simulation": {"turns": 450}},
                rag_context=["[Herodotus, Histories, chunk 1] tribute envoys and broken oaths"],
                enabled_override=True,
            )

        self.assertEqual(result, "ok")
        prompt = mocked.call_args.kwargs["system_prompt"]
        self.assertIn("Boueni-descended", prompt)
        self.assertIn("first-arrival traditions", prompt)
        self.assertIn("surviving Boueni-speaking", prompt)
        self.assertIn("Do not place the narrator in Elagos", prompt)
        self.assertIn("Do not state raw game measures", prompt)
        self.assertIn("story_seed_digest", prompt)
        self.assertIn("tribute envoys and broken oaths", prompt)
        self.assertNotIn("eccentric historian from a different world", prompt)


if __name__ == "__main__":
    unittest.main()
