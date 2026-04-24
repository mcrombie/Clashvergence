import unittest
from unittest.mock import patch

from src.heartland import register_ethnicity
from src.models import LanguageProfile
from src.actions import attack, expand, get_attackable_regions
from src.narrative import summarize_place_name_strata
from src.simulation_ui import _serialize_event, build_simulation_snapshots
from src.world import create_world
from src.region_naming import apply_region_name_layer, assign_region_founding_name


class RegionNamingTests(unittest.TestCase):
    def test_starting_regions_receive_homeland_display_names(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)

        owned_regions = [region for region in world.regions.values() if region.owner is not None]
        self.assertTrue(owned_regions)

        for region in owned_regions:
            owner = world.factions[region.owner]
            self.assertTrue(region.display_name)
            self.assertEqual(region.founding_name, region.display_name)
            self.assertEqual(region.original_namer_faction_id, owner.internal_id)
            self.assertEqual(region.display_name, owner.culture_name)

    def test_first_expansion_assigns_founding_name_and_conquest_keeps_it(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 10
        world.factions[defender_name].treasury = 1

        expanded = expand(attacker_name, "M", world)
        self.assertTrue(expanded)

        named_region = world.regions["M"]
        founded_name = named_region.display_name
        self.assertTrue(founded_name)
        self.assertNotEqual(founded_name, "M")
        self.assertEqual(named_region.founding_name, founded_name)
        self.assertEqual(
            named_region.original_namer_faction_id,
            world.factions[attacker_name].internal_id,
        )

        attackable_regions = sorted(get_attackable_regions(attacker_name, world))
        if not attackable_regions:
            fallback_target = next(
                neighbor_name
                for neighbor_name in world.regions["M"].neighbors
                if world.regions[neighbor_name].owner != attacker_name
            )
            world.regions[fallback_target].owner = defender_name
            world.regions[fallback_target].integrated_owner = defender_name
            world.regions[fallback_target].display_name = world.factions[defender_name].culture_name
            world.regions[fallback_target].founding_name = world.factions[defender_name].culture_name
            world.regions[fallback_target].original_namer_faction_id = world.factions[defender_name].internal_id
            attackable_regions = sorted(get_attackable_regions(attacker_name, world))

        target_region_name = attackable_regions[0]
        original_owner = world.regions[target_region_name].owner

        with patch("src.actions.random.random", return_value=0.0):
            succeeded = attack(attacker_name, target_region_name, world)

        self.assertTrue(succeeded)
        conquered_region = world.regions[target_region_name]
        self.assertEqual(conquered_region.owner, attacker_name)
        self.assertTrue(conquered_region.display_name)
        self.assertEqual(conquered_region.founding_name, world.factions[original_owner].culture_name)
        self.assertEqual(
            conquered_region.original_namer_faction_id,
            world.factions[original_owner].internal_id,
        )
        self.assertGreaterEqual(len(conquered_region.name_metadata.get("name_layers", [])), 1)
        self.assertEqual(conquered_region.name_metadata.get("current_name_reason"), "conquest")

    def test_snapshots_show_code_name_until_region_is_first_named(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        world.factions[faction_name].treasury = 10

        self.assertTrue(expand(faction_name, "M", world))
        world.turn = 1

        snapshots = build_simulation_snapshots(world)
        self.assertEqual(snapshots[0]["regions"]["M"]["display_name"], "M")
        self.assertNotEqual(snapshots[1]["regions"]["M"]["display_name"], "M")

    def test_homeland_naming_stays_direct_even_with_terrain(self):
        world = create_world(map_name="multi_ring_symmetry", num_factions=4)

        for region in world.regions.values():
            if region.owner is None:
                continue
            self.assertEqual(region.display_name, world.factions[region.owner].culture_name)

    def test_terrain_aware_naming_uses_region_cues(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))

        region = world.regions["M"]
        region.display_name = ""
        region.founding_name = ""
        region.original_namer_faction_id = None
        region.name_metadata = {}
        region.terrain_tags = ["riverland", "forest"]

        assigned_name = assign_region_founding_name(world, "M", faction_name, is_homeland=False)
        expected_terms = {"Banks", "Ford", "Grove", "Hollow", "Wash", "Wood"}
        self.assertTrue(
            any(term in assigned_name for term in expected_terms),
            msg=f"Expected a terrain-aware name, got {assigned_name}",
        )
        self.assertEqual(region.name_metadata["terrain_label"], "Riverland Forest")

    def test_region_naming_prefers_primary_ethnicity_language_profile(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]

        faction.primary_ethnicity = "Sarvi"
        register_ethnicity(
            world,
            "Sarvi",
            language_family="Valeri",
            language_profile=LanguageProfile(
                family_name="Sarvi",
                onsets=["sar"],
                middles=["a"],
                suffixes=["vek"],
                seed_fragments=["sarv"],
            ),
        )

        region = world.regions["M"]
        region.display_name = ""
        region.founding_name = ""
        region.original_namer_faction_id = None
        region.name_metadata = {}
        region.terrain_tags = []

        with patch("src.region_naming._stable_random") as stable_random:
            class FixedRandom:
                def choice(self, values):
                    return values[0]

            stable_random.return_value = FixedRandom()
            assigned_name = assign_region_founding_name(world, "M", faction_name, is_homeland=False)

        self.assertEqual(assigned_name, "Sarvford")
        self.assertEqual(region.name_metadata["pattern"], "ethnicity_fragment_settlement")
        self.assertEqual(region.name_metadata["named_from"], "Sarvi")
        self.assertEqual(region.name_metadata["named_from_ethnicity"], "Sarvi")

    def test_region_naming_can_use_semantic_roots_from_language_profile(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_name = next(iter(world.factions))
        faction = world.factions[faction_name]

        faction.primary_ethnicity = "Sarvi"
        register_ethnicity(
            world,
            "Sarvi",
            language_family="Valeri",
            language_profile=LanguageProfile(
                family_name="Sarvi",
                onsets=[],
                middles=["a"],
                suffixes=["vek"],
                seed_fragments=[],
                lexical_roots={"settlement": ["zorvek"]},
            ),
        )

        region = world.regions["M"]
        region.display_name = ""
        region.founding_name = ""
        region.original_namer_faction_id = None
        region.name_metadata = {}
        region.terrain_tags = []

        with patch("src.region_naming._stable_random") as stable_random:
            class FixedRandom:
                def choice(self, values):
                    return values[0]

            stable_random.return_value = FixedRandom()
            assigned_name = assign_region_founding_name(world, "M", faction_name, is_homeland=False)

        self.assertEqual(assigned_name, "Sarvzorvek")
        self.assertEqual(region.name_metadata["pattern"], "semantic_compound")

    def test_conquest_layering_and_restoration_preserve_strata(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        original_owner = faction_names[0]
        conqueror = faction_names[1]
        region = world.regions["M"]

        assign_region_founding_name(world, "M", original_owner, is_homeland=False)
        founding_name = region.founding_name

        layered_name = apply_region_name_layer(world, "M", conqueror, reason="conquest")
        self.assertTrue(layered_name["name"])
        self.assertTrue(layered_name["changed"])
        self.assertEqual(layered_name["layer_type"], "conquest")
        self.assertEqual(region.founding_name, founding_name)
        self.assertEqual(region.name_metadata["current_name_reason"], "conquest")
        self.assertEqual(region.name_metadata["name_layers"][0]["type"], "founding")
        self.assertEqual(region.name_metadata["name_layers"][-1]["type"], "conquest")

        restored_name = apply_region_name_layer(world, "M", original_owner, reason="restoration")
        self.assertEqual(restored_name["name"], founding_name)
        self.assertTrue(restored_name["changed"])
        self.assertEqual(restored_name["layer_type"], "restoration")
        self.assertEqual(region.display_name, founding_name)
        self.assertEqual(region.name_metadata["current_name_reason"], "restoration")
        self.assertEqual(region.name_metadata["name_layers"][-1]["type"], "restoration")

    def test_snapshots_and_chronicle_expose_name_history(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        original_owner = faction_names[0]
        conqueror = faction_names[1]
        region = world.regions["M"]

        assign_region_founding_name(world, "M", original_owner, is_homeland=False)
        apply_region_name_layer(world, "M", conqueror, reason="conquest")
        apply_region_name_layer(world, "M", original_owner, reason="restoration")
        world.region_history = [{
            "M": {
                "owner": region.owner,
                "resources": region.resources,
                "population": region.population,
                "display_name": region.display_name,
                "founding_name": region.founding_name,
                "original_namer_faction_id": region.original_namer_faction_id,
                "name_metadata": dict(region.name_metadata),
                "ethnic_composition": dict(region.ethnic_composition),
                "dominant_ethnicity": None,
                "ethnic_claimants": [],
                "owner_primary_ethnicity": None,
                "owner_has_ethnic_claim": False,
                "ruling_ethnic_affinity": 0.0,
                "external_regime_agitators": [],
                "external_regime_agitation": 0.0,
                "climate": region.climate,
                "resource_fixed_endowments": {},
                "resource_wild_endowments": {},
                "resource_suitability": {},
                "resource_established": {},
                "resource_output": {},
                "resource_retained_output": {},
                "resource_routed_output": {},
                "resource_effective_output": {},
                "resource_damage": {},
                "resource_monetized_value": 0.0,
                "resource_isolation_factor": 0.0,
                "resource_route_depth": None,
                "resource_route_cost": 0.0,
                "resource_route_anchor": None,
                "resource_route_bottleneck": 1.0,
                "resource_route_mode": "land",
                "trade_route_role": "local",
                "trade_route_parent": None,
                "trade_route_children": 0,
                "trade_served_regions": 0,
                "trade_throughput": 0.0,
                "trade_transit_flow": 0.0,
                "trade_import_value": 0.0,
                "trade_transit_value": 0.0,
                "trade_hub_value": 0.0,
                "trade_value_bonus": 0.0,
                "trade_import_reliance": 0.0,
                "trade_disruption_risk": 0.0,
                "trade_warfare_pressure": 0.0,
                "trade_warfare_turns": 0,
                "trade_blockade_strength": 0.0,
                "trade_blockade_turns": 0,
                "trade_value_denied": 0.0,
                "resource_profile": {},
                "resource_output_summary": "",
                "resource_retained_output_summary": "",
                "resource_routed_output_summary": "",
                "taxable_value": 0.0,
                "infrastructure_level": 0.0,
                "granary_level": 0.0,
                "storehouse_level": 0.0,
                "market_level": 0.0,
                "irrigation_level": 0.0,
                "pasture_level": 0.0,
                "logging_camp_level": 0.0,
                "road_level": 0.0,
                "copper_mine_level": 0.0,
                "stone_quarry_level": 0.0,
                "agriculture_level": 0.0,
                "pastoral_level": 0.0,
                "extractive_level": 0.0,
                "food_stored": 0.0,
                "food_storage_capacity": 0.0,
                "food_produced": 0.0,
                "food_consumption": 0.0,
                "food_balance": 0.0,
                "food_deficit": 0.0,
                "food_spoilage": 0.0,
                "food_overflow": 0.0,
                "migration_inflow": 0,
                "migration_outflow": 0,
                "refugee_inflow": 0,
                "refugee_outflow": 0,
                "frontier_settler_inflow": 0,
                "migration_pressure": 0.0,
                "migration_attraction": 0.0,
                "administrative_burden": 0.0,
                "administrative_support": 0.0,
                "administrative_distance": 0.0,
                "administrative_autonomy": 0.0,
                "administrative_tax_capture": 1.0,
                "homeland_faction_id": region.homeland_faction_id,
                "integrated_owner": region.integrated_owner,
                "integration_score": region.integration_score,
                "core_status": region.core_status,
                "settlement_level": region.settlement_level,
                "unrest": region.unrest,
                "unrest_event_level": region.unrest_event_level,
                "unrest_event_turns_remaining": region.unrest_event_turns_remaining,
            }
        }]

        snapshots = build_simulation_snapshots(world)
        self.assertIn("Founded as", snapshots[0]["regions"]["M"]["name_history_summary"][0])

        strata_lines = summarize_place_name_strata(world)
        self.assertTrue(any(line.startswith("M: founded as") for line in strata_lines))

    def test_attack_emits_region_rename_event_with_timeline_text(self):
        world = create_world(map_name="thirteen_region_ring", num_factions=4)
        faction_names = list(world.factions)
        attacker_name = faction_names[0]
        defender_name = faction_names[1]

        world.factions[attacker_name].treasury = 10
        world.factions[defender_name].treasury = 1

        attackable_regions = sorted(get_attackable_regions(attacker_name, world))
        if not attackable_regions:
            attacker_region = next(
                region for region in world.regions.values() if region.owner == attacker_name
            )
            fallback_target = next(
                neighbor_name
                for neighbor_name in attacker_region.neighbors
                if world.regions[neighbor_name].owner != attacker_name
            )
            world.regions[fallback_target].owner = defender_name
            world.regions[fallback_target].integrated_owner = defender_name
            assign_region_founding_name(world, fallback_target, defender_name, is_homeland=False)
            attackable_regions = sorted(get_attackable_regions(attacker_name, world))

        target_region_name = attackable_regions[0]
        old_name = world.regions[target_region_name].display_name

        with patch("src.actions.random.random", return_value=0.0), patch("src.region_naming._stable_random") as stable_random:
            class FixedRandom:
                def choice(self, values):
                    return values[0]

            stable_random.return_value = FixedRandom()
            succeeded = attack(attacker_name, target_region_name, world)

        self.assertTrue(succeeded)
        rename_events = [event for event in world.events if event.type == "region_rename"]
        self.assertEqual(len(rename_events), 1)
        rename_event = rename_events[0]
        self.assertEqual(rename_event.faction, attacker_name)
        self.assertEqual(rename_event.region, target_region_name)
        self.assertEqual(rename_event.get("rename_type"), "conquest")
        self.assertEqual(rename_event.get("old_name"), old_name)
        self.assertNotEqual(rename_event.get("new_name"), old_name)

        timeline_event = _serialize_event(rename_event, world)
        self.assertIn("renamed", timeline_event["title"].lower())
        self.assertIn(rename_event.get("new_name"), timeline_event["summary"])


if __name__ == "__main__":
    unittest.main()
