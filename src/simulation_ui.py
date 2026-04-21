from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from src.event_analysis import (
    build_initial_opening_state,
    get_final_standings,
)
from src.climate import format_climate_label
from src.map_visualization import (
    build_map_layout,
    build_multi_ring_coastline_polygon,
    build_multi_ring_region_geometry,
    get_faction_color,
    get_map_edges,
    is_multi_ring_map,
    natural_sort_key,
)
from src.maps import MAPS
from src.metrics import get_turn_metrics
from src.resource_economy import get_region_taxable_value
from src.heartland import (
    faction_has_ethnic_claim,
    get_region_external_regime_agitation_modifier,
    get_region_external_regime_agitators,
    get_faction_ethnic_claims,
    get_region_dominant_ethnicity,
    get_region_ethnic_claimants,
    get_region_owner_primary_ethnicity,
    get_region_ruling_ethnic_affinity,
    get_region_population_pressure,
    get_region_productive_capacity,
    get_region_surplus,
    get_region_surplus_label,
)
from src.narrative import (
    get_phase_ranges,
    summarize_final_standings,
    summarize_phases,
    summarize_strategic_interpretation,
    summarize_victor_history,
)
from src.resources import format_resource_map
from src.region_naming import format_region_reference, get_region_display_name
from src.terrain import format_terrain_label


SIMULATION_VIEWER_OUTPUT = Path("reports/simulation_view.html")


def _get_faction_display_name(world, faction_name: str | None) -> str:
    if faction_name is None:
        return "another faction"
    faction = world.factions.get(faction_name)
    if faction is None:
        return faction_name
    return faction.display_name


def _serialize_resource_map(resource_map):
    return {
        resource_name: round(float(amount), 3)
        for resource_name, amount in (resource_map or {}).items()
    }


def _build_region_resource_payload(region):
    fixed_text = format_resource_map(region.resource_fixed_endowments, limit=2)
    wild_text = format_resource_map(region.resource_wild_endowments, limit=2)
    established_text = format_resource_map(region.resource_established, limit=2)
    profile_parts = []
    if fixed_text != "None":
        profile_parts.append(f"Fixed: {fixed_text}")
    if wild_text != "None":
        profile_parts.append(f"Wild: {wild_text}")
    if established_text != "None":
        profile_parts.append(f"Established: {established_text}")
    return {
        "resource_fixed_endowments": _serialize_resource_map(region.resource_fixed_endowments),
        "resource_wild_endowments": _serialize_resource_map(region.resource_wild_endowments),
        "resource_suitability": _serialize_resource_map(region.resource_suitability),
        "resource_established": _serialize_resource_map(region.resource_established),
        "resource_output": _serialize_resource_map(region.resource_output),
        "resource_effective_output": _serialize_resource_map(region.resource_effective_output),
        "resource_damage": _serialize_resource_map(region.resource_damage),
        "resource_isolation_factor": round(float(region.resource_isolation_factor or 0.0), 3),
        "resource_route_depth": region.resource_route_depth,
        "resource_route_cost": round(float(region.resource_route_cost or 0.0), 3),
        "resource_route_anchor": region.resource_route_anchor,
        "resource_route_bottleneck": round(float(region.resource_route_bottleneck or 0.0), 3),
        "resource_profile": " | ".join(profile_parts) if profile_parts else "None",
        "resource_output_summary": format_resource_map(region.resource_effective_output or region.resource_output, limit=3),
        "taxable_value": round(get_region_taxable_value(region), 3),
        "infrastructure_level": round(region.infrastructure_level, 2),
        "agriculture_level": round(region.agriculture_level, 2),
        "pastoral_level": round(region.pastoral_level, 2),
        "extractive_level": round(region.extractive_level, 2),
    }


def _serialize_event(event, world):
    event_data = event.to_dict()
    event_data["turn_display"] = event.turn + 1
    event_data["faction_display_name"] = _get_faction_display_name(world, event.faction)
    event_data["counterpart_display_name"] = _get_faction_display_name(
        world,
        event.get("counterpart"),
    )
    event_data["origin_faction_display_name"] = _get_faction_display_name(
        world,
        event.get("origin_faction"),
    )
    event_data["rebel_faction_display_name"] = _get_faction_display_name(
        world,
        event.get("rebel_faction"),
    )
    if event.region is not None and event.region in world.regions:
        region = world.regions[event.region]
        event_data["region_display_name"] = get_region_display_name(region)
        event_data["region_reference"] = format_region_reference(region, include_code=True)
        event_data["terrain_label"] = format_terrain_label(region.terrain_tags)
        event_data["terrain_tags"] = list(region.terrain_tags)
        event_data["climate"] = region.climate
        event_data["climate_label"] = format_climate_label(region.climate)
    else:
        event_data["region_display_name"] = event.region
        event_data["region_reference"] = event.region
        event_data["terrain_label"] = None
        event_data["terrain_tags"] = []
        event_data["climate"] = None
        event_data["climate_label"] = None
    event_data["title"] = _get_event_title(event, world)
    event_data["summary"] = _get_event_summary(event, world)
    return event_data


def _get_event_title(event, world):
    region_reference = event.region
    faction_name = _get_faction_display_name(world, event.faction)
    counterpart_name = _get_faction_display_name(world, event.get("counterpart"))
    origin_name = _get_faction_display_name(world, event.get("origin_faction"))
    rebel_name = _get_faction_display_name(world, event.get("rebel_faction"))
    if event.region is not None and event.region in world.regions:
        region_reference = format_region_reference(world.regions[event.region], include_code=True)
    if event.type == "expand":
        return f"{faction_name} expanded into {region_reference}"
    if event.type == "attack":
        defender = _get_faction_display_name(world, event.get("defender")) if event.get("defender") else "Unknown"
        if event.get("regime_target_attack"):
            if event.get("success", False):
                return f"{faction_name} seized {region_reference} from {defender} in a regime claim offensive"
            return f"{faction_name}'s regime claim offensive against {region_reference} failed"
        if event.get("ethnic_claim_attack"):
            claim_ethnicity = event.get("claim_ethnicity") or "local"
            if event.get("success", False):
                return f"{faction_name} seized {region_reference} from {defender} in a {claim_ethnicity} claim offensive"
            return f"{faction_name}'s {claim_ethnicity} claim offensive against {region_reference} failed"
        if event.get("success", False):
            return f"{faction_name} captured {region_reference} from {defender}"
        return f"{faction_name} failed to take {region_reference} from {defender}"
    if event.type == "invest":
        return f"{faction_name} invested in {region_reference}"
    if event.type == "unrest_disturbance":
        return f"Unrest disturbed {region_reference} under {faction_name}"
    if event.type == "unrest_crisis":
        return f"Unrest crisis hit {region_reference} under {faction_name}"
    if event.type == "regime_agitation":
        sponsor_count = len(event.get("sponsors", []) or [])
        mode = event.get("lead_sponsor_mode", "standard")
        mode_prefix = {
            "heavy": "Heavy-handed ",
            "low": "Low-grade ",
        }.get(mode, "")
        if sponsor_count > 1:
            return f"{mode_prefix}rival regimes stirred unrest in {region_reference} against {faction_name}"
        lead_sponsor = _get_faction_display_name(world, event.get("lead_sponsor"))
        return f"{mode_prefix}{lead_sponsor} stirred unrest in {region_reference} against {faction_name}"
    if event.type == "unrest_secession":
        joined_region_count = int(event.get("joined_region_count", 0) or 0)
        if event.get("restoration") and event.get("restored_faction"):
            if joined_region_count > 0:
                return f"{region_reference} and {joined_region_count} neighboring region(s) rose against {faction_name} and restored {rebel_name}"
            return f"{region_reference} rose against {faction_name} and restored {rebel_name}"
        if event.get("conflict_type") == "civil_war":
            if event.get("joined_existing_rebellion") and event.get("rebel_faction"):
                if joined_region_count > 0:
                    return f"{region_reference} joined {rebel_name}'s civil war with {joined_region_count} neighboring region(s)"
                return f"{region_reference} joined {rebel_name}'s civil-war uprising"
            if event.get("rebel_faction"):
                if joined_region_count > 0:
                    return f"{region_reference} and {joined_region_count} neighboring region(s) rose against {faction_name} in civil war as {rebel_name}"
                return f"{region_reference} rose against {faction_name} in civil war as {rebel_name}"
            return f"{region_reference} rose against {faction_name} in civil war"
        if event.get("joined_existing_rebellion") and event.get("rebel_faction"):
            if joined_region_count > 0:
                return f"{region_reference} joined {rebel_name}'s regional uprising with {joined_region_count} neighboring region(s)"
            return f"{region_reference} joined {rebel_name}'s uprising"
        if event.get("rebel_faction"):
            if joined_region_count > 0:
                return f"{region_reference} and {joined_region_count} neighboring region(s) broke away from {faction_name} as {rebel_name}"
            return f"{region_reference} broke away from {faction_name} as {rebel_name}"
        return f"{region_reference} broke away from {faction_name}"
    if event.type == "rebel_independence":
        if event.get("conflict_type") == "civil_war":
            if event.get("origin_faction"):
                return f"{faction_name} consolidated as a rival regime against {origin_name}"
            return f"{faction_name} consolidated as a rival regime"
        if event.get("origin_faction"):
            return f"{faction_name} declared full independence from {origin_name}"
        return f"{faction_name} consolidated into an independent successor state"
    if event.type == "polity_advance":
        return (
            f"{faction_name} advanced from {event.get('old_government_type', event.get('old_polity_tier', 'tribe'))} "
            f"to {event.get('new_government_type', event.get('new_polity_tier', 'chiefdom'))}"
        )
    if event.type == "diplomacy_rivalry":
        return f"{faction_name} and {counterpart_name} became rivals"
    if event.type == "diplomacy_pact":
        return f"{faction_name} and {counterpart_name} signed a non-aggression pact"
    if event.type == "diplomacy_alliance":
        return f"{faction_name} and {counterpart_name} formed an alliance"
    if event.type == "diplomacy_truce":
        return f"{faction_name} and {counterpart_name} entered a truce"
    if event.type == "diplomacy_truce_end":
        return f"{faction_name} and {counterpart_name} saw their truce expire"
    if event.type == "diplomacy_break":
        return f"{faction_name} and {counterpart_name} broke their accord"
    return f"{faction_name} acted"


def _get_event_summary(event, world):
    terrain_text = ""
    if event.region is not None and event.region in world.regions:
        terrain_text = f" Terrain: {format_terrain_label(world.regions[event.region].terrain_tags)}."

    if event.type == "expand":
        return (
            f"Claimed a region worth {event.get('taxable_value', event.get('resources', 0)):.2f} taxable value "
            f"with {event.get('neighbors', 0)} links.{terrain_text}"
        )
    if event.type == "attack":
        chance = event.get("success_chance", 0)
        if event.get("regime_target_attack"):
            reason = event.get("regime_target_reason")
            motive = "civil-war legitimacy" if reason == "civil_war_claim" else "same-people regime rivalry"
            if event.get("success", False):
                return (
                    f"A {motive} attack succeeded at {chance:.0%} displayed odds."
                    f"{terrain_text}"
                )
            return (
                f"A {motive} attack failed at {chance:.0%} displayed odds."
                f"{terrain_text}"
            )
        if event.get("ethnic_claim_attack"):
            claim_ethnicity = event.get("claim_ethnicity") or "local"
            if event.get("success", False):
                return (
                    f"A claim-driven attack by {claim_ethnicity} forces succeeded at {chance:.0%} displayed odds."
                    f"{terrain_text}"
                )
            return (
                f"A claim-driven attack by {claim_ethnicity} forces failed at {chance:.0%} displayed odds."
                f"{terrain_text}"
            )
        if event.get("success", False):
            return f"Successful attack at {chance:.0%} displayed odds.{terrain_text}"
        return f"Attack failed at {chance:.0%} displayed odds.{terrain_text}"
    if event.type == "invest":
        project_type = event.get("project_type", "development").replace("_", " ")
        resource_focus = event.get("resource_focus")
        focus_text = f" in {resource_focus}" if resource_focus else ""
        return (
            f"Completed a {project_type}{focus_text} project, bringing the region to "
            f"{event.get('new_taxable_value', event.get('new_resources', 0)):.2f} taxable value."
            f"{terrain_text}"
        )
    if event.type == "unrest_disturbance":
        return (
            f"Moderate unrest disrupted local order and forced a treasury hit of "
            f"{abs(event.get('treasury_change', 0))}.{terrain_text}"
        )
    if event.type == "unrest_crisis":
        return (
            f"Critical unrest triggered a deeper disruption and treasury hit of "
            f"{abs(event.get('treasury_change', 0))}.{terrain_text}"
        )
    if event.type == "regime_agitation":
        sponsors = [
            _get_faction_display_name(world, sponsor)
            for sponsor in (event.get("sponsors", []) or [])
        ]
        sponsor_text = ", ".join(sponsors) if sponsors else "a rival regime"
        total_treasury_cost = sum(
            int((event.get("sponsor_costs", {}) or {}).get(sponsor, {}).get("treasury_cost", 0))
            for sponsor in (event.get("sponsors", []) or [])
        )
        mode = event.get("lead_sponsor_mode", "standard")
        mode_text = {
            "heavy": "through a heavy-handed campaign",
            "low": "through low-grade meddling",
        }.get(mode, "through sustained meddling")
        if event.get("claimant_sponsors"):
            return (
                f"{sponsor_text} helped push the region toward {event.get('event_level', 'disturbance')} {mode_text} by backing same-people unrest across the border"
                f"{f', paying {total_treasury_cost} treasury in the process' if total_treasury_cost > 0 else ''}."
                f"{terrain_text}"
            )
        return (
            f"{sponsor_text} aggravated same-people political tension across the border {mode_text}, helping local unrest rise"
            f"{f' while spending {total_treasury_cost} treasury to sustain the pressure' if total_treasury_cost > 0 else ''}."
            f"{terrain_text}"
        )
    if event.type == "unrest_secession":
        rebel_faction = _get_faction_display_name(world, event.get("rebel_faction"))
        ruler_faction = _get_faction_display_name(world, event.faction)
        joined_region_count = int(event.get("joined_region_count", 0) or 0)
        if event.get("restoration") and rebel_faction:
            joined_clause = (
                f" The revolt also pulled in {joined_region_count} neighboring region(s)."
                if joined_region_count > 0
                else ""
            )
            return (
                f"Surviving {event.get('revived_ethnicity') or 'local'} communities turned sustained crisis into a restoration revolt for {rebel_faction}."
                + joined_clause
                + terrain_text
            )
        if event.get("conflict_type") == "civil_war":
            joined_clause = (
                f" The fighting also pulled in {joined_region_count} neighboring region(s)."
                if joined_region_count > 0
                else ""
            )
            if event.get("joined_existing_rebellion") and rebel_faction:
                return (
                    f"Sustained crisis pushed the region into {rebel_faction}'s existing civil-war movement instead of a separate breakaway."
                    + joined_clause
                    + terrain_text
                )
            return (
                (
                    f"Sustained crisis escalated into a same-people civil war against {ruler_faction}, rallying behind {rebel_faction}."
                    if rebel_faction
                    else f"Sustained crisis escalated into civil war against {ruler_faction}."
                )
                + joined_clause
                + terrain_text
            )
        if event.get("joined_existing_rebellion") and rebel_faction:
            joined_clause = (
                f" Nearby unrest drew in {joined_region_count} neighboring region(s) as part of the same movement."
                if joined_region_count > 0
                else ""
            )
            return (
                f"Sustained crisis fed directly into {rebel_faction}'s existing rebellion instead of creating a separate breakaway."
                + joined_clause
                + terrain_text
            )
        return (
            (
                f"Sustained crisis raised {rebel_faction} out of {ruler_faction}'s collapsing rule."
                if rebel_faction
                else f"Sustained crisis forced the region out of {ruler_faction}'s control."
            )
            + (
                f" The uprising also spread into {joined_region_count} neighboring region(s)."
                if joined_region_count > 0
                else ""
            )
            + terrain_text
        )
    if event.type == "rebel_independence":
        government_type = event.get("government_type", "State")
        if event.get("conflict_type") == "civil_war":
            return (
                f"After surviving its fragile uprising, the claimant hardened into a rival {government_type.lower()} backed by the same broader people."
                + terrain_text
            )
        return (
            f"After surviving its fragile rebellion, the polity hardened into a full {government_type.lower()}."
            + terrain_text
        )
    if event.type == "polity_advance":
        return (
            f"Settlement growth and accumulated surplus pushed the realm into a more sophisticated political tier."
            + terrain_text
        )
    if event.type == "diplomacy_rivalry":
        return (
            f"Border friction, grievances, or strategic distrust pushed these factions into open rivalry."
            + terrain_text
        )
    if event.type == "diplomacy_pact":
        return (
            f"Mutual caution turned into a temporary understanding that should reduce opportunistic attacks."
            + terrain_text
        )
    if event.type == "diplomacy_alliance":
        return (
            f"Shared interests hardened into a formal alignment that blocks direct conflict."
            + terrain_text
        )
    if event.type == "diplomacy_truce":
        return (
            f"Recent violence or a secession settlement forced a temporary pause in fighting."
            + terrain_text
        )
    if event.type == "diplomacy_truce_end":
        return (
            f"The cooling-off period ended, leaving the relationship to settle into peace, rivalry, or renewed conflict."
            + terrain_text
        )
    if event.type == "diplomacy_break":
        return (
            f"A previous diplomatic bond collapsed as trust fell or strategic pressure mounted."
            + terrain_text
        )
    return "No summary available."


