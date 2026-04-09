from src.world import create_initial_world
from src.simulation import run_simulation


def count_owned_regions(world):
    """Returns a dictionary of faction_name -> number of owned regions."""

    owned_region_counts = {faction_name: 0 for faction_name in world.factions}

    for region in world.regions.values():
        if region.owner is not None:
            owned_region_counts[region.owner] += 1

    return owned_region_counts


def get_center_owner(world):
    """Returns the owner of the center region M."""

    return world.regions["M"].owner


def summarize_world(world):
    """Returns a summary dictionary for the final state of the world."""

    owned_region_counts = count_owned_regions(world)

    summary = {
        "turn": world.turn,
        "center_owner": get_center_owner(world),
        "factions": {}
    }

    for faction_name, faction in world.factions.items():
        summary["factions"][faction_name] = {
            "treasury": faction.treasury,
            "owned_regions": owned_region_counts[faction_name],
        }

    return summary


def run_experiment(num_turns, faction_order):
    """Runs one simulation and returns a summary."""

    world = create_initial_world()
    final_world = run_simulation(
        world,
        num_turns,
        faction_order=faction_order,
        verbose=False
    )
    return summarize_world(final_world)


def format_experiment_summary(summary, faction_order):
    lines = []
    lines.append("\n==============================")
    lines.append(f"Faction Order: {faction_order}")
    lines.append(f"Turns: {summary['turn']}")
    lines.append(f"Center Owner: {summary['center_owner']}")
    lines.append("Faction Results:")

    for faction_name, faction_summary in summary["factions"].items():
        lines.append(
            f"  {faction_name}: "
            f"treasury={faction_summary['treasury']}, "
            f"owned_regions={faction_summary['owned_regions']}"
        )

    return "\n".join(lines)


def run_order_comparison(num_turns=10, output_file=None):
    faction_orders = [
        ["Faction1", "Faction2", "Faction3"],
        ["Faction2", "Faction3", "Faction1"],
        ["Faction3", "Faction1", "Faction2"],
    ]

    all_output = []

    for faction_order in faction_orders:
        summary = run_experiment(num_turns=num_turns, faction_order=faction_order)
        formatted = format_experiment_summary(summary, faction_order)

        print(formatted)
        all_output.append(formatted)

    if output_file:
        with open(output_file, "w") as f:
            f.write("\n\n".join(all_output))