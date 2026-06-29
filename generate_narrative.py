"""One-shot script: generate interpretive narrative from a saved input JSON.

Usage:
    python generate_narrative.py [input_json] [output_txt]

Defaults:
    input_json  = reports/interpretive_narrative_input.json
    output_txt  = reports/runs/azhora_sc4_live/interpretive_narrative.txt
"""
import json
import os
import sys
from pathlib import Path

from src.ai_interpretation import AI_INTERPRETATION_MODEL, generate_ai_interpretation

INPUT_DEFAULT  = Path("reports/interpretive_narrative_input.json")
OUTPUT_DEFAULT = Path("reports/runs/azhora_sc4_live/interpretive_narrative.txt")

def main():
    input_path  = Path(sys.argv[1]) if len(sys.argv) > 1 else INPUT_DEFAULT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT_DEFAULT

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Error: set OPENAI_API_KEY before running this script.")

    if not input_path.exists():
        raise SystemExit(f"Error: input file not found: {input_path}")

    with open(input_path, encoding="utf-8") as f:
        ai_summary = json.load(f)

    print(f"Generating narrative from {input_path} …")
    narrative = generate_ai_interpretation(ai_summary, strict=True, enabled_override=True)
    if not narrative:
        raise SystemExit("Error: generation returned empty result.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Interpretive Narrative", "", f"Model: {AI_INTERPRETATION_MODEL}", "", narrative]
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Narrative written to {output_path}")

if __name__ == "__main__":
    main()
