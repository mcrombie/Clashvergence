from src.world import create_initial_world
from src.simulation import run_simulation


# def main():
#     world = create_initial_world()
#     world = run_simulation(world, 10)

#     print("\nFinal Results")
#     for faction_name, faction in world.factions.items():
#         print(f"{faction_name}: treasury={faction.treasury}")

#     for region_name, region in world.regions.items():
#         print(
#             f"{region_name}: owner={region.owner}, resources={region.resources}"
#         )


# if __name__ == "__main__":
#     main()


from src.experiments import run_order_comparison


def main():
    run_order_comparison(num_turns=10, output_file="results.txt")


if __name__ == "__main__":
    main()