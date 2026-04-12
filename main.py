from src.experiments import run_turn_horizon_comparison


def main():
    run_turn_horizon_comparison(
        turn_counts=[5, 10, 20, 40, 80, 160],
        iterations_per_batch=100,
        num_batches=5,
        map_name="thirteen_region_ring",
        output_file="turn_horizon_results.txt",
    )


if __name__ == "__main__":
    main()