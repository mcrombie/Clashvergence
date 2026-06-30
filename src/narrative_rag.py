from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any


DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "CLASHVERGENCE_RAG_EMBEDDING_MODEL",
    "text-embedding-3-small",
)
CACHE_VERSION = 1
LOCAL_EMBEDDING_DIMENSIONS = 256


SOURCE_CONFIGS = {
    "herodotus": {
        "filename": "herodotus_histories.txt",
        "label": "Herodotus, Histories",
        "chunk_words": 600,
        "overlap_words": 100,
    },
    "dunsany": {
        "filename": "dunsany_elfland_daughter.txt",
        "label": "Lord Dunsany, The King of Elfland's Daughter",
        "chunk_words": 350,
        "overlap_words": 75,
    },
}


EVENT_QUERY_ROUTES = {
    "succession_crisis": "king dies heir takes power legitimacy disputed claimant court crisis",
    "succession": "king dies heir takes power dynasty lineage succession custom",
    "religious_reform": "priests reform cult gods old names new worship altar shrine",
    "war_declared": "ships merchants harbor tribute sea trade war declared",
    "war_peace": "war ends settlement tribute oath subjugation surrender",
    "attack": "army attacks fortified crossing burned fields breached palisades",
    "unrest_secession": "province breaks away new name new banner revolt secession",
    "rebel_independence": "rebel state becomes independent parent kingdom divided",
    "diplomacy_rivalry": "envoys kneeling tribute oaths sworn and broken rivalry",
    "diplomacy_tributary": "tribute envoys kneeling gifts oath king subordinate",
    "diplomacy_alliance": "allies swear oaths coalition envoys common cause",
    "polity_advance": "realm endures centuries roads altars institutions continuity",
    "social_form_transition": "people leave wandering life and settle into institutions",
    "ideology_shift": "custom law council legitimacy old ways new rule",
    "regime_agitation": "claimant faction stirs unrest border province legitimacy",
    "migration_wave": "people travel road river crossing refuge distant country",
    "refugee_wave": "refugees flee burned fields roads shrines crowded ferries",
    "band_migration": "wandering band moves across country road frontier",
    "expand": "frontier watchposts survey markers new tax rolls claimed roads",
    "develop": "granaries roads markets storehouses tax rolls city works",
    "invest": "granaries roads markets storehouses tax rolls city works",
}


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    source: str
    source_label: str
    location: str
    start_char: int
    end_char: int
    text: str


@dataclass
class RagIndex:
    chunks: list[RagChunk]
    embeddings: list[list[float]]
    embedding_provider: str
    embedding_model: str
    corpus_dir: Path
    source_hashes: dict[str, str]


def build_rag_index(corpus_dir: Path, force_rebuild: bool = False) -> RagIndex:
    """Build or load the cached style RAG index for the configured corpus."""
    corpus_dir = Path(corpus_dir)
    cache_path = corpus_dir / "embeddings" / "style_index.json"
    source_hashes = _read_source_hashes(corpus_dir)

    if not force_rebuild and cache_path.exists():
        cached = _load_cached_index(cache_path, corpus_dir)
        if (
            cached is not None
            and cached.source_hashes == source_hashes
            and cached.embedding_model == DEFAULT_EMBEDDING_MODEL
        ):
            return cached

    chunks = _build_chunks(corpus_dir)
    if not chunks:
        raise FileNotFoundError(
            f"No source text found in {corpus_dir}. Run python corpus/fetch_corpus.py first."
        )

    texts = [chunk.text for chunk in chunks]
    embeddings, provider = _embed_texts(texts)
    index = RagIndex(
        chunks=chunks,
        embeddings=embeddings,
        embedding_provider=provider,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        corpus_dir=corpus_dir,
        source_hashes=source_hashes,
    )
    _write_cached_index(cache_path, index)
    return index


def retrieve_style_context(index: RagIndex, query: str, k: int = 5) -> list[str]:
    """Retrieve formatted style passages for one query."""
    ranked = _rank_chunks(index, query)
    return [_format_chunk(index.chunks[chunk_index]) for chunk_index, _score in ranked[: max(1, k)]]


