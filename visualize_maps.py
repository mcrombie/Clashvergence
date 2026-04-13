from __future__ import annotations

import argparse
from pathlib import Path

from src.maps import MAPS
from src.map_visualization import render_index_html, render_map_html


DEFAULT_OUTPUT_DIR = Path("reports/map_visuals")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate simple testing-oriented visualizations for map layouts."
    )
    parser.add_argument(
        "--maps",
        nargs="+",
        default=sorted(MAPS),
        help="One or more map names to render.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where HTML visualizations will be written.",
    )
    return parser.parse_args()


def validate_maps(map_names):
    invalid_maps = [map_name for map_name in map_names if map_name not in MAPS]
    if invalid_maps:
        available = ", ".join(sorted(MAPS))
        invalid = ", ".join(invalid_maps)
        raise ValueError(f"Unknown map(s): {invalid}. Available maps: {available}")


def main():
    args = parse_args()
    validate_maps(args.maps)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for map_name in args.maps:
        html_text = render_map_html(map_name, MAPS[map_name])
        output_path = args.output_dir / f"{map_name}.html"
        output_path.write_text(html_text, encoding="utf-8")
        print(f"Wrote {output_path}")

    index_path = args.output_dir / "index.html"
    index_path.write_text(render_index_html(args.maps), encoding="utf-8")
    print(f"Wrote {index_path}")


if __name__ == "__main__":
    main()
