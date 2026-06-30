"""Fetch the public-domain style corpus for interpretive narrative RAG.

Run from the repository root:
    python corpus/fetch_corpus.py
"""
from __future__ import annotations

from pathlib import Path
import re
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent

SOURCES = {
    "herodotus_histories.txt": [
        "https://www.gutenberg.org/cache/epub/2707/pg2707.txt",
        "https://www.gutenberg.org/files/2707/2707-0.txt",
        "https://www.gutenberg.org/files/2707/2707.txt",
    ],
    "dunsany_elfland_daughter.txt": [
        "https://www.gutenberg.org/cache/epub/61077/pg61077.txt",
        "https://www.gutenberg.org/files/61077/61077-0.txt",
        "https://www.gutenberg.org/files/61077/61077.txt",
    ],
}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for filename, urls in SOURCES.items():
        text = fetch_first_available(urls)
        cleaned = strip_gutenberg_boilerplate(text)
        output_path = ROOT / filename
        output_path.write_text(cleaned, encoding="utf-8")
        print(f"Wrote {output_path} ({len(cleaned.split())} words)")


def fetch_first_available(urls: list[str]) -> str:
    errors = []
    for url in urls:
        try:
            request = Request(
                url,
                headers={"User-Agent": "Clashvergence narrative corpus fetcher"},
            )
            with urlopen(request, timeout=60) as response:
                raw = response.read()
            return raw.decode("utf-8", errors="replace")
        except (OSError, URLError) as exc:
            errors.append(f"{url}: {exc}")
    raise RuntimeError("Could not fetch source text:\n" + "\n".join(errors))


def strip_gutenberg_boilerplate(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    start_match = re.search(
        r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if start_match:
        text = text[start_match.end() :]

    end_match = re.search(
        r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if end_match:
        text = text[: end_match.start()]

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


if __name__ == "__main__":
    main()