def build_simulation_snapshots(world):
    initial_state = build_initial_opening_state(world)
    initial_region_history = world.region_history[0] if world.region_history else {}
    region_state = {
        region_name: {
            "owner": initial_state[region_name]["owner"],
            "resources": initial_state[region_name]["resources"],
            "population": initial_region_history.get(region_name, {}).get("population", region.population),
            "productive_capacity": initial_region_history.get(region_name, {}).get("productive_capacity", get_region_productive_capacity(region, world)),
            "population_pressure": initial_region_history.get(region_name, {}).get("population_pressure", get_region_population_pressure(region)),
            "surplus": initial_region_history.get(region_name, {}).get("surplus", get_region_surplus(region, world)),
            "surplus_label": initial_region_history.get(region_name, {}).get("surplus_label", get_region_surplus_label(region, world)),
            "ethnic_composition": dict(initial_region_history.get(region_name, {}).get("ethnic_composition", region.ethnic_composition)),
            "dominant_ethnicity": initial_region_history.get(region_name, {}).get("dominant_ethnicity"),
            "ethnic_claimants": list(initial_region_history.get(region_name, {}).get("ethnic_claimants", get_region_ethnic_claimants(region, world))),
            "owner_primary_ethnicity": initial_region_history.get(region_name, {}).get("owner_primary_ethnicity", get_region_owner_primary_ethnicity(region, world)),
            "owner_has_ethnic_claim": initial_region_history.get(region_name, {}).get("owner_has_ethnic_claim", faction_has_ethnic_claim(world, region, region.owner)),
            "ruling_ethnic_affinity": initial_region_history.get(region_name, {}).get("ruling_ethnic_affinity", round(get_region_ruling_ethnic_affinity(region, world), 2)),
            "external_regime_agitators": list(initial_region_history.get(region_name, {}).get("external_regime_agitators", get_region_external_regime_agitators(region, world))),
            "external_regime_agitation": initial_region_history.get(region_name, {}).get("external_regime_agitation", round(get_region_external_regime_agitation_modifier(region, world), 3)),
            "neighbors": list(region.neighbors),
            "display_name": region.display_name if initial_state[region_name]["owner"] is not None else region.name,
            "founding_name": region.founding_name if initial_state[region_name]["owner"] is not None else "",
            "original_namer_faction_id": (
                region.original_namer_faction_id
                if initial_state[region_name]["owner"] is not None
                else None
            ),
            "terrain_tags": list(region.terrain_tags),
            "terrain_label": format_terrain_label(region.terrain_tags),
            "climate": region.climate,
            "climate_label": format_climate_label(region.climate),
            "resource_fixed_endowments": dict(initial_region_history.get(region_name, {}).get("resource_fixed_endowments", region.resource_fixed_endowments)),
            "resource_wild_endowments": dict(initial_region_history.get(region_name, {}).get("resource_wild_endowments", region.resource_wild_endowments)),
            "resource_suitability": dict(initial_region_history.get(region_name, {}).get("resource_suitability", region.resource_suitability)),
            "resource_established": dict(initial_region_history.get(region_name, {}).get("resource_established", region.resource_established)),
            "resource_output": dict(initial_region_history.get(region_name, {}).get("resource_output", region.resource_output)),
            "resource_effective_output": dict(initial_region_history.get(region_name, {}).get("resource_effective_output", region.resource_effective_output)),
            "resource_damage": dict(initial_region_history.get(region_name, {}).get("resource_damage", region.resource_damage)),
            "resource_isolation_factor": initial_region_history.get(region_name, {}).get("resource_isolation_factor", region.resource_isolation_factor),
            "resource_route_depth": initial_region_history.get(region_name, {}).get("resource_route_depth", region.resource_route_depth),
            "resource_route_cost": initial_region_history.get(region_name, {}).get("resource_route_cost", region.resource_route_cost),
            "resource_route_anchor": initial_region_history.get(region_name, {}).get("resource_route_anchor", region.resource_route_anchor),
            "resource_route_bottleneck": initial_region_history.get(region_name, {}).get("resource_route_bottleneck", region.resource_route_bottleneck),
            "resource_profile": initial_region_history.get(region_name, {}).get("resource_profile", _build_region_resource_payload(region)["resource_profile"]),
            "resource_output_summary": initial_region_history.get(region_name, {}).get("resource_output_summary", _build_region_resource_payload(region)["resource_output_summary"]),
            "taxable_value": initial_region_history.get(region_name, {}).get("taxable_value", _build_region_resource_payload(region)["taxable_value"]),
            "infrastructure_level": initial_region_history.get(region_name, {}).get("infrastructure_level", region.infrastructure_level),
            "agriculture_level": initial_region_history.get(region_name, {}).get("agriculture_level", region.agriculture_level),
            "pastoral_level": initial_region_history.get(region_name, {}).get("pastoral_level", region.pastoral_level),
            "extractive_level": initial_region_history.get(region_name, {}).get("extractive_level", region.extractive_level),
            "homeland_faction_id": initial_region_history.get(region_name, {}).get("homeland_faction_id"),
            "integrated_owner": initial_region_history.get(region_name, {}).get("integrated_owner"),
            "integration_score": initial_region_history.get(region_name, {}).get("integration_score", 0.0),
            "core_status": initial_region_history.get(region_name, {}).get("core_status", "frontier"),
            "settlement_level": initial_region_history.get(region_name, {}).get("settlement_level", region.settlement_level),
            "unrest": initial_region_history.get(region_name, {}).get("unrest", 0.0),
            "unrest_event_level": initial_region_history.get(region_name, {}).get("unrest_event_level", "none"),
            "unrest_event_turns_remaining": initial_region_history.get(region_name, {}).get("unrest_event_turns_remaining", 0),
        }
        for region_name, region in world.regions.items()
    }

    snapshots = [{
        "turn": 0,
        "events": [],
        "metrics": None,
        "regions": {
            region_name: {
                "owner": region["owner"],
                "resources": region["resources"],
                "population": region["population"],
                "productive_capacity": region["productive_capacity"],
                "population_pressure": region["population_pressure"],
                "surplus": region["surplus"],
                "surplus_label": region["surplus_label"],
                "ethnic_composition": dict(region["ethnic_composition"]),
                "dominant_ethnicity": region["dominant_ethnicity"],
                "ethnic_claimants": list(region["ethnic_claimants"]),
                "owner_primary_ethnicity": region["owner_primary_ethnicity"],
                "owner_has_ethnic_claim": region["owner_has_ethnic_claim"],
                "ruling_ethnic_affinity": region["ruling_ethnic_affinity"],
                "external_regime_agitators": list(region["external_regime_agitators"]),
                "external_regime_agitation": region["external_regime_agitation"],
                "display_name": region["display_name"],
                "founding_name": region["founding_name"],
                "original_namer_faction_id": region["original_namer_faction_id"],
                "terrain_tags": region["terrain_tags"],
                "terrain_label": region["terrain_label"],
                "climate": region["climate"],
                "climate_label": region["climate_label"],
                "resource_fixed_endowments": dict(region["resource_fixed_endowments"]),
                "resource_wild_endowments": dict(region["resource_wild_endowments"]),
                "resource_suitability": dict(region["resource_suitability"]),
                "resource_established": dict(region["resource_established"]),
                "resource_output": dict(region["resource_output"]),
                "resource_effective_output": dict(region["resource_effective_output"]),
                "resource_damage": dict(region["resource_damage"]),
                "resource_isolation_factor": region["resource_isolation_factor"],
                "resource_route_depth": region["resource_route_depth"],
                "resource_route_cost": region["resource_route_cost"],
                "resource_route_anchor": region["resource_route_anchor"],
                "resource_route_bottleneck": region["resource_route_bottleneck"],
                "resource_profile": region["resource_profile"],
                "resource_output_summary": region["resource_output_summary"],
                "taxable_value": region["taxable_value"],
                "infrastructure_level": region["infrastructure_level"],
                "agriculture_level": region["agriculture_level"],
                "pastoral_level": region["pastoral_level"],
                "extractive_level": region["extractive_level"],
                "homeland_faction_id": region["homeland_faction_id"],
                "integrated_owner": region["integrated_owner"],
                "integration_score": region["integration_score"],
                "core_status": region["core_status"],
                "settlement_level": region["settlement_level"],
                "unrest": region["unrest"],
                "unrest_event_level": region["unrest_event_level"],
                "unrest_event_turns_remaining": region["unrest_event_turns_remaining"],
            }
            for region_name, region in region_state.items()
        },
        "changed_regions": [],
        "contested_regions": [],
        "standings": _build_snapshot_standings_from_regions(region_state, world),
    }]

    for turn_number in range(1, world.turn + 1):
        turn_events = [event for event in world.events if event.turn == turn_number - 1]
        history_snapshot = world.region_history[turn_number] if len(world.region_history) > turn_number else {}
        changed_regions = []
        contested_regions = []

        for event in turn_events:
            if event.region is None:
                continue

            if event.type == "expand":
                region_state[event.region]["owner"] = event.faction
                region_state[event.region]["display_name"] = event.get(
                    "region_display_name",
                    region_state[event.region]["display_name"],
                )
                region_state[event.region]["founding_name"] = event.get(
                    "region_display_name",
                    region_state[event.region]["founding_name"],
                )
                region_state[event.region]["original_namer_faction_id"] = (
                    world.regions[event.region].original_namer_faction_id
                )
                changed_regions.append(event.region)
            elif event.type == "attack":
                contested_regions.append(event.region)
                if event.get("success", False):
                    region_state[event.region]["owner"] = event.faction
                    changed_regions.append(event.region)
            elif event.type == "invest":
                region_state[event.region]["resources"] = event.get(
                    "new_resources",
                    region_state[event.region]["resources"],
                )
                changed_regions.append(event.region)

        for region_name, history_region in history_snapshot.items():
            region_state[region_name]["owner"] = history_region["owner"]
            region_state[region_name]["resources"] = history_region["resources"]
            region_state[region_name]["population"] = history_region.get("population", region_state[region_name]["population"])
            region_state[region_name]["productive_capacity"] = history_region.get("productive_capacity", region_state[region_name]["productive_capacity"])
            region_state[region_name]["population_pressure"] = history_region.get("population_pressure", region_state[region_name]["population_pressure"])
            region_state[region_name]["surplus"] = history_region.get("surplus", region_state[region_name]["surplus"])
            region_state[region_name]["surplus_label"] = history_region.get("surplus_label", region_state[region_name]["surplus_label"])
            region_state[region_name]["ethnic_composition"] = dict(history_region.get("ethnic_composition", region_state[region_name]["ethnic_composition"]))
            region_state[region_name]["dominant_ethnicity"] = history_region.get("dominant_ethnicity")
            region_state[region_name]["ethnic_claimants"] = list(history_region.get("ethnic_claimants", region_state[region_name]["ethnic_claimants"]))
            region_state[region_name]["owner_primary_ethnicity"] = history_region.get("owner_primary_ethnicity")
            region_state[region_name]["owner_has_ethnic_claim"] = history_region.get("owner_has_ethnic_claim", False)
            region_state[region_name]["ruling_ethnic_affinity"] = history_region.get("ruling_ethnic_affinity", 0.0)
            region_state[region_name]["external_regime_agitators"] = list(history_region.get("external_regime_agitators", []))
            region_state[region_name]["external_regime_agitation"] = history_region.get("external_regime_agitation", 0.0)
            region_state[region_name]["resource_fixed_endowments"] = dict(history_region.get("resource_fixed_endowments", region_state[region_name]["resource_fixed_endowments"]))
            region_state[region_name]["resource_wild_endowments"] = dict(history_region.get("resource_wild_endowments", region_state[region_name]["resource_wild_endowments"]))
            region_state[region_name]["resource_suitability"] = dict(history_region.get("resource_suitability", region_state[region_name]["resource_suitability"]))
            region_state[region_name]["resource_established"] = dict(history_region.get("resource_established", region_state[region_name]["resource_established"]))
            region_state[region_name]["resource_output"] = dict(history_region.get("resource_output", region_state[region_name]["resource_output"]))
            region_state[region_name]["resource_effective_output"] = dict(history_region.get("resource_effective_output", region_state[region_name]["resource_effective_output"]))
            region_state[region_name]["resource_damage"] = dict(history_region.get("resource_damage", region_state[region_name]["resource_damage"]))
            region_state[region_name]["resource_isolation_factor"] = history_region.get("resource_isolation_factor", region_state[region_name]["resource_isolation_factor"])
            region_state[region_name]["resource_route_depth"] = history_region.get("resource_route_depth", region_state[region_name]["resource_route_depth"])
            region_state[region_name]["resource_route_cost"] = history_region.get("resource_route_cost", region_state[region_name]["resource_route_cost"])
            region_state[region_name]["resource_route_anchor"] = history_region.get("resource_route_anchor", region_state[region_name]["resource_route_anchor"])
            region_state[region_name]["resource_route_bottleneck"] = history_region.get("resource_route_bottleneck", region_state[region_name]["resource_route_bottleneck"])
            region_state[region_name]["resource_profile"] = history_region.get("resource_profile", region_state[region_name]["resource_profile"])
            region_state[region_name]["resource_output_summary"] = history_region.get("resource_output_summary", region_state[region_name]["resource_output_summary"])
            region_state[region_name]["taxable_value"] = history_region.get("taxable_value", region_state[region_name]["taxable_value"])
            region_state[region_name]["infrastructure_level"] = history_region.get("infrastructure_level", region_state[region_name]["infrastructure_level"])
            region_state[region_name]["agriculture_level"] = history_region.get("agriculture_level", region_state[region_name]["agriculture_level"])
            region_state[region_name]["pastoral_level"] = history_region.get("pastoral_level", region_state[region_name]["pastoral_level"])
            region_state[region_name]["extractive_level"] = history_region.get("extractive_level", region_state[region_name]["extractive_level"])
            region_state[region_name]["display_name"] = history_region["display_name"] or region_state[region_name]["display_name"]
            region_state[region_name]["founding_name"] = history_region["founding_name"]
            region_state[region_name]["original_namer_faction_id"] = history_region["original_namer_faction_id"]
            region_state[region_name]["homeland_faction_id"] = history_region["homeland_faction_id"]
            region_state[region_name]["integrated_owner"] = history_region["integrated_owner"]
            region_state[region_name]["integration_score"] = history_region["integration_score"]
            region_state[region_name]["core_status"] = history_region["core_status"]
            region_state[region_name]["settlement_level"] = history_region.get("settlement_level", region_state[region_name]["settlement_level"])
            region_state[region_name]["unrest"] = history_region.get("unrest", 0.0)
            region_state[region_name]["unrest_event_level"] = history_region.get("unrest_event_level", "none")
            region_state[region_name]["unrest_event_turns_remaining"] = history_region.get("unrest_event_turns_remaining", 0)
            region_state[region_name]["climate"] = history_region.get("climate", region_state[region_name]["climate"])
            region_state[region_name]["climate_label"] = format_climate_label(region_state[region_name]["climate"])

        metrics = get_turn_metrics(world, turn_number)
        snapshots.append({
            "turn": turn_number,
            "events": [_serialize_event(event, world) for event in turn_events],
            "metrics": metrics,
            "regions": {
                region_name: {
                    "owner": region["owner"],
                    "resources": region["resources"],
                    "population": region["population"],
                    "productive_capacity": region["productive_capacity"],
                    "population_pressure": region["population_pressure"],
                    "surplus": region["surplus"],
                    "surplus_label": region["surplus_label"],
                    "ethnic_composition": dict(region["ethnic_composition"]),
                    "dominant_ethnicity": region["dominant_ethnicity"],
                    "ethnic_claimants": list(region["ethnic_claimants"]),
                    "owner_primary_ethnicity": region["owner_primary_ethnicity"],
                    "owner_has_ethnic_claim": region["owner_has_ethnic_claim"],
                    "ruling_ethnic_affinity": region["ruling_ethnic_affinity"],
                    "external_regime_agitators": list(region["external_regime_agitators"]),
                    "external_regime_agitation": region["external_regime_agitation"],
                    "display_name": region["display_name"],
                    "founding_name": region["founding_name"],
                    "original_namer_faction_id": region["original_namer_faction_id"],
                    "terrain_tags": region["terrain_tags"],
                    "terrain_label": region["terrain_label"],
                    "climate": region["climate"],
                    "climate_label": region["climate_label"],
                    "resource_fixed_endowments": dict(region["resource_fixed_endowments"]),
                    "resource_wild_endowments": dict(region["resource_wild_endowments"]),
                    "resource_suitability": dict(region["resource_suitability"]),
                    "resource_established": dict(region["resource_established"]),
                    "resource_output": dict(region["resource_output"]),
                    "resource_effective_output": dict(region["resource_effective_output"]),
                    "resource_damage": dict(region["resource_damage"]),
                    "resource_isolation_factor": region["resource_isolation_factor"],
                    "resource_route_depth": region["resource_route_depth"],
                    "resource_route_cost": region["resource_route_cost"],
                    "resource_route_anchor": region["resource_route_anchor"],
                    "resource_route_bottleneck": region["resource_route_bottleneck"],
                    "resource_profile": region["resource_profile"],
                    "resource_output_summary": region["resource_output_summary"],
                    "taxable_value": region["taxable_value"],
                    "infrastructure_level": region["infrastructure_level"],
                    "agriculture_level": region["agriculture_level"],
                    "pastoral_level": region["pastoral_level"],
                    "extractive_level": region["extractive_level"],
                    "homeland_faction_id": region["homeland_faction_id"],
                    "integrated_owner": region["integrated_owner"],
                    "integration_score": region["integration_score"],
                    "core_status": region["core_status"],
                    "settlement_level": region["settlement_level"],
                    "unrest": region["unrest"],
                    "unrest_event_level": region["unrest_event_level"],
                    "unrest_event_turns_remaining": region["unrest_event_turns_remaining"],
                }
                for region_name, region in region_state.items()
            },
            "changed_regions": sorted(set(changed_regions), key=natural_sort_key),
            "contested_regions": sorted(set(contested_regions), key=natural_sort_key),
            "standings": _build_snapshot_standings(metrics, region_state, world),
        })

    return snapshots


