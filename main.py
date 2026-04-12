from src.experiments import run_multiple_batches


def main():
    run_multiple_batches(
        num_turns=20,
        iterations_per_batch=100,
        num_batches=5,
        map_name="thirteen_region_ring",
        output_file="results.txt",
    )


if __name__ == "__main__":
    main()