def build_generation_queries(ai_summary: dict) -> list[str]:
    """Build event-aware retrieval queries from an AI interpretation summary."""
    queries: list[str] = []

    narrator_context = ai_summary.get("narrator_origin_context") or {}
    if narrator_context:
        queries.append(
            "ancestral first arrival family memory homeland old people founding "
            f"{narrator_context.get('ancestral_faction', '')} "
            f"{narrator_context.get('ancestral_homeland', '')} "
            f"{narrator_context.get('ancestral_religion', '')}"
        )
        for event in narrator_context.get("early_boueni_events", [])[:3]:
            brief = event.get("brief")
            if brief:
                queries.append(
                    "first loss secession ancestral homeland descendants "
                    + str(brief)
                )

    event_type_counts = ai_summary.get("event_type_counts", {})
    for event_type, query in EVENT_QUERY_ROUTES.items():
        if int(event_type_counts.get(event_type, 0) or 0) > 0:
            queries.append(query)

    for episode in ai_summary.get("centerpiece_episodes", [])[:8]:
        event_type = str(episode.get("type", ""))
        routed = EVENT_QUERY_ROUTES.get(event_type)
        brief = str(episode.get("brief", ""))
        region = str(episode.get("region_display_name") or "")
        actors = " ".join(
            str(value)
            for value in [
                episode.get("actor_narrative") or episode.get("actor"),
                episode.get("counterpart_narrative") or episode.get("counterpart"),
            ]
            if value
        )
        query = " ".join(value for value in [routed, actors, region, brief] if value)
        if query:
            queries.append(query)

    text_sections = [
        *ai_summary.get("phase_summaries", [])[:3],
        *ai_summary.get("turning_points", [])[:5],
        *ai_summary.get("structural_drivers", [])[:4],
    ]
    joined = " ".join(str(section) for section in text_sections).lower()
    keyword_routes = [
        (("succession", "claimant", "dynasty", "heir"), EVENT_QUERY_ROUTES["succession_crisis"]),
        (("religion", "reform", "cult", "altar"), EVENT_QUERY_ROUTES["religious_reform"]),
        (("trade", "naval", "blockade", "harbor"), EVENT_QUERY_ROUTES["war_declared"]),
        (("tributary", "tribute", "subordinate"), EVENT_QUERY_ROUTES["diplomacy_tributary"]),
        (("secession", "breakaway", "rebel"), EVENT_QUERY_ROUTES["unrest_secession"]),
        (("migration", "refugee", "fled"), EVENT_QUERY_ROUTES["refugee_wave"]),
    ]
    for keywords, query in keyword_routes:
        if any(keyword in joined for keyword in keywords):
            queries.append(query)

    world_identity = ai_summary.get("world_identity", {})
    world_name = world_identity.get("world_name")
    era_name = world_identity.get("era_name")
    if world_name or era_name:
        queries.append(
            f"realm endures centuries roads altars continuity {world_name or ''} {era_name or ''}".strip()
        )

    place_names = _extract_place_names(ai_summary)
    if place_names:
        queries.append(
            "river crossing place mountains coast geography frontier "
            + " ".join(place_names[:8])
        )

    if not queries:
        queries.append("kingdoms rise and fall roads altars tribute succession war")

    return _dedupe_preserving_order(queries)[:10]


def retrieve_syncretic_style_context(
    index: RagIndex,
    queries: list[str],
    *,
    k_per_query: int = 3,
    max_passages: int = 9,
) -> list[str]:
    """Retrieve a blended passage set across all queries, keeping both source registers."""
    if not index.chunks:
        return []

    selected: list[int] = []
    seen: set[str] = set()
    for query in queries or ["kingdoms rise and fall roads altars tribute succession war"]:
        for chunk_index, _score in _rank_chunks(index, query)[: max(1, k_per_query)]:
            chunk_id = index.chunks[chunk_index].chunk_id
            if chunk_id in seen:
                continue
            selected.append(chunk_index)
            seen.add(chunk_id)
            if len(selected) >= max_passages:
                break
        if len(selected) >= max_passages:
            break

    available_sources = {chunk.source for chunk in index.chunks}
    selected_sources = {index.chunks[chunk_index].source for chunk_index in selected}
    missing_sources = sorted(available_sources - selected_sources)
    for source in missing_sources:
        query = "mythic names roads altars kings customs sea history"
        source_ranked = [
            chunk_index
            for chunk_index, _score in _rank_chunks(index, query)
            if index.chunks[chunk_index].source == source
            and index.chunks[chunk_index].chunk_id not in seen
        ]
        if not source_ranked:
            continue
        insert_at = max(0, min(len(selected), max_passages - 1))
        if len(selected) >= max_passages:
            removed = selected.pop()
            seen.discard(index.chunks[removed].chunk_id)
        selected.insert(insert_at, source_ranked[0])
        seen.add(index.chunks[source_ranked[0]].chunk_id)

    return [_format_chunk(index.chunks[chunk_index]) for chunk_index in selected[:max_passages]]


def build_style_context_for_summary(
    ai_summary: dict,
    *,
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    force_rebuild: bool = False,
    max_passages: int = 9,
) -> list[str]:
    index = build_rag_index(corpus_dir, force_rebuild=force_rebuild)
    queries = build_generation_queries(ai_summary)
    return retrieve_syncretic_style_context(
        index,
        queries,
        max_passages=max_passages,
    )


def _read_source_hashes(corpus_dir: Path) -> dict[str, str]:
    hashes = {}
    for config in SOURCE_CONFIGS.values():
        path = corpus_dir / config["filename"]
        if path.exists():
            hashes[config["filename"]] = _sha256(path.read_bytes())
    return hashes