def _build_snapshot_standings(metrics, region_state, world):
    if metrics is None:
        return _build_snapshot_standings_from_regions(region_state, world)

    standings = []
    for faction_name, faction_metrics in metrics["factions"].items():
        standings.append({
            "faction": faction_name,
            "treasury": faction_metrics["treasury"],
            "owned_regions": faction_metrics["regions"],
        })
    standings.sort(
        key=lambda item: (item["treasury"], item["owned_regions"]),
        reverse=True,
    )
    return standings


def _build_snapshot_standings_from_regions(region_state, world):
    owned_counts = Counter(
        region["owner"]
        for region in region_state.values()
        if region["owner"] in world.factions
    )
    standings = []
    for faction_name, faction in world.factions.items():
        standings.append({
            "faction": faction_name,
            "treasury": faction.starting_treasury,
            "owned_regions": owned_counts.get(faction_name, 0),
        })
    standings.sort(
        key=lambda item: (item["treasury"], item["owned_regions"]),
        reverse=True,
    )
    return standings


def _atlas_region_sort_key(region_name):
    if region_name.startswith("O"):
        bucket = 0
    elif region_name.startswith("M"):
        bucket = 1
    elif region_name.startswith("I"):
        bucket = 2
    elif region_name == "C":
        bucket = 4
    else:
        bucket = 3
    return (bucket, natural_sort_key(region_name))


def build_simulation_view_model(world):
    positions = build_map_layout(MAPS[world.map_name]["regions"], width=900, height=900)
    edges = get_map_edges(MAPS[world.map_name]["regions"])
    atlas_geometry = None
    atlas_coastline = []
    if is_multi_ring_map(MAPS[world.map_name]["regions"]):
        atlas_geometry = build_multi_ring_region_geometry(
            MAPS[world.map_name]["regions"],
            map_name=world.map_name,
            width=900,
            height=900,
        )
        atlas_coastline = [
            [round(point[0], 1), round(point[1], 1)]
            for point in build_multi_ring_coastline_polygon(width=900, height=900)
        ]
    snapshots = build_simulation_snapshots(world)
    final_standings = get_final_standings(world)
    phase_ranges = get_phase_ranges(world.turn)
    _phase_analyses, phase_summary_lines = summarize_phases(world)
    phase_summaries = [
        {
            "name": phase_name,
            "start_turn": start_turn,
            "end_turn": end_turn,
            "summary": summary_line,
        }
        for (phase_name, start_turn, end_turn), summary_line in zip(phase_ranges, phase_summary_lines)
    ]

    factions = [
        {
            "name": faction_name,
            "display_name": world.factions[faction_name].display_name,
            "internal_id": world.factions[faction_name].internal_id,
            "strategy": world.factions[faction_name].doctrine_label,
            "doctrine_label": world.factions[faction_name].doctrine_label,
            "doctrine_summary": world.factions[faction_name].doctrine_summary,
            "terrain_identity": world.factions[faction_name].doctrine_profile.terrain_identity,
            "homeland_identity": world.factions[faction_name].doctrine_profile.homeland_identity,
            "climate_identity": world.factions[faction_name].doctrine_profile.climate_identity,
            "is_rebel": world.factions[faction_name].is_rebel,
            "origin_faction": world.factions[faction_name].origin_faction,
            "rebel_conflict_type": world.factions[faction_name].rebel_conflict_type,
            "proto_state": world.factions[faction_name].proto_state,
            "known_factions": list(world.factions[faction_name].known_factions or []),
            "government_type": world.factions[faction_name].government_type,
            "polity_tier": world.factions[faction_name].polity_tier,
            "government_form": world.factions[faction_name].government_form,
            "primary_ethnicity": world.factions[faction_name].primary_ethnicity,
            "ethnic_claims": get_faction_ethnic_claims(world, faction_name),
            "rebel_age": world.factions[faction_name].rebel_age,
            "independence_score": world.factions[faction_name].independence_score,
            "resource_access": _serialize_resource_map(world.factions[faction_name].resource_access),
            "resource_gross_output": _serialize_resource_map(world.factions[faction_name].resource_gross_output),
            "resource_effective_access": _serialize_resource_map(world.factions[faction_name].resource_effective_access),
            "resource_isolated_output": _serialize_resource_map(world.factions[faction_name].resource_isolated_output),
            "resource_shortages": {
                key: round(float(value), 3)
                for key, value in (world.factions[faction_name].resource_shortages or {}).items()
            },
            "derived_capacity": {
                key: round(float(value), 3)
                for key, value in (world.factions[faction_name].derived_capacity or {}).items()
            },
            "resource_access_summary": format_resource_map(world.factions[faction_name].resource_access, limit=4),
            "resource_gross_summary": format_resource_map(world.factions[faction_name].resource_gross_output, limit=4),
            "resource_isolated_summary": format_resource_map(world.factions[faction_name].resource_isolated_output, limit=4),
            "resource_shortage_summary": ", ".join(
                [
                    f"{label} {value:.1f}"
                    for label, value in (
                        ("Food", world.factions[faction_name].resource_shortages.get("food_security", 0.0)),
                        ("Mobility", world.factions[faction_name].resource_shortages.get("mobility_capacity", 0.0)),
                        ("Metal", world.factions[faction_name].resource_shortages.get("metal_capacity", 0.0)),
                        ("Construction", world.factions[faction_name].resource_shortages.get("construction_capacity", 0.0)),
                    )
                    if value > 0
                ]
            ) or "None",
            "color": get_faction_color(
                faction_name,
                internal_id=world.factions[faction_name].internal_id,
            ),
        }
        for faction_name in sorted(world.factions, key=natural_sort_key)
    ]

    atlas_region_names = (
        sorted(atlas_geometry, key=_atlas_region_sort_key)
        if atlas_geometry is not None
        else []
    )

    return {
        "map_name": world.map_name,
        "map_description": MAPS[world.map_name]["description"],
        "turns": world.turn,
        "regions": [
            {
                "name": region_name,
                "display_name": get_region_display_name(world.regions[region_name]),
                "population": world.regions[region_name].population,
                "productive_capacity": get_region_productive_capacity(world.regions[region_name], world),
                "population_pressure": get_region_population_pressure(world.regions[region_name]),
                "surplus": get_region_surplus(world.regions[region_name], world),
                "surplus_label": get_region_surplus_label(world.regions[region_name], world),
                "dominant_ethnicity": get_region_dominant_ethnicity(world.regions[region_name]),
                "ethnic_claimants": get_region_ethnic_claimants(world.regions[region_name], world),
                "owner_primary_ethnicity": get_region_owner_primary_ethnicity(world.regions[region_name], world),
                "owner_has_ethnic_claim": faction_has_ethnic_claim(world, world.regions[region_name], world.regions[region_name].owner),
                "ruling_ethnic_affinity": round(get_region_ruling_ethnic_affinity(world.regions[region_name], world), 2),
                "external_regime_agitators": get_region_external_regime_agitators(world.regions[region_name], world),
                "external_regime_agitation": round(get_region_external_regime_agitation_modifier(world.regions[region_name], world), 3),
                "terrain_tags": list(world.regions[region_name].terrain_tags),
                "terrain_label": format_terrain_label(world.regions[region_name].terrain_tags),
                "climate": world.regions[region_name].climate,
                "climate_label": format_climate_label(world.regions[region_name].climate),
                "settlement_level": world.regions[region_name].settlement_level,
                **_build_region_resource_payload(world.regions[region_name]),
                "x": round(positions[region_name][0], 1),
                "y": round(positions[region_name][1], 1),
                "neighbors": sorted(region_data["neighbors"], key=natural_sort_key),
            }
            for region_name, region_data in sorted(
                MAPS[world.map_name]["regions"].items(),
                key=lambda item: natural_sort_key(item[0]),
            )
        ],
        "atlas_regions": [
            {
                "name": region_name,
                "display_name": get_region_display_name(world.regions[region_name]),
                "population": world.regions[region_name].population,
                "productive_capacity": get_region_productive_capacity(world.regions[region_name], world),
                "population_pressure": get_region_population_pressure(world.regions[region_name]),
                "surplus": get_region_surplus(world.regions[region_name], world),
                "surplus_label": get_region_surplus_label(world.regions[region_name], world),
                "dominant_ethnicity": get_region_dominant_ethnicity(world.regions[region_name]),
                "ethnic_claimants": get_region_ethnic_claimants(world.regions[region_name], world),
                "owner_primary_ethnicity": get_region_owner_primary_ethnicity(world.regions[region_name], world),
                "owner_has_ethnic_claim": faction_has_ethnic_claim(world, world.regions[region_name], world.regions[region_name].owner),
                "ruling_ethnic_affinity": round(get_region_ruling_ethnic_affinity(world.regions[region_name], world), 2),
                "external_regime_agitators": get_region_external_regime_agitators(world.regions[region_name], world),
                "external_regime_agitation": round(get_region_external_regime_agitation_modifier(world.regions[region_name], world), 3),
                "terrain_tags": list(world.regions[region_name].terrain_tags),
                "terrain_label": format_terrain_label(world.regions[region_name].terrain_tags),
                "climate": world.regions[region_name].climate,
                "climate_label": format_climate_label(world.regions[region_name].climate),
                "settlement_level": world.regions[region_name].settlement_level,
                **_build_region_resource_payload(world.regions[region_name]),
                "polygon": [
                    [round(point[0], 1), round(point[1], 1)]
                    for point in atlas_geometry[region_name]["polygon"]
                ],
                "label_x": round(atlas_geometry[region_name]["label"][0], 1),
                "label_y": round(atlas_geometry[region_name]["label"][1], 1),
            }
            for region_name in atlas_region_names
        ] if atlas_geometry is not None else [],
        "atlas_coastline": atlas_coastline,
        "edges": edges,
        "factions": factions,
        "ethnicities": [
            {
                "name": ethnicity.name,
                "language_family": ethnicity.language_family,
                "parent_ethnicity": ethnicity.parent_ethnicity,
                "origin_faction": ethnicity.origin_faction,
            }
            for ethnicity in sorted(world.ethnicities.values(), key=lambda item: natural_sort_key(item.name))
        ],
        "snapshots": snapshots,
        "phase_summaries": phase_summaries,
        "narrative_summary": {
            "strategic": summarize_strategic_interpretation(world),
            "victor": summarize_victor_history(world),
            "final": summarize_final_standings(world),
        },
        "final_standings": final_standings,
    }


