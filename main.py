import argparse
from pathlib import Path

from src.world import create_world
from src.simulation import run_simulation
from src.narrative import build_chronicle
from src.event_analysis import get_event_log
from src.metrics import analyze_competition_metrics, get_metrics_log
from src.simulation_ui import write_simulation_html
from src.region_naming import format_region_reference
from src.terrain import format_terrain_label


REPORTS_DIR = Path("reports")
RESULTS_OUTPUT = REPORTS_DIR / "results.txt"
CHRONICLE_OUTPUT = REPORTS_DIR / "chronicle.txt"


def build_simulation_setup(world, map_name, num_turns, starting_treasuries):
    """Builds the simulation setup section for the results report."""
    lines = []

    lines.append("Simulation Setup")
    lines.append("")
    lines.append(f"Map: {map_name}")
    lines.append(f"Turns: {num_turns}")
    lines.append(f"Regions: {len(world.regions)}")
    lines.append(f"Factions: {len(world.factions)}")
    lines.append("Faction Doctrines:")

    for faction_name, faction in world.factions.items():
        tradition_labels = ",".join(faction.identity.source_traditions) if faction.identity else ""
        lines.append(
            f"  {faction_name}: doctrine={faction.doctrine_label}, "
            f"homeland={faction.doctrine_profile.homeland_identity}, "
            f"terrain_identity={faction.doctrine_profile.terrain_identity}, "
            f"starting_treasury={starting_treasuries[faction_name]}, "
            f"culture={faction.culture_name}, "
            f"government={faction.government_type}, "
            f"internal_id={faction.internal_id}, "
            f"traditions={tradition_labels}, "
            f"ai_generated={faction.identity.ai_generated if faction.identity else False}"
        )

    return lines


def format_event(event, world):
    """Formats one simulation event for the results report."""
    region_reference = event.region
    terrain_text = ""
    if event.region is not None and event.region in world.regions:
        region_reference = format_region_reference(world.regions[event.region], include_code=True)
        terrain_text = f", terrain={format_terrain_label(world.regions[event.region].terrain_tags)}"

    if event["type"] == "expand":
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} expanded into {region_reference} "
            f"(score={event.get('score', 0)}, resources={event.get('resources', 0)}, "
            f"neighbors={event.get('neighbors', 0)}, "
            f"unclaimed_neighbors={event.get('unclaimed_neighbors', 0)}, "
            f"core_status={event.get('core_status', 'frontier')}, "
            f"treasury_after={event.get('treasury_after', 0)}{terrain_text})"
        )

    if event["type"] == "invest":
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} invested in {region_reference} "
            f"(invest_amount={event.get('invest_amount', 0)}, "
            f"new_resources={event.get('new_resources', 0)}{terrain_text})"
        )

    if event["type"] == "attack":
        defender = event.get("defender", "Unknown")
        outcome = "captured" if event.get("success", False) else "failed against"
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} attacked {defender} in {region_reference} "
            f"and {outcome} the region "
            f"(success_chance={event.get('success_chance', 0):.3f}, "
            f"attack_strength={event.get('attack_strength', 0)}, "
            f"defense_strength={event.get('defense_strength', 0)}, "
            f"core_status={event.get('core_status', 'frontier')}, "
            f"treasury_after={event.get('treasury_after', 0)}{terrain_text})"
        )

    if event["type"] == "income":
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} collected base income "
            f"(base_income={event.get('base_income', event.get('income', 0))}, "
            f"owned_regions={event.get('owned_regions', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    if event["type"] == "empire_scale":
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} paid empire scale penalty "
            f"(owned_regions={event.get('owned_regions', 0)}, "
            f"free_regions={event.get('empire_free_regions', 0)}, "
            f"scale_cost={event.get('empire_scale_cost', 0)}, "
            f"empire_penalty={event.get('empire_penalty', 0)}, "
            f"effective_income={event.get('effective_income', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    if event["type"] == "maintenance":
        return (
            f"Turn {event['turn'] + 1}: {event['faction']} paid maintenance "
            f"(maintenance={event.get('maintenance', 0)}, "
            f"owned_regions={event.get('owned_regions', 0)}, "
            f"net_income={event.get('net_income', 0)}, "
            f"treasury_after={event.get('treasury_after', 0)})"
        )

    return f"Turn {event['turn'] + 1}: {event}"


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
            f"Largest treasury lead: turn {treasury_lead['turn']}, "
            f"{treasury_lead['leader']} by {treasury_lead['margin']} over {treasury_lead['runner_up']}"
        )

    region_lead = competition["largest_region_lead"]
    if region_lead["leader"] is not None:
        lines.append(
            f"Largest region lead: turn {region_lead['turn']}, "
            f"{region_lead['leader']} by {region_lead['margin']} over {region_lead['runner_up']}"
        )

    runaway = competition["runaway"]
    if runaway["detected"]:
        lines.append(
            f"Runaway: yes, {runaway['winner']} took an uncontested treasury lead for good on turn {runaway['start_turn']}."
        )
    else:
        lines.append("Runaway: no decisive permanent treasury lead.")

    comeback = competition["comeback"]
    if comeback["winner"] is not None:
        lines.append(
            f"Comeback: {'yes' if comeback['detected'] else 'no'}, "
            f"{comeback['winner']} faced a max treasury deficit of {comeback['max_deficit_overcome']} "
            f"and trailed by {comeback['midpoint_deficit']} at midpoint turn {comeback['midpoint_turn']}."
        )

    eliminated = [
        f"{faction_name} on turn {data['turn']}"
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
            f"homeland_regions={closing.get('homeland_regions', 0)}, "
            f"core_regions={closing.get('core_regions', 0)}, "
            f"frontier_regions={closing.get('frontier_regions', 0)}"
        )

    lines.append("")
    lines.append("Per-Turn Metrics")
    lines.append("")

    for snapshot in get_metrics_log(world):
        lines.append(f"Turn {snapshot['turn']}")
        for faction_name, faction_metrics in snapshot["factions"].items():
            lines.append(
                f"  {faction_name}: treasury={faction_metrics['treasury']}, "
                f"regions={faction_metrics['regions']}, "
                f"attacks={faction_metrics['attacks']}, "
                f"expansions={faction_metrics['expansions']}, "
                f"investments={faction_metrics['investments']}, "
                f"base_income={faction_metrics['income']}, "
                f"nominal_income={faction_metrics.get('nominal_income', faction_metrics['income'])}, "
                f"scale_penalty={faction_metrics.get('empire_penalty', 0)}, "
                f"effective_income={faction_metrics.get('effective_income', 0)}, "
                f"maintenance={faction_metrics['maintenance']}, "
                f"net={faction_metrics['net_income']}, "
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
        help="Map name to simulate.",
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
    return parser.parse_args()


def main():
    args = parse_args()
    map_name = args.map_name
    num_turns = args.num_turns
    num_factions = args.num_factions

    try:
        world = create_world(map_name=map_name, num_factions=num_factions)
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

    simulation_view_output = write_simulation_html(world)
    print(f"\nSimulation viewer written to {simulation_view_output}")


if __name__ == "__main__":
    main()