def _build_chunks(corpus_dir: Path) -> list[RagChunk]:
    chunks: list[RagChunk] = []
    for source, config in SOURCE_CONFIGS.items():
        path = corpus_dir / config["filename"]
        if not path.exists():
            continue
        text = _normalize_text(path.read_text(encoding="utf-8", errors="replace"))
        chunks.extend(
            _chunk_source_text(
                source=source,
                source_label=config["label"],
                text=text,
                chunk_words=int(config["chunk_words"]),
                overlap_words=int(config["overlap_words"]),
            )
        )
    return chunks


def _chunk_source_text(
    *,
    source: str,
    source_label: str,
    text: str,
    chunk_words: int,
    overlap_words: int,
) -> list[RagChunk]:
    word_matches = list(re.finditer(r"\S+", text))
    if not word_matches:
        return []

    step = max(1, chunk_words - overlap_words)
    chunks: list[RagChunk] = []
    chunk_number = 1
    for start_word in range(0, len(word_matches), step):
        end_word = min(len(word_matches), start_word + chunk_words)
        if end_word <= start_word:
            break
        start_char = word_matches[start_word].start()
        end_char = word_matches[end_word - 1].end()
        chunk_text = text[start_char:end_char].strip()
        if len(chunk_text.split()) < max(40, chunk_words // 5):
            continue
        location = f"chunk {chunk_number}"
        chunks.append(
            RagChunk(
                chunk_id=f"{source}:{chunk_number}",
                source=source,
                source_label=source_label,
                location=location,
                start_char=start_char,
                end_char=end_char,
                text=chunk_text,
            )
        )
        chunk_number += 1
        if end_word == len(word_matches):
            break
    return chunks


def _embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    if os.getenv("OPENAI_API_KEY"):
        return _embed_texts_openai(texts), "openai"
    return [_local_embedding(text) for text in texts], "local-hash"


def _embed_query(index: RagIndex, query: str) -> list[float]:
    if index.embedding_provider == "openai":
        return _embed_texts_openai([query])[0]
    return _local_embedding(query)


def _embed_texts_openai(texts: list[str]) -> list[list[float]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The openai package is required for OpenAI RAG embeddings.") from exc

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    embeddings: list[list[float]] = []
    batch_size = 96
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(
            model=DEFAULT_EMBEDDING_MODEL,
            input=batch,
        )
        response_data = sorted(response.data, key=lambda item: item.index)
        embeddings.extend([list(item.embedding) for item in response_data])
    return embeddings


def _local_embedding(text: str) -> list[float]:
    vector = [0.0] * LOCAL_EMBEDDING_DIMENSIONS
    tokens = re.findall(r"[a-zA-Z][a-zA-Z']+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % LOCAL_EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[bucket] += sign
    return _normalize_vector(vector)


def _rank_chunks(index: RagIndex, query: str) -> list[tuple[int, float]]:
    query_embedding = _normalize_vector(_embed_query(index, query))
    ranked = [
        (chunk_index, _cosine_similarity(query_embedding, embedding))
        for chunk_index, embedding in enumerate(index.embeddings)
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    length = min(len(a), len(b))
    dot = sum(a[index] * b[index] for index in range(length))
    norm_a = math.sqrt(sum(value * value for value in a[:length]))
    norm_b = math.sqrt(sum(value * value for value in b[:length]))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _format_chunk(chunk: RagChunk) -> str:
    text = re.sub(r"\s+", " ", chunk.text).strip()
    return f"[{chunk.source_label}, {chunk.location}] {text}"


def _load_cached_index(cache_path: Path, corpus_dir: Path) -> RagIndex | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if int(payload.get("cache_version", 0)) != CACHE_VERSION:
        return None
    chunks = [RagChunk(**entry) for entry in payload.get("chunks", [])]
    embeddings = payload.get("embeddings", [])
    if len(chunks) != len(embeddings):
        return None
    return RagIndex(
        chunks=chunks,
        embeddings=embeddings,
        embedding_provider=str(payload.get("embedding_provider", "local-hash")),
        embedding_model=str(payload.get("embedding_model", DEFAULT_EMBEDDING_MODEL)),
        corpus_dir=corpus_dir,
        source_hashes=dict(payload.get("source_hashes", {})),
    )


def _write_cached_index(cache_path: Path, index: RagIndex) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cache_version": CACHE_VERSION,
        "embedding_provider": index.embedding_provider,
        "embedding_model": index.embedding_model,
        "source_hashes": index.source_hashes,
        "chunks": [asdict(chunk) for chunk in index.chunks],
        "embeddings": index.embeddings,
    }
    cache_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _extract_place_names(ai_summary: dict) -> list[str]:
    names: list[str] = []
    for row in ai_summary.get("key_event_digest", [])[:20]:
        name = row.get("region_display_name")
        if name:
            names.append(str(name))
    for row in ai_summary.get("centerpiece_episodes", [])[:8]:
        name = row.get("region_display_name")
        if name:
            names.append(str(name))
    return _dedupe_preserving_order(names)


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        normalized = re.sub(r"\s+", " ", value).strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