def render_simulation_html(world):
    view_model = build_simulation_view_model(world)
    json_payload = json.dumps(view_model)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(world.map_name)} Simulation Viewer</title>
  <style>
    :root {{
      --bg: #0d1117;
      --panel: rgba(252, 248, 241, 0.94);
      --panel-strong: #fffdf8;
      --panel-soft: rgba(255, 255, 255, 0.72);
      --ink: #17212b;
      --muted: #4f6273;
      --line: rgba(46, 58, 71, 0.16);
      --accent: #1d5a55;
      --accent-soft: #d7ebe8;
      --shadow: 0 22px 60px rgba(10, 18, 28, 0.16);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Aptos", "Segoe UI", "Trebuchet MS", sans-serif;
      line-height: 1.5;
      color: var(--ink);
      background:
        radial-gradient(circle at top, rgba(72, 122, 148, 0.18), transparent 32%),
        linear-gradient(180deg, #10151d 0%, #0d1117 52%, #080b10 100%);
    }}
    .page {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px;
    }}
    .panel {{
      background: var(--panel);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255,255,255,0.48);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    h1, h2, h3, strong {{
      font-family: "Iowan Old Style", Georgia, "Times New Roman", serif;
      letter-spacing: -0.01em;
    }}
    .eyebrow {{
      display: inline-flex;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(32, 78, 74, 0.1);
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 12px;
      font-weight: 700;
    }}
    h1 {{
      margin: 14px 0 8px;
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 1.02;
    }}
    .lede {{
      margin: 0;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.6;
      max-width: 70ch;
    }}
    .hero-meta {{
      margin-top: 18px;
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(260px, 0.75fr);
      gap: 20px;
      align-items: start;
    }}
    .hero-subpanel {{
      background: rgba(255,255,255,0.52);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 18px;
      padding: 16px 18px;
    }}
    .overview-copy {{
      margin: 0;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.7;
      max-width: 68ch;
    }}
    .settings-block {{
      justify-self: stretch;
      text-align: left;
      min-width: 220px;
    }}
    .settings-list {{
      margin: 10px 0 0;
      display: grid;
      gap: 8px;
    }}
    .setting-row {{
      display: grid;
      gap: 2px;
    }}
    .setting-label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .setting-value {{
      font-size: 0.98rem;
      font-weight: 600;
      color: var(--ink);
    }}
    .layout {{
      display: grid;
      gap: 22px;
    }}
    .section-title {{
      margin: 0 0 14px;
      font-size: 1.2rem;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}
    .playback-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.62fr);
      gap: 18px;
      align-items: start;
    }}
    .map-stage {{
      min-width: 0;
    }}
    .side-rail {{
      display: grid;
      gap: 14px;
      min-width: 0;
    }}
    .side-section {{
      background: rgba(255,255,255,0.5);
      border: 1px solid rgba(63, 74, 89, 0.1);
      border-radius: 20px;
      padding: 16px;
    }}
    .side-title {{
      margin: 0 0 10px;
      font-size: 0.95rem;
    }}
    .map-shell {{
      position: relative;
      overflow: hidden;
      background:
        radial-gradient(circle at center, rgba(255,255,255,0.92), rgba(255,255,255,0.42)),
        radial-gradient(circle at 50% 30%, rgba(211, 232, 227, 0.48), transparent 58%),
        linear-gradient(180deg, rgba(194, 219, 214, 0.35), rgba(255,255,255,0.05));
      border-radius: 22px;
      border: 1px solid rgba(63, 74, 89, 0.12);
      padding: 12px;
    }}
    .controls {{
      display: grid;
      gap: 14px;
      margin-bottom: 14px;
      background: rgba(255,255,255,0.52);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 18px;
      padding: 14px;
    }}
    .transport {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .view-toggle {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .toggle-row {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      font: inherit;
      font-weight: 700;
      color: #fff;
      background: linear-gradient(135deg, #204e4a, #356f69);
      cursor: pointer;
      box-shadow: 0 10px 20px rgba(32, 78, 74, 0.2);
    }}
    button.secondary {{
      color: var(--ink);
      background: #efe6d4;
      box-shadow: none;
    }}
    button.secondary.active {{
      color: #fff;
      background: linear-gradient(135deg, #204e4a, #356f69);
      box-shadow: 0 10px 20px rgba(32, 78, 74, 0.16);
    }}
    .turn-readout {{
      font-size: 0.95rem;
      color: var(--muted);
      font-weight: 600;
    }}
    .timeline-controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    input[type="range"] {{
      width: 100%;
      accent-color: #204e4a;
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .edge {{
      stroke: rgba(83, 88, 98, 0.28);
      stroke-width: 2;
    }}
    .atlas-water {{
      fill: rgba(24, 73, 122, 0.34);
    }}
    .atlas-landmass {{
      fill: rgba(219, 212, 188, 0.45);
      stroke: rgba(91, 81, 59, 0.36);
      stroke-width: 5;
      filter: drop-shadow(0 18px 24px rgba(58, 67, 79, 0.12));
    }}
    .atlas-relief {{
      fill: none;
      stroke: rgba(105, 120, 93, 0.14);
      stroke-width: 2;
      stroke-linejoin: round;
      stroke-linecap: round;
      stroke-dasharray: 8 8;
    }}
    .atlas-symbol {{
      fill: none;
      stroke: rgba(66, 59, 46, 0.44);
      stroke-width: 1.35;
      stroke-linecap: round;
      stroke-linejoin: round;
      opacity: 0.72;
      pointer-events: none;
    }}
    .atlas-symbol.soft-fill {{
      fill: rgba(250, 244, 232, 0.1);
    }}
    .atlas-symbol.water {{
      stroke: rgba(54, 105, 150, 0.58);
    }}
    .atlas-symbol.vegetation {{
      stroke: rgba(55, 98, 60, 0.58);
    }}
    .atlas-symbol.earth {{
      stroke: rgba(104, 81, 56, 0.58);
    }}
    .atlas-territory {{
      stroke: rgba(60, 51, 36, 0.82);
      stroke-width: 2.2;
      stroke-linejoin: round;
      transition: fill 180ms ease, stroke-width 180ms ease, transform 180ms ease;
    }}
    .atlas-territory.changed {{
      stroke-width: 4;
    }}
    .atlas-territory.contested {{
      stroke: #8a2f1f;
    }}
    .region-node {{
      stroke: rgba(37, 43, 52, 0.65);
      stroke-width: 1.6;
      transition: transform 180ms ease, fill 180ms ease, stroke-width 180ms ease;
    }}
    .region-node.changed {{
      stroke-width: 4;
      transform: scale(1.08);
    }}
    .region-node.contested {{
      stroke: #8a2f1f;
    }}
    .region-label {{
      font-size: 13px;
      font-weight: 700;
      fill: #111827;
      paint-order: stroke;
      stroke: rgba(255, 252, 245, 0.94);
      stroke-width: 3px;
      pointer-events: none;
    }}
    .region-resource {{
      font-size: 11px;
      letter-spacing: 0.05em;
      font-weight: 700;
      fill: #274c5e;
      paint-order: stroke;
      stroke: rgba(255, 252, 245, 0.92);
      stroke-width: 2.6px;
      pointer-events: none;
    }}
    .terrain-overlay {{
      font-size: 9.5px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 700;
      fill: #4b5f4b;
      pointer-events: none;
      opacity: 0.88;
    }}
    .atlas-polity-label {{
      font-size: 18px;
      font-weight: 800;
      fill: #14202b;
      text-anchor: middle;
      pointer-events: none;
      paint-order: stroke;
      stroke: rgba(255, 252, 245, 0.96);
      stroke-width: 5px;
      letter-spacing: 0.01em;
    }}
    .atlas-polity-label.small {{
      font-size: 15px;
    }}
    .atlas-polity-label.large {{
      font-size: 21px;
    }}
    .atlas-polity-label-sub {{
      font-size: 13px;
      font-weight: 700;
      fill: var(--muted);
      text-anchor: middle;
      pointer-events: none;
      paint-order: stroke;
      stroke: rgba(255, 252, 245, 0.94);
      stroke-width: 4px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    .map-layer.hidden {{
      display: none;
    }}
    .legend {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    .terrain-legend {{
      margin-top: 10px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .timeline-shell {{
      background: rgba(255,255,255,0.46);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 20px;
      padding: 14px;
    }}
    .timeline-caption {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 0.94rem;
      line-height: 1.6;
    }}
    .timeline-key {{
      margin-top: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .timeline-key-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .timeline-line-chip {{
      width: 18px;
      height: 3px;
      border-radius: 999px;
      display: inline-block;
    }}
    .timeline-axis {{
      stroke: rgba(63, 74, 89, 0.22);
      stroke-width: 1.4;
    }}
    .timeline-grid {{
      stroke: rgba(63, 74, 89, 0.12);
      stroke-width: 1;
      stroke-dasharray: 4 6;
    }}
    .timeline-label {{
      fill: var(--muted);
      font-size: 12px;
      font-family: Georgia, "Times New Roman", serif;
    }}
    .timeline-line {{
      fill: none;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    .timeline-dot {{
      stroke: rgba(255,255,255,0.9);
      stroke-width: 2;
    }}
    .timeline-shift {{
      fill: #fff7d6;
      stroke: #9a7a2f;
      stroke-width: 1.5;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 0.92rem;
      color: var(--muted);
    }}
    .swatch {{
      width: 13px;
      height: 13px;
      border-radius: 999px;
      border: 1px solid rgba(17, 24, 39, 0.45);
    }}
    .terrain-chip {{
      width: 14px;
      height: 14px;
      border-radius: 5px;
      border: 1px solid rgba(17, 24, 39, 0.16);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.28);
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .summary-stack {{
      display: grid;
      gap: 12px;
    }}
    .settings-label {{
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .panel-hidden {{
      display: none;
    }}
    .summary-card {{
      background: rgba(255,255,255,0.56);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 18px;
      padding: 16px;
    }}
    .summary-card strong {{
      display: block;
      font-size: 0.92rem;
      margin-bottom: 8px;
    }}
    .summary-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .card-header strong {{
      margin-bottom: 0;
    }}
    .summary-copy {{
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.55;
    }}
    .scroll-panel {{
      max-height: 420px;
      overflow-y: auto;
      padding-right: 4px;
    }}
    .scroll-panel::-webkit-scrollbar {{
      width: 10px;
    }}
    .scroll-panel::-webkit-scrollbar-thumb {{
      background: rgba(63, 74, 89, 0.2);
      border-radius: 999px;
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    .stat-grid {{
      margin-top: 14px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }}
    .stat-grid.compact {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-top: 12px;
    }}
    .stat-chip {{
      display: grid;
      gap: 2px;
      padding: 10px 12px;
      background: var(--panel-soft);
      border: 1px solid rgba(63, 74, 89, 0.08);
      border-radius: 14px;
      min-width: 0;
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .stat-value {{
      color: var(--ink);
      font-size: 1rem;
      font-weight: 700;
    }}
    .summary-list {{
      margin: 10px 0 0;
      padding-left: 18px;
      color: var(--muted);
    }}
    .summary-list li + li {{
      margin-top: 8px;
    }}
    .list {{
      display: grid;
      gap: 10px;
    }}
    .event-item, .standing-item {{
      display: grid;
      gap: 6px;
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255,255,255,0.56);
      border: 1px solid rgba(63, 74, 89, 0.08);
    }}
    .standings-bar {{
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .standing-item.bar {{
      padding: 12px 14px;
      gap: 4px;
      border-radius: 16px;
      min-width: 0;
    }}
    .standing-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }}
    .event-meta, .subtle {{
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .event-header {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .event-icon {{
      width: 28px;
      height: 28px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      font-size: 0.95rem;
      line-height: 1;
      border: 1px solid rgba(31, 41, 51, 0.12);
      background: rgba(255,255,255,0.9);
      color: var(--ink);
    }}
    .event-icon-expand {{
      background: rgba(61, 122, 72, 0.14);
      color: #2f6a39;
    }}
    .event-icon-invest {{
      background: rgba(189, 140, 58, 0.18);
      color: #8a5a12;
    }}
    .event-icon-attack {{
      background: rgba(143, 74, 66, 0.16);
      color: #7e2f24;
    }}
    .event-icon-unrest {{
      background: rgba(173, 95, 33, 0.16);
      color: #8c4b12;
    }}
    .event-icon-secession {{
      background: rgba(110, 42, 74, 0.18);
      color: #6e2a4a;
    }}
    .event-icon-success {{
      background: rgba(46, 111, 76, 0.16);
      color: #2f6a39;
    }}
    .faction-inline {{
      font-weight: 700;
    }}
    .pill {{
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 12px;
      background: rgba(0,0,0,0.05);
      font-weight: 700;
      white-space: nowrap;
    }}
    .mini-stats {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .detail-grid {{
      display: grid;
      gap: 10px;
    }}
    .detail-grid-two {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .detail-section + .detail-section {{
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
    }}
    .detail-section-title {{
      margin: 0 0 10px;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .detail-row {{
      display: grid;
      gap: 3px;
    }}
    .detail-label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .detail-value {{
      font-size: 0.98rem;
      color: var(--ink);
    }}
    .panel-note {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .summary-card .panel-note {{
      margin: 6px 0 0;
    }}
    @media (max-width: 1100px) {{
      .playback-layout {{
        grid-template-columns: 1fr;
      }}
      .standings-bar,
      .hero-meta,
      .stat-grid,
      .detail-grid-two {{
        grid-template-columns: 1fr;
      }}
      .settings-block {{
        justify-self: start;
        text-align: left;
      }}
    }}
    @media (max-width: 720px) {{
      .page {{
        padding: 16px;
      }}
      .hero-meta {{
        grid-template-columns: 1fr;
      }}
      .standings-bar {{
        grid-template-columns: 1fr;
      }}
      .stat-grid.compact {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        line-height: 1.02;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="layout">
      <div class="panel">
        <span class="eyebrow">Simulation Viewer</span>
        <h1>Clashvergence</h1>
        <div class="hero-meta">
          <div class="hero-subpanel">
            <p class="settings-label">Overview</p>
            <p class="overview-copy">This simulation is meant to replicate the way human nations clash and converge across time and space, with geography, expansion pressure, and strategic tradeoffs shaping how power rises, collides, and settles.</p>
          </div>
          <div class="hero-subpanel settings-block">
            <p class="settings-label">Simulation Settings</p>
            <div class="settings-list">
              <div class="setting-row">
                <div class="setting-label">Map</div>
                <div class="setting-value">{html.escape(world.map_name.replace("_", " ").title())}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Turns</div>
                <div class="setting-value">{world.turn}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Regions</div>
                <div class="setting-value">{len(world.regions)}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Factions</div>
                <div class="setting-value">{len(world.factions)}</div>
              </div>
              <div class="setting-row">
                <div class="setting-label">Events</div>
                <div class="setting-value">{len(world.events)}</div>
              </div>
            </div>
          </div>
        </div>

        <h2 class="section-title">Map Playback</h2>
        <div class="controls">
          <div class="transport">
            <button type="button" id="play-toggle">Play</button>
            <button type="button" class="secondary" id="prev-turn">Prev</button>
            <button type="button" class="secondary" id="next-turn">Next</button>
            <div class="turn-readout" id="turn-readout">Turn 0 of 0</div>
          </div>
          <div class="toggle-row">
            <div class="view-toggle" id="view-toggle"></div>
            <div class="view-toggle" id="terrain-toggle"></div>
          </div>
          <input id="turn-slider" type="range" min="0" max="0" value="0">
        </div>
        <div class="playback-layout">
          <div class="map-stage">
            <div class="map-shell">
              <svg id="simulation-map" viewBox="0 0 900 900" role="img" aria-label="Simulation map">
                <g id="atlas-background-layer" class="map-layer"></g>
                <g id="atlas-layer" class="map-layer"></g>
                <g id="atlas-symbol-layer" class="map-layer"></g>
                <g id="atlas-label-layer" class="map-layer"></g>
                <g id="atlas-polity-label-layer" class="map-layer hidden"></g>
                <g id="atlas-terrain-layer" class="map-layer hidden"></g>
                <g id="graph-layer" class="map-layer">
                  <g id="edge-layer"></g>
                  <g id="region-layer"></g>
                  <g id="label-layer"></g>
                  <g id="terrain-layer" class="map-layer hidden"></g>
                </g>
              </svg>
            </div>
            <div class="legend" id="legend"></div>
            <div class="terrain-legend" id="terrain-legend"></div>
          </div>
          <aside class="side-rail">
            <section class="side-section">
              <h3 class="side-title">Current Turn</h3>
              <div class="summary-stack">
                <article class="summary-card" id="turn-context"></article>
                <div class="list scroll-panel" id="turn-events"></div>
              </div>
            </section>
            <section class="side-section">
              <h3 class="side-title">Region Detail</h3>
              <article class="summary-card" id="region-detail"></article>
            </section>
            <section class="side-section">
              <h3 class="side-title">Doctrine Evolution</h3>
              <p class="panel-note">Faction posture, diplomacy, and structural pressure at the current turn.</p>
              <div class="summary-stack scroll-panel" id="doctrine-panel"></div>
            </section>
          </aside>
        </div>
        <div class="standings-bar" id="standings"></div>
      </div>

      <div class="panel panel-hidden" id="run-summary-panel">
        <h2 class="section-title">Run Summary</h2>
        <div class="summary-stack" id="run-summary"></div>
      </div>

      <div class="panel">
        <div class="section-header">
          <h2 class="section-title">Doctrine Timeline</h2>
          <div class="timeline-controls" id="doctrine-timeline-controls"></div>
        </div>
        <div class="timeline-shell">
          <svg viewBox="0 0 920 320" role="img" aria-label="Doctrine posture timeline" id="doctrine-timeline"></svg>
          <div class="timeline-key" id="doctrine-timeline-key"></div>
          <p class="timeline-caption" id="doctrine-timeline-caption"></p>
        </div>
      </div>
    </section>
  </div>

  <script>
    const data = {json_payload};
    const unclaimedColor = {json.dumps(get_faction_color(None))};
    const state = {{
      currentTurn: 0,
      playing: false,
      timer: null,
      mapView: data.atlas_regions.length ? "atlas" : "graph",
      atlasLabelMode: "regions",
      showTerrainOverlay: false,
      colorMode: "ownership",
      focusRegionName: null,
    }};

    const slider = document.getElementById("turn-slider");
    const readout = document.getElementById("turn-readout");
    const playToggle = document.getElementById("play-toggle");
    const prevButton = document.getElementById("prev-turn");
    const nextButton = document.getElementById("next-turn");
    const viewToggle = document.getElementById("view-toggle");
    const terrainToggle = document.getElementById("terrain-toggle");
    const atlasBackgroundLayer = document.getElementById("atlas-background-layer");
    const atlasLayer = document.getElementById("atlas-layer");
    const atlasSymbolLayer = document.getElementById("atlas-symbol-layer");
    const atlasLabelLayer = document.getElementById("atlas-label-layer");
    const atlasPolityLabelLayer = document.getElementById("atlas-polity-label-layer");
    const atlasTerrainLayer = document.getElementById("atlas-terrain-layer");
    const graphLayer = document.getElementById("graph-layer");
    const regionLayer = document.getElementById("region-layer");
    const edgeLayer = document.getElementById("edge-layer");
    const labelLayer = document.getElementById("label-layer");
    const terrainLayer = document.getElementById("terrain-layer");
    const legend = document.getElementById("legend");
    const terrainLegend = document.getElementById("terrain-legend");
    const standings = document.getElementById("standings");
    const turnContext = document.getElementById("turn-context");
    const turnEvents = document.getElementById("turn-events");
    const doctrinePanel = document.getElementById("doctrine-panel");
    const regionDetail = document.getElementById("region-detail");
    const runSummaryPanel = document.getElementById("run-summary-panel");
    const runSummary = document.getElementById("run-summary");
    const doctrineTimelineControls = document.getElementById("doctrine-timeline-controls");
    const doctrineTimeline = document.getElementById("doctrine-timeline");
    const doctrineTimelineKey = document.getElementById("doctrine-timeline-key");
    const doctrineTimelineCaption = document.getElementById("doctrine-timeline-caption");

    const colorByFaction = Object.fromEntries(data.factions.map((faction) => [faction.name, faction.color]));
    const staticRegionByName = Object.fromEntries(data.regions.map((region) => [region.name, region]));
    const atlasRegionByName = Object.fromEntries(data.atlas_regions.map((region) => [region.name, region]));
    const terrainBaseColors = {{
      coast: "#5a88c7",
      riverland: "#43b38f",
      highland: "#8b6a4f",
      hills: "#c49a63",
      marsh: "#6d7e4a",
      forest: "#3d7a48",
      steppe: "#d4bf63",
      plains: "#b8d879",
    }};
    const climateColors = {{
      temperate: "#8ebf78",
      oceanic: "#5b90cc",
      cold: "#9dc3d9",
      arid: "#d8b46a",
      steppe: "#c9c06f",
      tropical: "#4ea56d",
    }};
    const unrestColors = {{
      calm: "#9fb4a5",
      watch: "#d8c46a",
      disturbance: "#d88b4a",
      crisis: "#b24c37",
      secession: "#6e2a4a",
    }};
    const doctrineLineColors = {{
      expansion_posture: "#2d6a4f",
      war_posture: "#b24c37",
      development_posture: "#3c78a8",
      insularity: "#7b5ea7",
    }};

    if (!state.focusFactionName && data.factions.length) {{
      state.focusFactionName = data.factions[0].name;
    }}

    function getTerrainColor(tags) {{
      const [primaryTag = "plains"] = tags || [];
      return terrainBaseColors[primaryTag] || terrainBaseColors.plains;
    }}

    function getClimateColor(climate) {{
      return climateColors[climate || "temperate"] || climateColors.temperate;
    }}

    function getUnrestTier(regionSnapshot) {{
      const unrest = Number(regionSnapshot.unrest || 0);
      const eventLevel = regionSnapshot.unrest_event_level || "none";
      if (!regionSnapshot.owner) {{
        return "secession";
      }}
      if (eventLevel === "crisis") {{
        return "crisis";
      }}
      if (eventLevel === "disturbance") {{
        return "disturbance";
      }}
      if (unrest >= 7.5) {{
        return "crisis";
      }}
      if (unrest >= 4.0) {{
        return "disturbance";
      }}
      if (unrest >= 2.0) {{
        return "watch";
      }}
      return "calm";
    }}

    function getUnrestColor(regionSnapshot) {{
      return unrestColors[getUnrestTier(regionSnapshot)] || unrestColors.calm;
    }}

    function getUnrestLabel(regionSnapshot) {{
      const unrest = Number(regionSnapshot.unrest || 0);
      const eventLevel = regionSnapshot.unrest_event_level || "none";
      if (!regionSnapshot.owner) {{
        return "Seceded / Neutral";
      }}
      if (eventLevel === "crisis") {{
        return `Crisis (${{unrest.toFixed(1)}})`;
      }}
      if (eventLevel === "disturbance") {{
        return `Disturbance (${{unrest.toFixed(1)}})`;
      }}
      if (unrest >= 7.5) {{
        return `Critical (${{unrest.toFixed(1)}})`;
      }}
      if (unrest >= 4.0) {{
        return `Moderate (${{unrest.toFixed(1)}})`;
      }}
      if (unrest >= 2.0) {{
        return `Watch (${{unrest.toFixed(1)}})`;
      }}
      return `Calm (${{unrest.toFixed(1)}})`;
    }}

    function getTerrainAbbreviation(tags) {{
      const visibleTags = (tags || []).filter((tag) => tag !== "coast");
      return visibleTags.map((tag) => tag.slice(0, 2).toUpperCase()).join("/");
    }}

    function getRegionFill(regionSnapshot, staticRegion) {{
      if (state.colorMode === "terrain") {{
        return getTerrainColor(regionSnapshot.terrain_tags || staticRegion.terrain_tags);
      }}
      if (state.colorMode === "climate") {{
        return getClimateColor(regionSnapshot.climate || staticRegion.climate);
      }}
      if (state.colorMode === "unrest") {{
        return getUnrestColor(regionSnapshot);
      }}
      return colorByFaction[regionSnapshot.owner] || unclaimedColor;
    }}

    function getColorModeLabel() {{
      if (state.colorMode === "terrain") {{
        return "Terrain";
      }}
      if (state.colorMode === "climate") {{
        return "Climate";
      }}
      if (state.colorMode === "unrest") {{
        return "Unrest";
      }}
      return "Ownership";
    }}

    function cycleColorMode() {{
      if (state.colorMode === "ownership") {{
        state.colorMode = "terrain";
      }} else if (state.colorMode === "terrain") {{
        state.colorMode = "climate";
      }} else if (state.colorMode === "climate") {{
        state.colorMode = "unrest";
      }} else {{
        state.colorMode = "ownership";
      }}
    }}

    function formatPosture(value) {{
      if (value >= 0.72) {{
        return "High";
      }}
      if (value >= 0.46) {{
        return "Medium";
      }}
      return "Low";
    }}

    function getRegionDataByName(regionName) {{
      return data.regions.find((region) => region.name === regionName)
        || data.atlas_regions.find((region) => region.name === regionName)
        || null;
    }}

    function getFactionDataByName(factionName) {{
      return data.factions.find((faction) => faction.name === factionName) || null;
    }}

    function getFactionDisplayName(factionName) {{
      if (!factionName) {{
        return "Unclaimed";
      }}
      const faction = getFactionDataByName(factionName);
      return faction ? (faction.display_name || faction.name) : factionName;
    }}

    function svgElement(name, attrs) {{
      const element = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [key, value] of Object.entries(attrs)) {{
        element.setAttribute(key, value);
      }}
      return element;
    }}

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }}

    function formatResourceDamage(resourceDamage) {{
      const entries = Object.entries(resourceDamage || {{}})
        .filter(([, value]) => Number(value || 0) > 0.04)
        .sort((left, right) => Number(right[1]) - Number(left[1]));
      if (!entries.length) {{
        return "Low";
      }}
      const [resourceName, value] = entries[0];
      return `${{escapeHtml(resourceName.replaceAll("_", " "))}} ${{Number(value).toFixed(2)}}`;
    }}

    function colorizeFactionNames(text) {{
      let highlighted = escapeHtml(text ?? "");
      const factionsByLength = [...data.factions]
        .sort((left, right) => (right.display_name || right.name).length - (left.display_name || left.name).length);

      for (const faction of factionsByLength) {{
        const safeName = escapeHtml(faction.display_name || faction.name);
        highlighted = highlighted.split(safeName).join(
          `<span class="faction-inline" style="color:${{faction.color}};">${{safeName}}</span>`,
        );
      }}

      return highlighted;
    }}

    function getEventIconData(type) {{
      if (type === "expand") {{
        return {{ symbol: "◌", className: "event-icon-expand", label: "Expansion" }};
      }}
      if (type === "invest") {{
        return {{ symbol: "▲", className: "event-icon-invest", label: "Investment" }};
      }}
      if (type === "attack") {{
        return {{ symbol: "⚔", className: "event-icon-attack", label: "Attack" }};
      }}
      return {{ symbol: "•", className: "", label: "Event" }};
    }}

    function polygonPointsText(points) {{
      return points.map((point) => `${{point[0]}},${{point[1]}}`).join(" ");
    }}

    function getAtlasSymbolOffsets(count) {{
      if (count <= 1) {{
        return [
          [-32, -24],
          [0, -32],
          [32, -24],
          [-34, 0],
          [34, 0],
          [-24, 24],
          [24, 24],
        ];
      }}
      if (count === 2) {{
        return [
          [-36, -26],
          [0, -34],
          [36, -26],
          [-38, 2],
          [38, 2],
          [-28, 26],
          [0, 32],
          [28, 26],
        ];
      }}
      return [
        [-38, -28],
        [-10, -36],
        [20, -34],
        [40, -6],
        [36, 24],
        [8, 34],
        [-22, 32],
        [-40, 6],
      ];
    }}

    function getDisplayTerrainTags(tags) {{
      const filtered = (tags || []).filter((tag) => tag !== "plains" && tag !== "coast");
      if (filtered.length) {{
        return filtered.slice(0, 3);
      }}
      return ["plains"];
    }}

    function splitPolityLabel(displayName) {{
      const words = String(displayName || "").trim().split(/\\s+/).filter(Boolean);
      if (words.length <= 1) {{
        return [displayName || "Unclaimed"];
      }}
      if (words.length === 2) {{
        return words;
      }}
      return [words.slice(0, -1).join(" "), words.at(-1)];
    }}

    function resolvePolityLabelOverlap(labels) {{
      const minimumDistance = 58;
      const resolved = labels
        .map((label) => ({{ ...label }}))
        .sort((left, right) => left.y - right.y);

      for (let index = 0; index < resolved.length; index += 1) {{
        for (let compareIndex = 0; compareIndex < index; compareIndex += 1) {{
          const current = resolved[index];
          const previous = resolved[compareIndex];
          const dx = current.x - previous.x;
          const dy = current.y - previous.y;
          if (Math.hypot(dx, dy) < minimumDistance) {{
            current.y = Math.min(850, previous.y + minimumDistance);
          }}
        }}
      }}

      return resolved;
    }}

    function getAtlasPolityLabelData(snapshot) {{
      const visited = new Set();
      const clusters = [];

      for (const region of data.atlas_regions) {{
        const regionSnapshot = snapshot.regions[region.name];
        if (!regionSnapshot || !regionSnapshot.owner || visited.has(region.name)) {{
          continue;
        }}

        const owner = regionSnapshot.owner;
        const stack = [region.name];
        const component = [];

        while (stack.length) {{
          const currentName = stack.pop();
          if (visited.has(currentName)) {{
            continue;
          }}

          const currentSnapshot = snapshot.regions[currentName];
          if (!currentSnapshot || currentSnapshot.owner !== owner) {{
            continue;
          }}

          visited.add(currentName);
          component.push(currentName);

          for (const neighborName of staticRegionByName[currentName]?.neighbors || []) {{
            if (!visited.has(neighborName) && snapshot.regions[neighborName]?.owner === owner) {{
              stack.push(neighborName);
            }}
          }}
        }}

        const atlasComponent = component
          .map((regionName) => atlasRegionByName[regionName])
          .filter(Boolean);

        if (!atlasComponent.length) {{
          continue;
        }}

        const centroidX = atlasComponent.reduce((total, item) => total + item.label_x, 0) / atlasComponent.length;
        const centroidY = atlasComponent.reduce((total, item) => total + item.label_y, 0) / atlasComponent.length;
        const displayName = getFactionDisplayName(owner);
        clusters.push({{
          owner,
          regionCount: component.length,
          x: centroidX,
          y: centroidY,
          lines: splitPolityLabel(displayName),
        }});
      }}

      return resolvePolityLabelOverlap(clusters);
    }}

    function renderAtlasPolityLabels(snapshot) {{
      if (!data.atlas_regions.length) {{
        return;
      }}

      atlasPolityLabelLayer.replaceChildren();

      for (const cluster of getAtlasPolityLabelData(snapshot)) {{
        const group = svgElement("g", {{}});
        const mainLabelClass = cluster.regionCount >= 4
          ? "atlas-polity-label large"
          : (cluster.regionCount === 1 ? "atlas-polity-label small" : "atlas-polity-label");
        const firstLineY = cluster.lines.length > 1 ? cluster.y - 8 : cluster.y;

        cluster.lines.forEach((line, index) => {{
          const text = svgElement("text", {{
            x: cluster.x.toFixed(1),
            y: (firstLineY + (index * 18)).toFixed(1),
            class: mainLabelClass,
          }});
          text.textContent = line;
          group.appendChild(text);
        }});

        if (cluster.regionCount > 1) {{
          const subLabel = svgElement("text", {{
            x: cluster.x.toFixed(1),
            y: (cluster.lines.length > 1 ? firstLineY + 34 : cluster.y + 18).toFixed(1),
            class: "atlas-polity-label-sub",
          }});
          subLabel.textContent = `${{cluster.regionCount}} regions`;
          group.appendChild(subLabel);
        }}

        const title = svgElement("title", {{}});
        title.textContent = `${{getFactionDisplayName(cluster.owner)}} controls ${{cluster.regionCount}} connected region${{cluster.regionCount === 1 ? "" : "s"}}.`;
        group.appendChild(title);
        atlasPolityLabelLayer.appendChild(group);
      }}
    }}

    function appendAtlasTerrainSymbol(group, tag, centerX, centerY, size) {{
      if (tag === "forest") {{
        for (const offset of [-size * 0.62, 0, size * 0.62]) {{
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset).toFixed(1)}} ${{(centerY + (size * 0.72)).toFixed(1)}} L ${{(centerX + offset).toFixed(1)}} ${{(centerY - (size * 0.2)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset - (size * 0.18)).toFixed(1)}} ${{(centerY - (size * 0.62)).toFixed(1)}} L ${{(centerX + offset - (size * 0.42)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} L ${{(centerX + offset + (size * 0.08)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} Z`,
            class: "atlas-symbol vegetation soft-fill",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset + (size * 0.12)).toFixed(1)}} ${{(centerY - (size * 0.68)).toFixed(1)}} L ${{(centerX + offset - (size * 0.22)).toFixed(1)}} ${{(centerY - (size * 0.1)).toFixed(1)}} L ${{(centerX + offset + (size * 0.42)).toFixed(1)}} ${{(centerY - (size * 0.08)).toFixed(1)}} Z`,
            class: "atlas-symbol vegetation soft-fill",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset - (size * 0.46)).toFixed(1)}} ${{(centerY + (size * 0.1)).toFixed(1)}} Q ${{(centerX + offset - (size * 0.12)).toFixed(1)}} ${{(centerY - (size * 0.52)).toFixed(1)}} ${{(centerX + offset + (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.08)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offset - (size * 0.36)).toFixed(1)}} ${{(centerY + (size * 0.28)).toFixed(1)}} Q ${{(centerX + offset).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} ${{(centerX + offset + (size * 0.38)).toFixed(1)}} ${{(centerY + (size * 0.26)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
        }}
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.95)).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}} Q ${{centerX.toFixed(1)}} ${{(centerY + (size * 0.9)).toFixed(1)}} ${{(centerX + (size * 0.95)).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}}`,
          class: "atlas-symbol vegetation",
        }}));
        return;
      }}

      if (tag === "highland") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.55)).toFixed(1)}} L ${{(centerX - (size * 0.32)).toFixed(1)}} ${{(centerY - (size * 0.5)).toFixed(1)}} L ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}} L ${{(centerX + (size * 0.62)).toFixed(1)}} ${{(centerY - (size * 0.38)).toFixed(1)}} L ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.48)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.3)).toFixed(1)}} ${{(centerY + (size * 0.15)).toFixed(1)}} L ${{(centerX - (size * 0.12)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.72)).toFixed(1)}} ${{(centerY + (size * 0.46)).toFixed(1)}} L ${{(centerX - (size * 0.46)).toFixed(1)}} ${{(centerY - (size * 0.12)).toFixed(1)}} L ${{(centerX - (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}} L ${{(centerX + (size * 0.34)).toFixed(1)}} ${{(centerY - (size * 0.16)).toFixed(1)}} L ${{(centerX + (size * 0.7)).toFixed(1)}} ${{(centerY + (size * 0.38)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        return;
      }}

      if (tag === "riverland") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} C ${{(centerX - (size * 0.58)).toFixed(1)}} ${{(centerY - (size * 0.82)).toFixed(1)}}, ${{(centerX - (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}, ${{centerX.toFixed(1)}} ${{centerY.toFixed(1)}} C ${{(centerX + (size * 0.2)).toFixed(1)}} ${{(centerY - (size * 0.42)).toFixed(1)}}, ${{(centerX + (size * 0.56)).toFixed(1)}} ${{(centerY + (size * 0.82)).toFixed(1)}}, ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.68)).toFixed(1)}} ${{(centerY + (size * 0.22)).toFixed(1)}} C ${{(centerX - (size * 0.3)).toFixed(1)}} ${{(centerY + (size * 0.04)).toFixed(1)}}, ${{(centerX - (size * 0.12)).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}}, ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        return;
      }}

      if (tag === "coast") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY - (size * 0.12)).toFixed(1)}} C ${{(centerX - (size * 0.55)).toFixed(1)}} ${{(centerY - (size * 0.72)).toFixed(1)}}, ${{(centerX + (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.08)).toFixed(1)}}, ${{(centerX + size).toFixed(1)}} ${{(centerY - (size * 0.3)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.74)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}} Q ${{(centerX - (size * 0.28)).toFixed(1)}} ${{(centerY + (size * 0.06)).toFixed(1)}} ${{centerX.toFixed(1)}} ${{(centerY + (size * 0.32)).toFixed(1)}} Q ${{(centerX + (size * 0.28)).toFixed(1)}} ${{(centerY + (size * 0.58)).toFixed(1)}} ${{(centerX + (size * 0.74)).toFixed(1)}} ${{(centerY + (size * 0.28)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        return;
      }}

      if (tag === "marsh") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.62)).toFixed(1)}} Q ${{(centerX - (size * 0.55)).toFixed(1)}} ${{(centerY + (size * 0.22)).toFixed(1)}} ${{(centerX - (size * 0.12)).toFixed(1)}} ${{(centerY + (size * 0.48)).toFixed(1)}} T ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.44)).toFixed(1)}}`,
          class: "atlas-symbol water",
        }}));
        for (const offsetX of [-size * 0.48, 0, size * 0.48]) {{
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offsetX).toFixed(1)}} ${{(centerY + (size * 0.72)).toFixed(1)}} Q ${{(centerX + offsetX - (size * 0.08)).toFixed(1)}} ${{centerY.toFixed(1)}} ${{(centerX + offsetX).toFixed(1)}} ${{(centerY - (size * 0.46)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
        }}
        return;
      }}

      if (tag === "hills") {{
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.5)).toFixed(1)}} Q ${{(centerX - (size * 0.58)).toFixed(1)}} ${{(centerY - (size * 0.18)).toFixed(1)}} ${{(centerX - (size * 0.16)).toFixed(1)}} ${{(centerY + (size * 0.22)).toFixed(1)}} Q ${{(centerX + (size * 0.16)).toFixed(1)}} ${{(centerY - (size * 0.22)).toFixed(1)}} ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.72)).toFixed(1)}} ${{(centerY + (size * 0.2)).toFixed(1)}} Q ${{centerX.toFixed(1)}} ${{(centerY - (size * 0.46)).toFixed(1)}} ${{(centerX + (size * 0.72)).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX - (size * 0.92)).toFixed(1)}} ${{(centerY + (size * 0.58)).toFixed(1)}} Q ${{(centerX - (size * 0.54)).toFixed(1)}} ${{(centerY + (size * 0.1)).toFixed(1)}} ${{(centerX - (size * 0.2)).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        group.appendChild(svgElement("path", {{
          d: `M ${{(centerX + (size * 0.08)).toFixed(1)}} ${{(centerY + (size * 0.34)).toFixed(1)}} Q ${{(centerX + (size * 0.42)).toFixed(1)}} ${{(centerY - (size * 0.12)).toFixed(1)}} ${{(centerX + (size * 0.92)).toFixed(1)}} ${{(centerY + (size * 0.52)).toFixed(1)}}`,
          class: "atlas-symbol earth",
        }}));
        return;
      }}

      if (tag === "steppe") {{
        for (const offsetX of [-size * 0.55, 0, size * 0.55]) {{
          group.appendChild(svgElement("path", {{
            d: `M ${{(centerX + offsetX).toFixed(1)}} ${{(centerY + (size * 0.72)).toFixed(1)}} Q ${{(centerX + offsetX - (size * 0.18)).toFixed(1)}} ${{(centerY + (size * 0.18)).toFixed(1)}} ${{(centerX + offsetX).toFixed(1)}} ${{(centerY - (size * 0.36)).toFixed(1)}} Q ${{(centerX + offsetX + (size * 0.22)).toFixed(1)}} ${{(centerY + (size * 0.06)).toFixed(1)}} ${{(centerX + offsetX).toFixed(1)}} ${{(centerY + (size * 0.64)).toFixed(1)}}`,
            class: "atlas-symbol vegetation",
          }}));
        }}
        return;
      }}

      group.appendChild(svgElement("path", {{
        d: `M ${{(centerX - size).toFixed(1)}} ${{(centerY + (size * 0.42)).toFixed(1)}} Q ${{(centerX - (size * 0.45)).toFixed(1)}} ${{(centerY + (size * 0.1)).toFixed(1)}} ${{centerX.toFixed(1)}} ${{(centerY + (size * 0.26)).toFixed(1)}} Q ${{(centerX + (size * 0.45)).toFixed(1)}} ${{(centerY - (size * 0.04)).toFixed(1)}} ${{(centerX + size).toFixed(1)}} ${{(centerY + (size * 0.24)).toFixed(1)}}`,
        class: "atlas-symbol earth",
      }}));
    }}

    function buildStaticMap() {{
      function attachTitle(element, id) {{
        const title = svgElement("title", {{ id }});
        element.appendChild(title);
      }}

      if (data.atlas_regions.length) {{
        atlasBackgroundLayer.appendChild(svgElement("rect", {{
          x: 0,
          y: 0,
          width: 900,
          height: 900,
          class: "atlas-water",
        }}));

        atlasBackgroundLayer.appendChild(svgElement("polygon", {{
          points: polygonPointsText(data.atlas_coastline),
          class: "atlas-landmass",
        }}));

        for (const scale of [0.88, 0.76]) {{
          const reliefPoints = data.atlas_coastline.map((point) => {{
            const dx = point[0] - 450;
            const dy = point[1] - 450;
            return [450 + (dx * scale), 450 + (dy * scale)];
          }});
          atlasBackgroundLayer.appendChild(svgElement("polygon", {{
            points: polygonPointsText(reliefPoints),
            class: "atlas-relief",
          }}));
        }}

        for (const region of data.atlas_regions) {{
          const polygon = svgElement("polygon", {{
            points: polygonPointsText(region.polygon),
            class: "atlas-territory",
            id: `atlas-region-${{region.name}}`,
          }});
          attachTitle(polygon, `atlas-title-${{region.name}}`);
          polygon.addEventListener("mouseenter", () => {{
            state.focusRegionName = region.name;
            renderRegionDetail(data.snapshots[state.currentTurn]);
          }});
          atlasLayer.appendChild(polygon);

          const terrainTags = getDisplayTerrainTags(region.terrain_tags);
          const symbolOffsets = getAtlasSymbolOffsets(terrainTags.length);
          const terrainGroup = svgElement("g", {{
            id: `atlas-symbols-${{region.name}}`,
          }});
          symbolOffsets.forEach((offset, index) => {{
            const tag = terrainTags[index % terrainTags.length];
            const [offsetX, offsetY] = offset;
            appendAtlasTerrainSymbol(
              terrainGroup,
              tag,
              region.label_x + offsetX,
              region.label_y + offsetY,
              8,
            );
          }});
          atlasSymbolLayer.appendChild(terrainGroup);

          atlasLabelLayer.appendChild(svgElement("text", {{
            x: region.label_x,
            y: region.label_y - 8,
            "text-anchor": "middle",
            class: "region-label",
            id: `atlas-label-${{region.name}}`,
          }}));

          atlasLabelLayer.appendChild(svgElement("text", {{
            x: region.label_x,
            y: region.label_y + 13,
            "text-anchor": "middle",
            class: "region-resource",
            id: `atlas-resource-${{region.name}}`,
          }}));

          atlasTerrainLayer.appendChild(svgElement("text", {{
            x: region.label_x,
            y: region.label_y + 28,
            "text-anchor": "middle",
            class: "terrain-overlay",
            id: `atlas-terrain-${{region.name}}`,
          }}));
        }}
      }}

      for (const [first, second] of data.edges) {{
        const firstRegion = data.regions.find((region) => region.name === first);
        const secondRegion = data.regions.find((region) => region.name === second);
        edgeLayer.appendChild(svgElement("line", {{
          x1: firstRegion.x,
          y1: firstRegion.y,
          x2: secondRegion.x,
          y2: secondRegion.y,
          class: "edge",
        }}));
      }}

      for (const region of data.regions) {{
        const node = svgElement("circle", {{
          cx: region.x,
          cy: region.y,
          r: 25,
          class: "region-node",
          id: `region-node-${{region.name}}`,
        }});
        attachTitle(node, `region-title-${{region.name}}`);
        node.addEventListener("mouseenter", () => {{
          state.focusRegionName = region.name;
          renderRegionDetail(data.snapshots[state.currentTurn]);
        }});
        regionLayer.appendChild(node);

        labelLayer.appendChild(svgElement("text", {{
          x: region.x,
          y: region.y - 8,
          "text-anchor": "middle",
          class: "region-label",
          id: `region-label-${{region.name}}`,
        }}));

        labelLayer.appendChild(svgElement("text", {{
          x: region.x,
          y: region.y + 13,
          "text-anchor": "middle",
          class: "region-resource",
          id: `region-resource-${{region.name}}`,
        }}));

        terrainLayer.appendChild(svgElement("text", {{
          x: region.x,
          y: region.y + 28,
          "text-anchor": "middle",
          class: "terrain-overlay",
          id: `region-terrain-${{region.name}}`,
        }}));
      }}
    }}

    function renderViewToggle() {{
      const overlayLabel = state.showTerrainOverlay ? "Terrain Labels On" : "Terrain Labels";
      const colorModeLabel = `Colors: ${{getColorModeLabel()}}`;
      const atlasLabelModeLabel = `Labels: ${{state.atlasLabelMode === "realms" ? "Realms" : "Regions"}}`;
      terrainToggle.innerHTML = `
        <button type="button" class="secondary" data-terrain="overlay">${{overlayLabel}}</button>
        <button type="button" class="secondary" data-terrain="mode">${{colorModeLabel}}</button>
        ${{data.atlas_regions.length ? `<button type="button" class="secondary" data-terrain="labels">${{atlasLabelModeLabel}}</button>` : ""}}
      `;

      if (!data.atlas_regions.length) {{
        graphLayer.classList.remove("hidden");
        atlasLayer.classList.add("hidden");
        atlasLabelLayer.classList.add("hidden");
        for (const button of terrainToggle.querySelectorAll("[data-terrain]")) {{
          const isActive = (
            (button.dataset.terrain === "overlay" && state.showTerrainOverlay)
            || (button.dataset.terrain === "mode" && state.colorMode !== "ownership")
            || (button.dataset.terrain === "labels" && state.atlasLabelMode !== "regions")
          );
          button.classList.toggle("active", isActive);
          button.addEventListener("click", () => {{
            if (button.dataset.terrain === "overlay") {{
              state.showTerrainOverlay = !state.showTerrainOverlay;
            }} else if (button.dataset.terrain === "mode") {{
              cycleColorMode();
            }} else if (button.dataset.terrain === "labels") {{
              state.atlasLabelMode = state.atlasLabelMode === "regions" ? "realms" : "regions";
            }}
            renderViewToggle();
            renderLegend();
            renderTurn(state.currentTurn);
          }});
        }}
        syncMapView();
        return;
      }}

      viewToggle.innerHTML = `
        <button type="button" class="secondary" data-view="atlas">Atlas View</button>
        <button type="button" class="secondary" data-view="graph">Graph View</button>
      `;

      for (const button of viewToggle.querySelectorAll("[data-view]")) {{
        button.classList.toggle("active", button.dataset.view === state.mapView);
        button.addEventListener("click", () => {{
          state.mapView = button.dataset.view;
          renderViewToggle();
          renderTurn(state.currentTurn);
        }});
      }}

      for (const button of terrainToggle.querySelectorAll("[data-terrain]")) {{
        const isActive = (
          (button.dataset.terrain === "overlay" && state.showTerrainOverlay)
          || (button.dataset.terrain === "mode" && state.colorMode !== "ownership")
          || (button.dataset.terrain === "labels" && state.atlasLabelMode !== "regions")
        );
        button.classList.toggle("active", isActive);
        button.addEventListener("click", () => {{
          if (button.dataset.terrain === "overlay") {{
            state.showTerrainOverlay = !state.showTerrainOverlay;
          }} else if (button.dataset.terrain === "mode") {{
            cycleColorMode();
          }} else if (button.dataset.terrain === "labels") {{
            state.atlasLabelMode = state.atlasLabelMode === "regions" ? "realms" : "regions";
          }}
          renderViewToggle();
          renderLegend();
          renderTurn(state.currentTurn);
        }});
      }}

      syncMapView();
    }}

    function syncMapView() {{
      const showAtlas = state.mapView === "atlas" && data.atlas_regions.length;
      atlasBackgroundLayer.classList.toggle("hidden", !showAtlas);
      atlasLayer.classList.toggle("hidden", !showAtlas);
      atlasSymbolLayer.classList.toggle("hidden", !showAtlas);
      atlasLabelLayer.classList.toggle("hidden", !showAtlas || state.atlasLabelMode !== "regions");
      atlasPolityLabelLayer.classList.toggle("hidden", !showAtlas || state.atlasLabelMode !== "realms");
      atlasTerrainLayer.classList.toggle("hidden", !showAtlas || !state.showTerrainOverlay);
      graphLayer.classList.toggle("hidden", showAtlas);
      terrainLayer.classList.toggle("hidden", !state.showTerrainOverlay);

      for (const button of viewToggle.querySelectorAll("[data-view]")) {{
        button.classList.toggle("active", button.dataset.view === state.mapView);
      }}
      for (const button of terrainToggle.querySelectorAll("[data-terrain]")) {{
        const isActive = (
          (button.dataset.terrain === "overlay" && state.showTerrainOverlay)
          || (button.dataset.terrain === "mode" && state.colorMode !== "ownership")
          || (button.dataset.terrain === "labels" && state.atlasLabelMode !== "regions")
        );
        button.classList.toggle("active", isActive);
      }}
    }}

    function renderLegend(snapshot = data.snapshots[state.currentTurn]) {{
      let items;
      if (state.colorMode === "terrain") {{
        const uniqueTerrain = new Map();
        for (const region of data.regions) {{
          const key = region.terrain_label;
          if (!uniqueTerrain.has(key)) {{
            uniqueTerrain.set(key, region.terrain_tags);
          }}
        }}
        items = [...uniqueTerrain.entries()].map(([label, tags]) => `
          <span class="legend-item">
            <span class="swatch" style="background:${{getTerrainColor(tags)}}"></span>
            Terrain: ${{escapeHtml(label)}}
          </span>
        `);
      }} else if (state.colorMode === "climate") {{
        const uniqueClimates = new Map();
        for (const region of data.regions) {{
          if (!uniqueClimates.has(region.climate)) {{
            uniqueClimates.set(region.climate, region.climate_label);
          }}
        }}
        items = [...uniqueClimates.entries()].map(([climate, label]) => `
          <span class="legend-item">
            <span class="swatch" style="background:${{getClimateColor(climate)}}"></span>
            Climate: ${{escapeHtml(label)}}
          </span>
        `);
      }} else if (state.colorMode === "unrest") {{
        const unrestEntries = [
          ["calm", "Calm"],
          ["watch", "Watch"],
          ["disturbance", "Disturbance"],
          ["crisis", "Crisis"],
          ["secession", "Seceded / Neutral"],
        ];
        items = unrestEntries.map(([tier, label]) => `
          <span class="legend-item">
            <span class="swatch" style="background:${{unrestColors[tier]}}"></span>
            Unrest: ${{escapeHtml(label)}}
          </span>
        `);
      }} else {{
        const ownedFactions = new Set(
          Object.values(snapshot?.regions || {{}})
            .map((region) => region.owner)
            .filter(Boolean),
        );
        const hasUnclaimedRegions = Object.values(snapshot?.regions || {{}})
          .some((region) => !region.owner);
        items = [
          ...data.factions
            .filter((faction) => ownedFactions.has(faction.name))
            .map((faction) => `<span class="legend-item"><span class="swatch" style="background:${{faction.color}}"></span>${{escapeHtml(faction.display_name || faction.name)}} <span class="subtle">${{escapeHtml(faction.doctrine_label)}}</span></span>`),
        ];
        if (hasUnclaimedRegions) {{
          items.push(`<span class="legend-item"><span class="swatch" style="background:${{unclaimedColor}}"></span>Unclaimed</span>`);
        }}
      }}
      legend.innerHTML = items.join("");
    }}

    function renderTerrainLegend() {{
      const uniqueTerrain = new Map();
      for (const region of data.regions) {{
        const key = region.terrain_label;
        if (!uniqueTerrain.has(key)) {{
          uniqueTerrain.set(key, region.terrain_tags);
        }}
      }}

      terrainLegend.innerHTML = [...uniqueTerrain.entries()].map(([label, tags]) => `
        <span class="legend-item">
          <span class="terrain-chip" style="background:${{getTerrainColor(tags)}}"></span>
          ${{escapeHtml(label)}}
        </span>
      `).join("");
    }}

    function renderRunSummary() {{
      const strategic = data.narrative_summary.strategic || [];
      const victor = data.narrative_summary.victor || [];
      const finalLines = data.narrative_summary.final || [];

      runSummary.innerHTML = `
        <article class="summary-card">
          <strong>Phase Arc</strong>
          <ul class="summary-list">
            ${{data.phase_summaries.map((phase) => `<li><strong>${{escapeHtml(phase.name)}}:</strong> ${{escapeHtml(phase.summary)}}</li>`).join("")}}
          </ul>
        </article>
        <article class="summary-card">
          <strong>Strategic Read</strong>
          <p class="summary-copy">${{escapeHtml(strategic[0] || "No strategic interpretation available.")}}</p>
        </article>
        <article class="summary-card">
          <strong>Winner's Story</strong>
          <p class="summary-copy">${{escapeHtml(victor[0] || "No victor summary available.")}}</p>
        </article>
        <article class="summary-card">
          <strong>Final Order</strong>
          <ul class="summary-list">
            ${{finalLines.map((line) => `<li>${{escapeHtml(line)}}</li>`).join("")}}
          </ul>
        </article>
      `;
    }}

    function buildDoctrineTimelineControls() {{
      doctrineTimelineControls.innerHTML = data.factions.map((faction) => `
        <button type="button" class="secondary${{faction.name === state.focusFactionName ? " active" : ""}}" data-faction="${{escapeHtml(faction.name)}}">
          ${{escapeHtml(faction.display_name || faction.name)}}
        </button>
      `).join("");

      for (const button of doctrineTimelineControls.querySelectorAll("[data-faction]")) {{
        button.addEventListener("click", () => {{
          state.focusFactionName = button.dataset.faction;
          buildDoctrineTimelineControls();
          renderDoctrineTimeline();
        }});
      }}
    }}

    function renderDoctrineTimeline() {{
      const factionName = state.focusFactionName || data.factions[0]?.name;
      const faction = getFactionDataByName(factionName);
      if (!faction) {{
        doctrineTimeline.innerHTML = "";
        doctrineTimelineKey.innerHTML = "";
        doctrineTimelineCaption.textContent = "No faction selected.";
        return;
      }}

      const history = data.snapshots
        .filter((snapshot) => snapshot.turn > 0 && snapshot.metrics && snapshot.metrics.factions[factionName])
        .map((snapshot) => ({{
          turn: snapshot.turn,
          ...snapshot.metrics.factions[factionName],
        }}));

      if (!history.length) {{
        doctrineTimeline.innerHTML = "";
        doctrineTimelineKey.innerHTML = "";
        doctrineTimelineCaption.textContent = `${{factionName}} has no doctrine history yet.`;
        return;
      }}

      const width = 920;
      const height = 320;
      const margin = {{ top: 24, right: 22, bottom: 42, left: 54 }};
      const innerWidth = width - margin.left - margin.right;
      const innerHeight = height - margin.top - margin.bottom;
      const maxTurn = Math.max(...history.map((entry) => entry.turn));
      const xForTurn = (turn) => margin.left + (((turn - 1) / Math.max(1, maxTurn - 1)) * innerWidth);
      const yForValue = (value) => margin.top + ((1 - value) * innerHeight);
      const postureKeys = ["expansion_posture", "war_posture", "development_posture", "insularity"];
      const postureLabels = {{
        expansion_posture: "Expansion",
        war_posture: "War",
        development_posture: "Development",
        insularity: "Insularity",
      }};
      const horizontalTicks = [0, 0.25, 0.5, 0.75, 1];
      const verticalTicks = history.map((entry) => entry.turn);
      const shiftPoints = history.filter((entry, index) => index > 0 && history[index - 1].doctrine_label !== entry.doctrine_label);
      const makePath = (key) => history.map((entry, index) => {{
        const x = xForTurn(entry.turn).toFixed(1);
        const y = yForValue(entry[key]).toFixed(1);
        return `${{index === 0 ? "M" : "L"}}${{x}},${{y}}`;
      }}).join(" ");

      doctrineTimeline.innerHTML = `
        <rect x="0" y="0" width="${{width}}" height="${{height}}" rx="16" fill="rgba(255,255,255,0.72)"></rect>
        ${{horizontalTicks.map((tick) => `
          <g>
            <line x1="${{margin.left}}" y1="${{yForValue(tick).toFixed(1)}}" x2="${{(width - margin.right).toFixed(1)}}" y2="${{yForValue(tick).toFixed(1)}}" class="timeline-grid"></line>
            <text x="${{(margin.left - 12).toFixed(1)}}" y="${{(yForValue(tick) + 4).toFixed(1)}}" text-anchor="end" class="timeline-label">${{tick.toFixed(2)}}</text>
          </g>
        `).join("")}}
        ${{verticalTicks.map((tick) => `
          <g>
            <line x1="${{xForTurn(tick).toFixed(1)}}" y1="${{margin.top}}" x2="${{xForTurn(tick).toFixed(1)}}" y2="${{(height - margin.bottom).toFixed(1)}}" class="timeline-grid"></line>
            <text x="${{xForTurn(tick).toFixed(1)}}" y="${{(height - 16).toFixed(1)}}" text-anchor="middle" class="timeline-label">T${{tick}}</text>
          </g>
        `).join("")}}
        <line x1="${{margin.left}}" y1="${{(height - margin.bottom).toFixed(1)}}" x2="${{(width - margin.right).toFixed(1)}}" y2="${{(height - margin.bottom).toFixed(1)}}" class="timeline-axis"></line>
        <line x1="${{margin.left}}" y1="${{margin.top}}" x2="${{margin.left}}" y2="${{(height - margin.bottom).toFixed(1)}}" class="timeline-axis"></line>
        ${{postureKeys.map((key) => `
          <path d="${{makePath(key)}}" class="timeline-line" stroke="${{doctrineLineColors[key]}}"></path>
          ${{history.map((entry) => `
            <circle cx="${{xForTurn(entry.turn).toFixed(1)}}" cy="${{yForValue(entry[key]).toFixed(1)}}" r="4.5" class="timeline-dot" fill="${{doctrineLineColors[key]}}">
              <title>${{escapeHtml(factionName)}} | Turn ${{entry.turn}} | ${{escapeHtml(postureLabels[key])}}: ${{entry[key].toFixed(2)}} | Doctrine: ${{escapeHtml(entry.doctrine_label)}}</title>
            </circle>
          `).join("")}}
        `).join("")}}
        ${{shiftPoints.map((entry) => `
          <g>
            <circle cx="${{xForTurn(entry.turn).toFixed(1)}}" cy="${{(margin.top - 8).toFixed(1)}}" r="6" class="timeline-shift">
              <title>${{escapeHtml(factionName)}} | Turn ${{entry.turn}} | Doctrine shift to ${{escapeHtml(entry.doctrine_label)}}</title>
            </circle>
          </g>
        `).join("")}}
      `;

      doctrineTimelineKey.innerHTML = postureKeys.map((key) => `
        <span class="timeline-key-item">
          <span class="timeline-line-chip" style="background:${{doctrineLineColors[key]}}"></span>
          ${{escapeHtml(postureLabels[key])}}
        </span>
      `).join("");

      const openingDoctrine = history[0].doctrine_label;
      const closingDoctrine = history[history.length - 1].doctrine_label;
      const shiftCount = shiftPoints.length;
      doctrineTimelineCaption.textContent = `${{factionName}} began this run as ${{openingDoctrine}}, ended as ${{closingDoctrine}}, and shifted doctrine ${{shiftCount}} time${{shiftCount === 1 ? "" : "s"}} while its posture scores evolved across the simulation.`;
    }}

    function syncRunSummaryVisibility(turn) {{
      runSummaryPanel.classList.toggle("panel-hidden", turn < data.turns);
    }}

    function renderTurnContext(turn, snapshot) {{
      const eventCount = snapshot.events.length;
      const contestedCount = snapshot.contested_regions.length;
      const changedCount = snapshot.changed_regions.length;
      const unstableCount = Object.values(snapshot.regions).filter((region) =>
        Number(region.unrest || 0) >= 4 || ((region.unrest_event_level || "none") !== "none")
      ).length;
      const leader = snapshot.standings[0];
      const leaderText = leader
        ? `${{getFactionDisplayName(leader.faction)}} leads on $${{leader.treasury}} with ${{leader.owned_regions}} region${{leader.owned_regions === 1 ? "" : "s"}}.`
        : "No leader yet.";
      const contextText = turn === 0
        ? "Initial setup before any faction has acted."
        : leaderText;

      turnContext.innerHTML = `
        <div class="card-header">
          <strong>${{turn === 0 ? "Initial State" : `Turn ${{turn}} Snapshot`}}</strong>
          <span class="pill">Palette: ${{escapeHtml(getColorModeLabel())}}</span>
        </div>
        <p class="summary-copy">${{escapeHtml(contextText)}}</p>
        <div class="stat-grid">
          <div class="stat-chip">
            <div class="stat-label">Events</div>
            <div class="stat-value">${{eventCount}}</div>
          </div>
          <div class="stat-chip">
            <div class="stat-label">Changed Regions</div>
            <div class="stat-value">${{changedCount}}</div>
          </div>
          <div class="stat-chip">
            <div class="stat-label">Contested</div>
            <div class="stat-value">${{contestedCount}}</div>
          </div>
          <div class="stat-chip">
            <div class="stat-label">Unstable</div>
            <div class="stat-value">${{unstableCount}}</div>
          </div>
          <div class="stat-chip">
            <div class="stat-label">Leading Faction</div>
            <div class="stat-value">${{escapeHtml(leader ? getFactionDisplayName(leader.faction) : "None")}}</div>
          </div>
          <div class="stat-chip">
            <div class="stat-label">Leading Treasury</div>
            <div class="stat-value">${{leader ? `$${{leader.treasury}}` : "-"}}</div>
          </div>
        </div>
      `;
    }}

    function renderRegionDetail(snapshot) {{
      const regionName = state.focusRegionName || snapshot.changed_regions[0] || data.regions[0]?.name;
      if (!regionName) {{
        regionDetail.innerHTML = `<strong>No Region Selected</strong><p class="summary-copy">Hover a region on the map to inspect its terrain and current status.</p>`;
        return;
      }}

      const staticRegion = getRegionDataByName(regionName);
      const regionSnapshot = snapshot.regions[regionName];
      if (!staticRegion || !regionSnapshot) {{
        regionDetail.innerHTML = `<strong>No Region Selected</strong><p class="summary-copy">Hover a region on the map to inspect its terrain and current status.</p>`;
        return;
      }}

      const ownerText = getFactionDisplayName(regionSnapshot.owner);
      const ownerColor = colorByFaction[regionSnapshot.owner] || unclaimedColor;
      const foundingText = regionSnapshot.founding_name
        ? `${{escapeHtml(regionSnapshot.founding_name)}}${{regionSnapshot.founding_name !== regionName ? ` <span class="subtle">(${{
          escapeHtml(regionName)
        }})</span>` : ""}}`
        : escapeHtml(regionName);
      const claimants = regionSnapshot.ethnic_claimants || staticRegion.ethnic_claimants || [];
      const claimsText = claimants.length
        ? claimants.map((factionName) => escapeHtml(getFactionDisplayName(factionName))).join(", ")
        : "None";
      const agitators = regionSnapshot.external_regime_agitators || staticRegion.external_regime_agitators || [];
      const agitationPressure = Number(regionSnapshot.external_regime_agitation ?? staticRegion.external_regime_agitation ?? 0);
      const agitationText = (!agitators.length || agitationPressure <= 0)
        ? "None"
        : `${{agitators.map((factionName) => escapeHtml(getFactionDisplayName(factionName))).join(", ")}} (${{agitationPressure.toFixed(3)}})`;

      regionDetail.innerHTML = `
        <div class="card-header">
          <div>
            <strong>${{escapeHtml(regionSnapshot.display_name || staticRegion.display_name || regionName)}}</strong>
            <p class="panel-note">${{escapeHtml(regionSnapshot.terrain_label || staticRegion.terrain_label || "Plains")}} terrain, ${{escapeHtml(regionSnapshot.climate_label || staticRegion.climate_label || "Temperate")}} climate.</p>
          </div>
          <span class="pill" style="background:${{ownerColor}}22; color:${{ownerColor}};">${{escapeHtml(ownerText)}}</span>
        </div>
        <div class="detail-section">
          <div class="detail-section-title">Identity</div>
          <div class="detail-grid detail-grid-two">
            <div class="detail-row">
              <div class="detail-label">Region Code</div>
              <div class="detail-value">${{escapeHtml(regionName)}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Homeland Of</div>
              <div class="detail-value">${{escapeHtml(regionSnapshot.homeland_faction_id || "None")}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Owner</div>
              <div class="detail-value">${{escapeHtml(ownerText)}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Founding Name</div>
              <div class="detail-value">${{foundingText}}</div>
            </div>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-section-title">Land And People</div>
          <div class="detail-grid detail-grid-two">
            <div class="detail-row">
              <div class="detail-label">Terrain</div>
              <div class="detail-value">
                <span class="terrain-chip" style="background:${{getTerrainColor(regionSnapshot.terrain_tags || staticRegion.terrain_tags)}}; display:inline-block; margin-right:8px; vertical-align:middle;"></span>
                ${{escapeHtml(regionSnapshot.terrain_label || staticRegion.terrain_label)}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Climate</div>
              <div class="detail-value">
                <span class="terrain-chip" style="background:${{getClimateColor(regionSnapshot.climate || staticRegion.climate)}}; display:inline-block; margin-right:8px; vertical-align:middle;"></span>
                ${{escapeHtml(regionSnapshot.climate_label || staticRegion.climate_label || "Temperate")}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Settlement</div>
              <div class="detail-value">${{escapeHtml(regionSnapshot.settlement_level || staticRegion.settlement_level || "wild")}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Dominant Ethnicity</div>
              <div class="detail-value">${{escapeHtml(regionSnapshot.dominant_ethnicity || staticRegion.dominant_ethnicity || "None")}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Ruling Affinity</div>
              <div class="detail-value">
                ${{Number((regionSnapshot.ruling_ethnic_affinity ?? staticRegion.ruling_ethnic_affinity ?? 0) * 100).toFixed(0)}}%
                ${{(regionSnapshot.owner_primary_ethnicity || staticRegion.owner_primary_ethnicity) ? ` (${{
                  escapeHtml(regionSnapshot.owner_primary_ethnicity || staticRegion.owner_primary_ethnicity)
                }})` : ""}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Ethnic Claims</div>
              <div class="detail-value">${{claimsText}}</div>
            </div>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-section-title">Economy And Stability</div>
          <div class="detail-grid detail-grid-two">
            <div class="detail-row">
              <div class="detail-label">Taxable / Legacy</div>
              <div class="detail-value">
                ${{Number(regionSnapshot.taxable_value ?? staticRegion.taxable_value ?? 0).toFixed(2)}}
                / R${{regionSnapshot.resources}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Resource Base</div>
              <div class="detail-value">${{escapeHtml(regionSnapshot.resource_profile || staticRegion.resource_profile || "None")}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Population</div>
              <div class="detail-value">${{Number(regionSnapshot.population || staticRegion.population || 0).toLocaleString()}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Surplus</div>
              <div class="detail-value">
                ${{Number(regionSnapshot.surplus ?? staticRegion.surplus ?? 0).toFixed(2)}}
                (${{escapeHtml(regionSnapshot.surplus_label || staticRegion.surplus_label || "stable")}})
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Capacity / Pressure</div>
              <div class="detail-value">
                ${{Number(regionSnapshot.productive_capacity ?? staticRegion.productive_capacity ?? 0).toFixed(2)}}
                / ${{Number(regionSnapshot.population_pressure ?? staticRegion.population_pressure ?? 0).toFixed(2)}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Output / Taxable</div>
              <div class="detail-value">
                ${{escapeHtml(regionSnapshot.resource_output_summary || staticRegion.resource_output_summary || "None")}}
                / ${{Number(regionSnapshot.taxable_value ?? staticRegion.taxable_value ?? 0).toFixed(2)}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Route / Isolation</div>
              <div class="detail-value">
                ${{(regionSnapshot.resource_route_anchor || staticRegion.resource_route_anchor) ? `${{escapeHtml(regionSnapshot.resource_route_anchor || staticRegion.resource_route_anchor)}} @ depth ${{Number(regionSnapshot.resource_route_depth ?? staticRegion.resource_route_depth ?? 0)}} / ` : ""}}
                ${{Number((regionSnapshot.resource_isolation_factor ?? staticRegion.resource_isolation_factor ?? 0) * 100).toFixed(0)}}%
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Cost / Bottleneck</div>
              <div class="detail-value">
                ${{Number(regionSnapshot.resource_route_cost ?? staticRegion.resource_route_cost ?? 0).toFixed(2)}}
                / ${{Number((regionSnapshot.resource_route_bottleneck ?? staticRegion.resource_route_bottleneck ?? 0) * 100).toFixed(0)}}%
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Route Damage</div>
              <div class="detail-value">
                ${{escapeHtml(formatResourceDamage(regionSnapshot.resource_damage || staticRegion.resource_damage || {{}}))}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Integration</div>
              <div class="detail-value">${{escapeHtml(regionSnapshot.core_status || "frontier")}} (${{Number(regionSnapshot.integration_score || 0).toFixed(1)}})</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Unrest</div>
              <div class="detail-value">
                <span class="terrain-chip" style="background:${{getUnrestColor(regionSnapshot)}}; display:inline-block; margin-right:8px; vertical-align:middle;"></span>
                ${{escapeHtml(getUnrestLabel(regionSnapshot))}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Unrest Event</div>
              <div class="detail-value">
                ${{escapeHtml(regionSnapshot.unrest_event_level || "none")}}
                ${{Number(regionSnapshot.unrest_event_turns_remaining || 0) > 0 ? ` (${{Number(regionSnapshot.unrest_event_turns_remaining)}} turn${{Number(regionSnapshot.unrest_event_turns_remaining) === 1 ? "" : "s"}} left)` : ""}}
              </div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Regime Agitation</div>
              <div class="detail-value">${{agitationText}}</div>
            </div>
            <div class="detail-row">
              <div class="detail-label">Neighbors</div>
              <div class="detail-value">${{staticRegion.neighbors.length}}</div>
            </div>
          </div>
        </div>
      `;
    }}

    function renderDoctrinePanel(snapshot) {{
      const previousSnapshot = state.currentTurn > 0 ? data.snapshots[state.currentTurn - 1] : null;
      const currentMetrics = snapshot.metrics ? snapshot.metrics.factions : null;
      const previousMetrics = previousSnapshot && previousSnapshot.metrics
        ? previousSnapshot.metrics.factions
        : null;

      doctrinePanel.innerHTML = data.factions.map((faction) => {{
        const metrics = currentMetrics ? currentMetrics[faction.name] : null;
        const previous = previousMetrics ? previousMetrics[faction.name] : null;

        if (!metrics) {{
          return `
            <article class="summary-card">
              <div class="card-header">
                <strong>${{escapeHtml(faction.display_name || faction.name)}}</strong>
                <span class="pill" style="background:${{faction.color}}22; color:${{faction.color}};">Forming</span>
              </div>
              <div class="subtle">${{escapeHtml(faction.homeland_identity)}} homeland</div>
              <p class="summary-copy">Doctrine is still forming from the starting terrain before the first turn resolves.</p>
            </article>
          `;
        }}

        const doctrineShift = previous && previous.doctrine_label !== metrics.doctrine_label
          ? `<div class="event-meta">Shifted from ${{escapeHtml(previous.doctrine_label)}} on the previous turn.</div>`
          : "";
        const polityStatus = faction.is_rebel
          ? (
              (faction.proto_state
                ? (faction.rebel_conflict_type === "civil_war"
                    ? "Proto-state civil-war claimant"
                    : "Proto-state rebellion")
                : (faction.rebel_conflict_type === "civil_war"
                    ? `${{escapeHtml(faction.government_type || "State")}} claimant`
                    : `${{escapeHtml(faction.government_type || "State")}} successor`))
              + (faction.origin_faction ? ` from ${{escapeHtml(getFactionDisplayName(faction.origin_faction))}}` : "")
            )
          : "Established faction";
        const rebelLifecycle = faction.is_rebel
          ? `
              <div class="detail-row">
                <div class="detail-label">Rebel Age</div>
                <div class="detail-value">${{Number(faction.rebel_age || 0)}} turn${{Number(faction.rebel_age || 0) === 1 ? "" : "s"}}</div>
              </div>
              <div class="detail-row">
                <div class="detail-label">Independence</div>
                <div class="detail-value">${{Number(faction.independence_score || 0).toFixed(1)}}</div>
              </div>
            `
          : "";

        return `
          <article class="summary-card">
            <div class="card-header">
              <div>
                <strong>${{escapeHtml(faction.display_name || faction.name)}}</strong>
                <p class="panel-note">${{polityStatus}}</p>
              </div>
              <span class="pill" style="background:${{faction.color}}22; color:${{faction.color}};">${{escapeHtml(metrics.doctrine_label)}}</span>
            </div>
            ${{doctrineShift}}
            <div class="detail-section">
              <div class="detail-section-title">Identity</div>
              <div class="detail-grid detail-grid-two">
                <div class="detail-row">
                  <div class="detail-label">Tier / Government</div>
                  <div class="detail-value">${{escapeHtml(faction.polity_tier || "tribe")}} / ${{escapeHtml(faction.government_form || "council")}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Primary Ethnicity</div>
                  <div class="detail-value">${{escapeHtml(faction.primary_ethnicity || "Unknown")}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Homeland</div>
                  <div class="detail-value">${{escapeHtml(metrics.homeland_identity)}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Terrain Identity</div>
                  <div class="detail-value">${{escapeHtml(metrics.terrain_identity)}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Climate Identity</div>
                  <div class="detail-value">${{escapeHtml(metrics.climate_identity || faction.climate_identity || "Temperate")}}</div>
                </div>
                ${{rebelLifecycle}}
              </div>
            </div>
            <div class="detail-section">
              <div class="detail-section-title">Pressure Map</div>
              <div class="detail-grid detail-grid-two">
                <div class="detail-row">
                  <div class="detail-label">Top Ally</div>
                  <div class="detail-value">${{escapeHtml(metrics.top_ally || "None")}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Top Rival</div>
                  <div class="detail-value">${{escapeHtml(metrics.top_rival || "None")}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Claim Dispute</div>
                  <div class="detail-value">
                    ${{
                      metrics.top_claim_dispute
                        ? `${{escapeHtml(metrics.top_claim_dispute)}} (${{Number(metrics.top_claim_dispute_regions || 0)}} region${{Number(metrics.top_claim_dispute_regions || 0) === 1 ? "" : "s"}})`
                        : "None"
                    }}
                  </div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Tier Tension</div>
                  <div class="detail-value">
                    ${{
                      metrics.top_polity_tension
                        ? `${{escapeHtml(getFactionDisplayName(metrics.top_polity_tension))}} (${{metrics.top_polity_tension_reason === "peer_state_rivalry" ? "peer rival" : "status gap"}})`
                        : "None"
                    }}
                  </div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Regime Tension</div>
                  <div class="detail-value">
                    ${{
                      metrics.top_regime_tension
                        ? `${{escapeHtml(getFactionDisplayName(metrics.top_regime_tension))}} (${{metrics.top_regime_tension_reason === "civil_war_legitimacy" ? "legitimacy struggle" : "regime split"}})`
                        : "None"
                    }}
                  </div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Regime Accord</div>
                  <div class="detail-value">
                    ${{
                      metrics.top_regime_accommodation
                        ? `${{escapeHtml(getFactionDisplayName(metrics.top_regime_accommodation))}} (${{metrics.top_regime_accommodation_reason === "same_people_accord" ? "same-people accord" : (metrics.top_regime_accommodation_reason === "legitimacy_accommodation" ? "negotiated channel" : "diplomatic restraint")}})`
                        : "None"
                    }}
                  </div>
                </div>
              </div>
            </div>
            <div class="detail-section">
              <div class="detail-section-title">Realm</div>
              <div class="detail-grid detail-grid-two">
                <div class="detail-row">
                  <div class="detail-label">Diplomacy</div>
                  <div class="detail-value">A${{metrics.alliance_count || 0}} / T${{metrics.truce_count || 0}} / P${{metrics.pact_count || 0}} / R${{metrics.rival_count || 0}} / C${{metrics.claim_dispute_count || 0}} / G${{metrics.regime_tension_count || 0}} / O${{metrics.regime_accommodation_count || 0}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Realm Structure</div>
                  <div class="detail-value">H${{metrics.homeland_regions}} / C${{metrics.core_regions}} / F${{metrics.frontier_regions}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Population</div>
                  <div class="detail-value">${{Number(metrics.population || 0).toLocaleString()}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Total Surplus</div>
                  <div class="detail-value">${{Number(metrics.total_surplus || 0).toFixed(2)}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Resource Access</div>
                  <div class="detail-value">${{escapeHtml(faction.resource_access_summary || "None")}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Gross Output</div>
                  <div class="detail-value">${{escapeHtml(faction.resource_gross_summary || "None")}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Isolated Output</div>
                  <div class="detail-value">${{escapeHtml(faction.resource_isolated_summary || "None")}}</div>
                </div>
                <div class="detail-row">
                  <div class="detail-label">Shortages</div>
                  <div class="detail-value">${{escapeHtml(faction.resource_shortage_summary || "None")}}</div>
                </div>
              </div>
            </div>
            <div class="detail-section">
              <div class="detail-section-title">Posture</div>
              <div class="stat-grid compact">
                <div class="stat-chip">
                  <div class="stat-label">Expansion</div>
                  <div class="stat-value">${{formatPosture(metrics.expansion_posture)}} (${{metrics.expansion_posture.toFixed(2)}})</div>
                </div>
                <div class="stat-chip">
                  <div class="stat-label">War</div>
                  <div class="stat-value">${{formatPosture(metrics.war_posture)}} (${{metrics.war_posture.toFixed(2)}})</div>
                </div>
                <div class="stat-chip">
                  <div class="stat-label">Development</div>
                  <div class="stat-value">${{formatPosture(metrics.development_posture)}} (${{metrics.development_posture.toFixed(2)}})</div>
                </div>
                <div class="stat-chip">
                  <div class="stat-label">Insularity</div>
                  <div class="stat-value">${{formatPosture(metrics.insularity)}} (${{metrics.insularity.toFixed(2)}})</div>
                </div>
              </div>
            </div>
          </article>
        `;
      }}).join("");
    }}

    function renderStandings(snapshot) {{
      standings.innerHTML = snapshot.standings.map((entry, index) => `
        <article class="standing-item bar">
          <div class="card-header">
            <strong>#${{index + 1}} ${{escapeHtml(getFactionDisplayName(entry.faction))}}</strong>
            <span class="pill" style="background:${{colorByFaction[entry.faction]}}22; color:${{colorByFaction[entry.faction]}};">${{escapeHtml(data.factions.find((faction) => faction.name === entry.faction).doctrine_label)}}</span>
          </div>
          <div class="stat-grid compact">
            <div class="stat-chip">
              <div class="stat-label">Treasury</div>
              <div class="stat-value">$${{entry.treasury}}</div>
            </div>
            <div class="stat-chip">
              <div class="stat-label">Regions</div>
              <div class="stat-value">${{entry.owned_regions}}</div>
            </div>
            <div class="stat-chip">
              <div class="stat-label">Population</div>
              <div class="stat-value">${{Number((snapshot.metrics && snapshot.metrics.factions[entry.faction] && snapshot.metrics.factions[entry.faction].population) || 0).toLocaleString()}}</div>
            </div>
          </div>
        </article>
      `).join("");
    }}

    function renderTurnEvents(snapshot) {{
        if (!snapshot.events.length) {{
        turnEvents.innerHTML = `<article class="event-item"><strong>Initial State</strong><div class="event-meta">No turn events yet.</div></article>`;
        return;
      }}

      turnEvents.innerHTML = snapshot.events.map((event) => {{
        const icon = getEventIconData(event.type);
        if (event.type === "unrest_disturbance" || event.type === "unrest_crisis") {{
          icon.symbol = "!";
          icon.className = "event-icon-unrest";
          icon.label = "Unrest";
        }} else if (event.type === "unrest_secession") {{
          icon.symbol = "x";
          icon.className = "event-icon-secession";
          icon.label = "Secession";
        }} else if (event.type === "rebel_independence") {{
          icon.symbol = "*";
          icon.className = "event-icon-success";
          icon.label = "Independence";
          }} else if (
            event.type === "diplomacy_rivalry"
            || event.type === "diplomacy_pact"
            || event.type === "diplomacy_alliance"
            || event.type === "diplomacy_truce"
            || event.type === "diplomacy_truce_end"
            || event.type === "diplomacy_break"
          ) {{
            icon.symbol = "=";
          icon.className = "event-icon-invest";
          icon.label = "Diplomacy";
        }}
        return `
        <article class="event-item">
          <div class="event-header">
            <span class="event-icon ${{icon.className}}" title="${{escapeHtml(icon.label)}}">${{icon.symbol}}</span>
            <strong>${{colorizeFactionNames(event.title)}}</strong>
          </div>
          <div>${{colorizeFactionNames(event.summary)}}</div>
          <div class="event-meta">Type: ${{escapeHtml(event.type)}}${{event.region_reference ? ` - Region ${{escapeHtml(event.region_reference)}}` : ""}}${{event.terrain_label ? ` - Terrain ${{escapeHtml(event.terrain_label)}}` : ""}}</div>
        </article>
      `;
      }}).join("");
    }}

    function applyUnrestStyling(element, regionSnapshot, isGraphView) {{
      const tier = getUnrestTier(regionSnapshot);
      if (tier === "disturbance" || tier === "crisis" || tier === "secession") {{
        element.setAttribute("stroke", getUnrestColor(regionSnapshot));
        element.setAttribute("stroke-width", isGraphView ? (tier === "crisis" ? 4 : 3) : (tier === "crisis" ? 5 : 4));
      }} else {{
        element.removeAttribute("stroke");
        element.removeAttribute("stroke-width");
      }}
    }}

    function updateMap(snapshot) {{
      const changed = new Set(snapshot.changed_regions);
      const contested = new Set(snapshot.contested_regions);
      renderAtlasPolityLabels(snapshot);

      for (const region of data.regions) {{
        const regionSnapshot = snapshot.regions[region.name];
        const fill = getRegionFill(regionSnapshot, region);
        const node = document.getElementById(`region-node-${{region.name}}`);
        const label = document.getElementById(`region-label-${{region.name}}`);
        const resource = document.getElementById(`region-resource-${{region.name}}`);

        node.setAttribute("fill", fill);
        applyUnrestStyling(node, regionSnapshot, true);
        node.classList.toggle("changed", changed.has(region.name));
        node.classList.toggle("contested", contested.has(region.name));
        label.textContent = regionSnapshot.display_name || region.display_name || region.name;
        resource.textContent = `T${{Number(regionSnapshot.taxable_value || 0).toFixed(1)}}${{(regionSnapshot.unrest_event_level || "none") === "crisis" ? " !!" : (Number(regionSnapshot.unrest || 0) >= 4 ? " !" : "")}}`;
        resource.setAttribute("fill", getUnrestColor(regionSnapshot));
        const title = document.getElementById(`region-title-${{region.name}}`);
        const terrainOverlay = document.getElementById(`region-terrain-${{region.name}}`);
        if (title) {{
          const ownerText = getFactionDisplayName(regionSnapshot.owner);
          const terrainText = regionSnapshot.terrain_label || region.terrain_label || "Plains";
          const climateText = regionSnapshot.climate_label || region.climate_label || "Temperate";
          const unrestText = getUnrestLabel(regionSnapshot);
          title.textContent = `${{regionSnapshot.display_name || region.display_name || region.name}} (${{region.name}}) - ${{ownerText}} - ${{terrainText}} - ${{climateText}} - Unrest: ${{unrestText}}`;
        }}
        if (terrainOverlay) {{
          terrainOverlay.textContent = getTerrainAbbreviation(regionSnapshot.terrain_tags || region.terrain_tags);
          terrainOverlay.setAttribute("fill", getTerrainColor(regionSnapshot.terrain_tags || region.terrain_tags));
        }}
      }}

      for (const region of data.atlas_regions) {{
        const regionSnapshot = snapshot.regions[region.name];
        const fill = getRegionFill(regionSnapshot, region);
        const polygon = document.getElementById(`atlas-region-${{region.name}}`);
        const label = document.getElementById(`atlas-label-${{region.name}}`);
        const resource = document.getElementById(`atlas-resource-${{region.name}}`);

        if (!polygon || !label || !resource) {{
          continue;
        }}

        polygon.setAttribute("fill", fill);
        applyUnrestStyling(polygon, regionSnapshot, false);
        polygon.classList.toggle("changed", changed.has(region.name));
        polygon.classList.toggle("contested", contested.has(region.name));
        label.textContent = regionSnapshot.display_name || region.display_name || region.name;
        resource.textContent = `T${{Number(regionSnapshot.taxable_value || 0).toFixed(1)}}${{(regionSnapshot.unrest_event_level || "none") === "crisis" ? " !!" : (Number(regionSnapshot.unrest || 0) >= 4 ? " !" : "")}}`;
        resource.setAttribute("fill", getUnrestColor(regionSnapshot));
        const title = document.getElementById(`atlas-title-${{region.name}}`);
        const terrainOverlay = document.getElementById(`atlas-terrain-${{region.name}}`);
        if (title) {{
          const ownerText = getFactionDisplayName(regionSnapshot.owner);
          const terrainText = regionSnapshot.terrain_label || region.terrain_label || "Plains";
          const climateText = regionSnapshot.climate_label || region.climate_label || "Temperate";
          const unrestText = getUnrestLabel(regionSnapshot);
          title.textContent = `${{regionSnapshot.display_name || region.display_name || region.name}} (${{region.name}}) - ${{ownerText}} - ${{terrainText}} - ${{climateText}} - Unrest: ${{unrestText}}`;
        }}
        if (terrainOverlay) {{
          terrainOverlay.textContent = getTerrainAbbreviation(regionSnapshot.terrain_tags || region.terrain_tags);
          terrainOverlay.setAttribute("fill", getTerrainColor(regionSnapshot.terrain_tags || region.terrain_tags));
        }}
      }}
    }}

    function renderTurn(turn) {{
      state.currentTurn = turn;
      const snapshot = data.snapshots[turn];
      slider.value = String(turn);
      readout.textContent = `Turn ${{turn}} of ${{data.turns}}`;
      syncRunSummaryVisibility(turn);
      updateMap(snapshot);
      renderLegend(snapshot);
      renderStandings(snapshot);
      renderTurnContext(turn, snapshot);
      renderTurnEvents(snapshot);
      renderDoctrinePanel(snapshot);
      renderRegionDetail(snapshot);
    }}

    function stopPlayback() {{
      state.playing = false;
      playToggle.textContent = "Play";
      if (state.timer) {{
        window.clearInterval(state.timer);
        state.timer = null;
      }}
    }}

    function startPlayback() {{
      stopPlayback();
      state.playing = true;
      playToggle.textContent = "Pause";
      state.timer = window.setInterval(() => {{
        if (state.currentTurn >= data.turns) {{
          stopPlayback();
          return;
        }}
        renderTurn(state.currentTurn + 1);
      }}, 1100);
    }}

    slider.max = String(data.turns);
    slider.addEventListener("input", () => {{
      stopPlayback();
      renderTurn(Number(slider.value));
    }});

    playToggle.addEventListener("click", () => {{
      if (state.playing) {{
        stopPlayback();
      }} else {{
        startPlayback();
      }}
    }});

    prevButton.addEventListener("click", () => {{
      stopPlayback();
      renderTurn(Math.max(0, state.currentTurn - 1));
    }});

    nextButton.addEventListener("click", () => {{
      stopPlayback();
      renderTurn(Math.min(data.turns, state.currentTurn + 1));
    }});

    buildStaticMap();
    renderLegend();
    renderTerrainLegend();
    renderViewToggle();
    renderRunSummary();
    buildDoctrineTimelineControls();
    renderDoctrineTimeline();
    renderTurn(0);
  </script>
</body>
</html>"""


def write_simulation_html(world, output_path=SIMULATION_VIEWER_OUTPUT):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_simulation_html(world), encoding="utf-8")
    return output_path
