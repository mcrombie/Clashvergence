import argparse
import json
import os
from pathlib import Path
import random

from src.calendar import (
    TURNS_PER_YEAR,
    format_snapshot_date,
    format_snapshot_label,
    format_turn_label,
    format_turn_span,
    get_turn_season_name,
)
from src.ai_interpretation import (
    AI_INTERPRETATION_MODEL,
    build_ai_interpretation_summary,
    generate_ai_interpretation,
    is_ai_interpretation_enabled,
)
from src.world import create_world
from src.simulation import run_simulation
from src.narrative import build_chronicle
from src.event_analysis import get_event_log
from src.metrics import analyze_competition_metrics, get_metrics_log
from src.map_generator_ui import write_map_generator_html
from src.simulation_ui import write_simulation_html
from src.region_naming import format_region_reference
from src.terrain import format_terrain_label, get_seasonal_terrain_note


REPORTS_DIR = Path("reports")
RESULTS_OUTPUT = REPORTS_DIR / "results.txt"
CHRONICLE_OUTPUT = REPORTS_DIR / "chronicle.txt"
AI_INTERPRETIVE_NARRATIVE_OUTPUT = REPORTS_DIR / "interpretive_narrative.txt"
AI_INTERPRETIVE_INPUT_OUTPUT = REPORTS_DIR / "interpretive_narrative_input.json"


def _get_faction_display_name(world, faction_name):
    if faction_name is None:
        return "another faction"
    faction = world.factions.get(faction_name)
    if faction is None:
        return faction_name
    return faction.display_name


def build_simulation_setup(world, map_name, num_turns, starting_treasuries):
    """Builds the simulation setup section for the results report."""
    lines = []

    lines.append("Simulation Setup")
    lines.append("")
    lines.append(f"Map: {map_name}")
    lines.append(f"Turns: {num_turns}")
    lines.append(f"Calendar: {TURNS_PER_YEAR} turns per year (Spring, Summer, Autumn, Winter)")
    lines.append(f"Duration: {format_turn_span(num_turns)}")
    if getattr(world, "random_seed", None) is not None:
        lines.append(f"Seed: {world.random_seed}")
    lines.append(f"Regions: {len(world.regions)}")
    lines.append(f"Factions: {len(world.factions)}")
    lines.append(f"Starting Population: {sum(region.population for region in world.regions.values())}")
    lines.append("Faction Doctrines:")

    for faction_name, faction in world.factions.items():
        tradition_labels = ",".join(faction.identity.source_traditions) if faction.identity else ""
        starting_treasury = starting_treasuries.get(faction_name, faction.starting_treasury)
        lines.append(
            f"  {faction.display_name}: doctrine={faction.doctrine_label}, "
            f"homeland={faction.doctrine_profile.homeland_identity}, "
            f"terrain_identity={faction.doctrine_profile.terrain_identity}, "
            f"starting_treasury={starting_treasury}, "
            f"culture={faction.culture_name}, "
            f"ethnicity={faction.primary_ethnicity}, "
            f"government={faction.government_type}, "
            f"ideology={faction.ideology.dominant_label}, "
            f"internal_id={faction.internal_id}, "
            f"traditions={tradition_labels}, "
            f"ai_generated={faction.identity.ai_generated if faction.identity else False}, "
            f"is_rebel={faction.is_rebel}, "
            f"origin_faction={faction.origin_faction}, "
            f"proto_state={faction.proto_state}"
        )

    return lines


