from src.world import create_world
from src.simulation import run_simulation


# def main():
#     world = create_world("ten_region_ring")
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
    run_order_comparison(
        num_turns=10,
        iterations=20,
        map_name="ten_region_ring",
        output_file="results.txt",
    )


if __name__ == "__main__":
    main()