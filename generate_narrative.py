"""One-shot script: generate interpretive narrative from a saved input JSON.

Usage:
    python generate_narrative.py [input_json] [output_txt] [--use-rag]

Defaults:
    input_json  = reports/interpretive_narrative_input.json
    output_txt  = reports/runs/azhora_sc4_live/interpretive_narrative.txt
"""
import argparse
import json
import os
from pathlib import Path

from src.ai_interpretation import (
    AI_INTERPRETATION_MODEL,
    enrich_summary_for_narrative_rag,
    generate_ai_interpretation,
)
from src.narrative_rag import (
    DEFAULT_CORPUS_DIR,
    build_generation_queries,
    build_rag_index,
    retrieve_syncretic_style_context,
)

INPUT_DEFAULT = Path("reports/interpretive_narrative_input.json")
OUTPUT_DEFAULT = Path("reports/runs/azhora_sc4_live/interpretive_narrative.txt")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate an AI interpretive narrative from a saved Clashvergence summary."
    )
    parser.add_argument(
        "input_json",
        nargs="?",
        default=INPUT_DEFAULT,
        type=Path,
        help="Path to interpretive_narrative_input.json.",
    )
    parser.add_argument(
        "output_txt",
        nargs="?",
        default=OUTPUT_DEFAULT,
        type=Path,
        help="Where to write the generated narrative.",
    )
    parser.add_argument(
        "--use-rag",
        action="store_true",
        help="Retrieve style passages from corpus/ and use the Boueni-remnant narrator persona.",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Force rebuilding the cached RAG embedding index.",
    )
    parser.add_argument(
        "--corpus-dir",
        default=DEFAULT_CORPUS_DIR,
        type=Path,
        help="Directory containing Herodotus and Dunsany source text files.",
    )
    parser.add_argument(
        "--rag-passages",
        default=9,
        type=int,
        help="Maximum number of retrieved style passages to inject.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = args.input_json
    output_path = args.output_txt

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Error: set OPENAI_API_KEY before running this script.")

    if not input_path.exists():
        raise SystemExit(f"Error: input file not found: {input_path}")

    with open(input_path, encoding="utf-8") as f:
        ai_summary = json.load(f)
    ai_summary = enrich_summary_for_narrative_rag(ai_summary)

    rag_context = None
    rag_note = None
    if args.use_rag:
        print(f"Building narrative RAG context from {args.corpus_dir} ...")
        index = build_rag_index(args.corpus_dir, force_rebuild=args.rebuild_index)
        queries = build_generation_queries(ai_summary)
        rag_context = retrieve_syncretic_style_context(
            index,
            queries,
            max_passages=max(1, args.rag_passages),
        )
        rag_note = (
            f"Narrative RAG: Boueni-descended remnant narrator, {len(rag_context)} style passages, "
            f"{index.embedding_provider} embeddings"
        )
        print(rag_note)

    print(f"Generating narrative from {input_path} ...")
    narrative = generate_ai_interpretation(
        ai_summary,
        strict=True,
        enabled_override=True,
        rag_context=rag_context,
    )
    if not narrative:
        raise SystemExit("Error: generation returned empty result.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Interpretive Narrative", "", f"Model: {AI_INTERPRETATION_MODEL}"]
    if rag_note:
        lines.extend(["", rag_note])
    lines.extend(["", narrative])
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Narrative written to {output_path}")


if __name__ == "__main__":
    main()