def format_event(event, world):
    """Formats one simulation event for the results report."""
    time_label = format_turn_label(event["turn"])
    region_reference = event.region
    faction_name = _get_faction_display_name(world, event.faction)
    counterpart_name = _get_faction_display_name(world, event.get("counterpart"))
    origin_name = _get_faction_display_name(world, event.get("origin_faction"))
    rebel_name = _get_faction_display_name(world, event.get("rebel_faction"))
    terrain_text = ""
    seasonal_text = ""
    if event.region is not None and event.region in world.regions:
        region = world.regions[event.region]
        region_reference = format_region_reference(region, include_code=True)
        terrain_text = f", terrain={format_terrain_label(region.terrain_tags)}"
        event_context = "general"
        if event["type"] == "attack":
            event_context = "attack"
        elif event["type"] in {"migration_wave", "refugee_wave"}:
            event_context = "migration"
        elif event["type"] in {"unrest_disturbance", "unrest_crisis", "regime_agitation"}:
            event_context = "unrest"
        seasonal_note = get_seasonal_terrain_note(region.terrain_tags, get_turn_season_name(event["turn"]), context=event_context)
        seasonal_text = f", seasonal_note={seasonal_note}" if seasonal_note else ""

    if event["type"] == "expand":
        return (
            f"{time_label}: {faction_name} expanded into {region_reference} "
            f"(score={event.get('score', 0)}, taxable={event.get('taxable_value', event.get('resources', 0))}, "
            f"neighbors={event.get('neighbors', 0)}, "
            f"unclaimed_neighbors={event.get('unclaimed_neighbors', 0)}, "
            f"core_status={event.get('core_status', 'frontier')}, "
            f"treasury_after={event.get('treasury_after', 0)}{terrain_text}{seasonal_text})"
        )

    if event["type"] in {"invest", "develop"}:
        project_type = event.get("project_type", "development").replace("_", " ")
        resource_focus = event.get("resource_focus")
        return (
            f"{time_label}: {faction_name} invested in {region_reference} "
            f"(project={project_type}"
            f"{f', focus={resource_focus}' if resource_focus else ''}, "
            f"invest_amount={event.get('invest_amount', 0)}, "
            f"new_taxable={event.get('new_taxable_value', event.get('new_resources', 0))}{terrain_text}{seasonal_text})"
        )

    if event["type"] == "attack":
        defender = _get_faction_display_name(world, event.get("defender")) if event.get("defender") else "Unknown"
        outcome = "captured" if event.get("success", False) else "failed against"
        return (
            f"{time_label}: {faction_name} attacked {defender} in {region_reference} "
            f"and {outcome} the region "
            f"(success_chance={event.get('success_chance', 0):.3f}, "
            f"attack_strength={event.get('attack_strength', 0)}, "
            f"defense_strength={event.get('defense_strength', 0)}, "
            f"core_status={event.get('core_status', 'frontier')}, "
            f"treasury_after={event.get('treasury_after', 0)}{terrain_text}{seasonal_text})"
        )

    if event["type"] == "income":
        return (
            f"{time_label}: {faction_name} collected base income "
            f"(base_income={event.get('base_income', event.get('income', 0))}, "
            f"owned_regions={event.get('owned_regions', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    if event["type"] == "empire_scale":
        return (
            f"{time_label}: {faction_name} paid empire scale penalty "
            f"(owned_regions={event.get('owned_regions', 0)}, "
            f"free_regions={event.get('empire_free_regions', 0)}, "
            f"scale_cost={event.get('empire_scale_cost', 0)}, "
            f"empire_penalty={event.get('empire_penalty', 0)}, "
            f"effective_income={event.get('effective_income', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    if event["type"] == "maintenance":
        return (
            f"{time_label}: {faction_name} paid maintenance "
            f"(maintenance={event.get('maintenance', 0)}, "
            f"owned_regions={event.get('owned_regions', 0)}, "
            f"net_income={event.get('net_income', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    if event["type"] == "unrest_disturbance":
        return (
            f"{time_label}: unrest disturbed {region_reference} under {faction_name} "
            f"(unrest={event.get('unrest', 0):.2f}, "
            f"duration={event.get('duration', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)}{terrain_text}{seasonal_text})"
        )

    if event["type"] == "unrest_crisis":
        return (
            f"{time_label}: crisis gripped {region_reference} under {faction_name} "
            f"(unrest={event.get('unrest', 0):.2f}, "
            f"duration={event.get('duration', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)}{terrain_text}{seasonal_text})"
        )

    if event["type"] == "unrest_secession":
        return (
            f"{time_label}: {region_reference} seceded from {faction_name} "
            f"as {rebel_name} "
            f"(unrest={event.get('unrest', 0):.2f}, "
            f"new_resources={event.get('new_resources', 0)}{terrain_text})"
        )

    if event["type"] == "rebel_independence":
        return (
            f"{time_label}: {faction_name} declared full independence "
            f"from {origin_name} "
            f"(rebel_age={event.get('rebel_age', 0)}, "
            f"independence_score={event.get('independence_score', 0):.2f}, "
            f"government={event.get('government_type', 'State')}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    if event["type"] == "polity_advance":
        return (
            f"{time_label}: {faction_name} advanced from "
            f"{event.get('old_polity_tier', 'lower order')} to {event.get('new_polity_tier', 'higher order')} "
            f"as a {event.get('new_government_type', 'new government')} "
            f"(population={event.get('population', 0)}, "
            f"towns={event.get('town_regions', 0)}, "
            f"cities={event.get('city_regions', 0)}, "
            f"surplus={event.get('total_surplus', 0)})"
        )

    if event["type"] == "technology_adoption":
        return (
            f"{time_label}: {region_reference} adopted {event.get('technology_label', 'a new method')} "
            f"under {faction_name} "
            f"(adoption={event.get('adoption', 0):.2f}{terrain_text}{seasonal_text})"
        )

    if event["type"] == "technology_institutionalized":
        return (
            f"{time_label}: {faction_name} institutionalized "
            f"{event.get('technology_label', 'a new method')} "
            f"(level={event.get('institutional_level', 0):.2f})"
        )

    if event["type"] == "diplomacy_rivalry":
        return (
            f"{time_label}: {faction_name} and {counterpart_name} "
            f"became rivals (score={event.get('score', 0):.2f})"
        )

    if event["type"] == "diplomacy_pact":
        return (
            f"{time_label}: {faction_name} and {counterpart_name} "
            f"entered a non-aggression pact (score={event.get('score', 0):.2f})"
        )

    if event["type"] == "diplomacy_alliance":
        return (
            f"{time_label}: {faction_name} and {counterpart_name} "
            f"formed an alliance (score={event.get('score', 0):.2f})"
        )

    if event["type"] == "diplomacy_truce":
        return (
            f"{time_label}: {faction_name} and {counterpart_name} "
            f"entered a truce for {event.get('duration', 0)} turn(s)"
        )

    if event["type"] == "diplomacy_truce_end":
        return (
            f"{time_label}: the truce between {faction_name} and "
            f"{counterpart_name} expired "
            f"(new_status={event.get('new_status', 'neutral')}, score={event.get('score', 0):.2f})"
        )

    if event["type"] == "ideology_shift":
        return (
            f"{time_label}: {faction_name} shifted from "
            f"{event.get('previous_label', 'an older political current')} to "
            f"{event.get('new_label', 'a new political current')} "
            f"(cohesion={event.get('cohesion', 0):.2f}, "
            f"radicalism={event.get('radicalism', 0):.2f}, "
            f"legitimacy_model={event.get('legitimacy_model', 'customary')})"
        )

    if event["type"] == "diplomacy_break":
        return (
            f"{time_label}: {faction_name} and {counterpart_name} "
            f"broke their {event.get('previous_status', 'diplomatic')} relationship "
            f"(score={event.get('score', 0):.2f})"
        )

    return f"{time_label}: {event}"


def build_results_report(world, map_name, num_turns, starting_treasuries):
    """Builds a detailed simulation report."""
    lines = []
    competition = analyze_competition_metrics(world)

    lines.append("Detailed Simulation Results")
    lines.append("")
    lines.extend(build_simulation_setup(world, map_name, num_turns, starting_treasuries))
    lines.append("")
    lines.append(build_chronicle(world))
    lines.append("")
    lines.append("Strategic Dynamics")
    lines.append("")
    lines.append(f"Outright treasury lead changes: {competition['lead_changes']}")

    treasury_lead = competition["largest_treasury_lead"]
    if treasury_lead["leader"] is not None:
        lines.append(
            f"Largest treasury lead: {format_snapshot_date(treasury_lead['turn'])}, "
            f"{treasury_lead['leader']} by {treasury_lead['margin']} over {treasury_lead['runner_up']}"
        )

    region_lead = competition["largest_region_lead"]
    if region_lead["leader"] is not None:
        lines.append(
            f"Largest region lead: {format_snapshot_date(region_lead['turn'])}, "
            f"{region_lead['leader']} by {region_lead['margin']} over {region_lead['runner_up']}"
        )

    runaway = competition["runaway"]
    if runaway["detected"]:
        lines.append(
            f"Runaway: yes, {runaway['winner']} took an uncontested treasury lead for good by {format_snapshot_date(runaway['start_turn'])}."
        )
    else:
        lines.append("Runaway: no decisive permanent treasury lead.")

    comeback = competition["comeback"]
    if comeback["winner"] is not None:
        lines.append(
            f"Comeback: {'yes' if comeback['detected'] else 'no'}, "
            f"{comeback['winner']} faced a max treasury deficit of {comeback['max_deficit_overcome']} "
            f"and trailed by {comeback['midpoint_deficit']} at {format_snapshot_date(comeback['midpoint_turn'])}."
        )

    eliminated = [
        f"{faction_name} by {format_snapshot_date(data['turn'])}"
        for faction_name, data in competition["eliminations"].items()
        if data["eliminated"]
    ]
    if eliminated:
        lines.append(f"Eliminations: {', '.join(eliminated)}.")
    else:
        lines.append("Eliminations: none.")

    lines.append("")
    lines.append("Event Log")
    lines.append("")

    for event in get_event_log(world):
        lines.append(format_event(event, world))

    lines.append("")
    lines.append("Doctrine Evolution")
    lines.append("")

    for faction_name in world.factions:
        history = [
            snapshot["factions"][faction_name]
            for snapshot in get_metrics_log(world)
            if faction_name in snapshot["factions"]
        ]
        if not history:
            continue

        opening = history[0]
        closing = history[-1]
        doctrine_shifts = sum(
            1
            for earlier, later in zip(history, history[1:])
            if earlier.get("doctrine_label") != later.get("doctrine_label")
        )
        lines.append(
            f"{faction_name}: homeland={closing.get('homeland_identity', 'Unknown')}, "
            f"opened as {opening.get('doctrine_label', 'Unknown')}, "
            f"ended as {closing.get('doctrine_label', 'Unknown')}, "
            f"terrain_identity={closing.get('terrain_identity', 'Unknown')}, "
            f"doctrine_shifts={doctrine_shifts}, "
            f"population={closing.get('population', 0)}, "
            f"homeland_regions={closing.get('homeland_regions', 0)}, "
            f"core_regions={closing.get('core_regions', 0)}, "
            f"frontier_regions={closing.get('frontier_regions', 0)}"
        )

    lines.append("")
    lines.append("Per-Turn Metrics")
    lines.append("")

    for snapshot in get_metrics_log(world):
        lines.append(format_snapshot_label(snapshot["turn"]))
        for faction_name, faction_metrics in snapshot["factions"].items():
            lines.append(
                f"  {faction_name}: treasury={faction_metrics['treasury']}, "
                f"regions={faction_metrics['regions']}, "
                f"population={faction_metrics.get('population', 0)}, "
                f"attacks={faction_metrics['attacks']}, "
                f"expansions={faction_metrics['expansions']}, "
                f"developments={faction_metrics.get('developments', faction_metrics['investments'])}, "
                f"base_income={faction_metrics['income']}, "
                f"nominal_income={faction_metrics.get('nominal_income', faction_metrics['income'])}, "
                f"scale_penalty={faction_metrics.get('empire_penalty', 0)}, "
                f"effective_income={faction_metrics.get('effective_income', 0)}, "
                f"maintenance={faction_metrics['maintenance']}, "
                f"net={faction_metrics['net_income']}, "
                f"tech_presence={faction_metrics.get('average_technology_presence', 0.0)}, "
                f"tech_institutional={faction_metrics.get('average_institutional_technology', 0.0)}, "
                f"ideology={faction_metrics.get('dominant_ideology_label', 'Customary Pluralism')}, "
                f"doctrine={faction_metrics.get('doctrine_label', 'Unknown')}, "
                f"homeland={faction_metrics.get('homeland_regions', 0)}, "
                f"core={faction_metrics.get('core_regions', 0)}, "
                f"frontier={faction_metrics.get('frontier_regions', 0)}"
            )
        lines.append("")

    return "\n".join(lines).rstrip()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run one Clashvergence simulation."
    )
    parser.add_argument(
        "--map",
        dest="map_name",
        default="multi_ring_symmetry",
        help="Map name to simulate. Use generated_ring, generated_frontier, or generated_basin for dynamic maps.",
    )
    parser.add_argument(
        "--turns",
        dest="num_turns",
        type=int,
        default=20,
        help="Number of turns to simulate.",
    )
    parser.add_argument(
        "--num-factions",
        type=int,
        default=4,
        help="Number of factions to include in the simulation.",
    )
    parser.add_argument(
        "--seed",
        help="Optional run seed for reproducible world generation, naming, and simulation outcomes.",
    )
    parser.add_argument(
        "--ai-narrative",
        choices=["auto", "on", "off"],
        default="auto",
        help="Whether to use the OpenAI API for interpretive narrative generation.",
    )
    parser.add_argument(
        "--map-lab",
        action="store_true",
        help="Write the standalone dynamic map generator UI and exit.",
    )
    parser.add_argument("--map-style", choices=["continent", "frontier", "basin", "archipelago", "highlands"])
    parser.add_argument("--map-seed")
    parser.add_argument("--map-regions", type=int)
    parser.add_argument("--map-landmasses", type=int)
    parser.add_argument("--map-water", type=float)
    parser.add_argument("--map-rivers", type=int)
    parser.add_argument("--map-mountains", type=int)
    parser.add_argument("--map-climate", choices=["temperate", "varied", "arid", "cold", "tropical"])
    parser.add_argument("--map-richness", type=float)
    parser.add_argument("--map-chokepoints", type=float)
    parser.add_argument("--map-diversity", type=float)
    parser.add_argument("--map-starts", choices=["balanced", "coastal", "heartland", "frontier"])
    return parser.parse_args()


def build_map_generation_overrides(args):
    option_map = {
        "map_style": "style",
        "map_seed": "seed",
        "map_regions": "region_count",
        "map_landmasses": "landmass_count",
        "map_water": "water_level",
        "map_rivers": "river_count",
        "map_mountains": "mountain_spines",
        "map_climate": "climate_mode",
        "map_richness": "resource_richness",
        "map_chokepoints": "chokepoint_density",
        "map_diversity": "terrain_diversity",
        "map_starts": "start_strategy",
    }
    overrides = {}
    for attribute_name, config_name in option_map.items():
        value = getattr(args, attribute_name, None)
        if value is not None:
            overrides[config_name] = value
    if "seed" not in overrides and getattr(args, "seed", None) is not None:
        overrides["seed"] = args.seed
    return overrides or None


def should_generate_ai_narrative(args) -> bool:
    if args.ai_narrative == "on":
        return True
    if args.ai_narrative == "off":
        return False
    return is_ai_interpretation_enabled()


def main():
    args = parse_args()
    if args.map_lab:
        output_path = write_map_generator_html()
        print(f"Map generator UI written to {output_path}")
        return

    map_name = args.map_name
    num_turns = args.num_turns
    num_factions = args.num_factions
    seed = args.seed
    map_generation_config = build_map_generation_overrides(args)
    if seed is not None:
        random.seed(seed)

    try:
        world = create_world(
            map_name=map_name,
            num_factions=num_factions,
            map_generation_config=map_generation_config,
            seed=seed,
        )
    except ValueError as error:
        raise SystemExit(f"Error: {error}") from error

    starting_treasuries = {
        faction_name: faction.treasury
        for faction_name, faction in world.factions.items()
    }
    world = run_simulation(world, num_turns=num_turns, verbose=False)
    chronicle = build_chronicle(world)
    results = build_results_report(world, map_name, num_turns, starting_treasuries)
    print(results)

    RESULTS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_OUTPUT, "w") as file:
        file.write(results)

    with open(CHRONICLE_OUTPUT, "w") as file:
        file.write(chronicle)

    ai_summary = build_ai_interpretation_summary(
        world,
        map_name=map_name,
        num_turns=num_turns,
    )
    with open(AI_INTERPRETIVE_INPUT_OUTPUT, "w", encoding="utf-8") as file:
        json.dump(ai_summary, file, indent=2, ensure_ascii=True)

    ai_narrative = None
    ai_narrative_requested = should_generate_ai_narrative(args)
    if ai_narrative_requested:
        if not os.getenv("OPENAI_API_KEY"):
            raise SystemExit(
                "Error: AI narrative generation requires OPENAI_API_KEY when --ai-narrative is on."
            )
        ai_narrative = generate_ai_interpretation(
            ai_summary,
            strict=True,
            enabled_override=True,
        )
        ai_lines = [
            "Interpretive Narrative",
            "",
            f"Model: {AI_INTERPRETATION_MODEL}",
            "",
            ai_narrative,
        ]
        with open(AI_INTERPRETIVE_NARRATIVE_OUTPUT, "w", encoding="utf-8") as file:
            file.write("\n".join(ai_lines).rstrip() + "\n")

    simulation_view_output = write_simulation_html(world)
    print(f"\nSimulation viewer written to {simulation_view_output}")
    if ai_narrative is not None:
        print(f"AI interpretive narrative written to {AI_INTERPRETIVE_NARRATIVE_OUTPUT}")
    else:
        if args.ai_narrative == "off":
            print("AI interpretive narrative skipped because --ai-narrative is off.")
        else:
            print(
                "AI interpretive narrative skipped because "
                "CLASHVERGENCE_ENABLE_AI_INTERPRETATION is disabled or OPENAI_API_KEY is missing."
            )


if __name__ == "__main__":
    main()
