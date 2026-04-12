from src.world import create_world
from src.simulation import run_simulation
from src.narrative import build_chronicle


def main():
    world = create_world(map_name="thirteen_region_ring")
    world = run_simulation(world, num_turns=20, verbose=False)

    chronicle = build_chronicle(world)
    print(chronicle)

    with open("chronicle.txt", "w") as file:
        file.write(chronicle)


if __name__ == "__main__":
    main()