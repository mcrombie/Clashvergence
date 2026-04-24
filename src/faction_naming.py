from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import asdict
from difflib import SequenceMatcher

from src.ai_interpretation import _extract_response_text, load_local_env_file
from src.models import FactionIdentity, LanguageProfile


load_local_env_file()


AI_FACTION_NAMING_MODEL = os.getenv("CLASHVERGENCE_FACTION_NAME_MODEL", "gpt-5.4-mini")
AI_FACTION_NAMING_TEMPERATURE = float(
    os.getenv("CLASHVERGENCE_FACTION_NAME_TEMPERATURE", "0.5")
)
AI_FACTION_NAMING_MAX_ATTEMPTS = max(
    1,
    int(os.getenv("CLASHVERGENCE_FACTION_NAME_MAX_ATTEMPTS", "3")),
)
AI_FACTION_NAMING_ENABLED = os.getenv(
    "CLASHVERGENCE_ENABLE_AI_FACTION_NAMING",
    "0",
).lower() in {"1", "true", "yes", "on"}

DEFAULT_POLITY_TIER = "tribe"
DEFAULT_GOVERNMENT_FORM = "council"

SOURCE_TRADITIONS = {
    "roman": {
        "label": "Roman and Gallic ethnonyms",
        "primary_sources": [
            "Julius Caesar, De Bello Gallico",
            "Tacitus, Germania",
            "Livy, Ab Urbe Condita",
        ],
        "seed_names": [
            "Arverni",
            "Aedui",
            "Sequani",
            "Helvetii",
            "Veneti",
            "Carnutes",
            "Lingones",
            "Remi",
            "Senones",
            "Batavi",
        ],
        "onsets": ["al", "ar", "bel", "car", "dur", "hel", "ling", "mar", "nor", "sev", "tal", "ver"],
        "middles": ["ae", "an", "er", "ev", "il", "on", "or", "ut", "av", "en", "ur", "ed"],
        "suffixes": ["and", "ar", "en", "ent", "ern", "ev", "on", "or", "os", "um", "un", "yn"],
    },
    "persian": {
        "label": "Achaemenid and Iranian ethnonyms",
        "primary_sources": [
            "Herodotus, Histories",
            "Behistun Inscription",
            "Xenophon, Cyropaedia",
        ],
        "seed_names": [
            "Persa",
            "Mada",
            "Parthava",
            "Bakhtri",
            "Saka",
            "Dahae",
            "Arachosia",
            "Drangiana",
            "Hyrcania",
            "Carmania",
        ],
        "onsets": ["akh", "ara", "ard", "bakh", "car", "dar", "far", "hyr", "par", "sak", "var", "zar"],
        "middles": ["a", "ae", "ar", "ax", "eh", "ir", "or", "th", "ush", "ava", "ian", "yra"],
        "suffixes": ["ad", "ae", "akh", "an", "and", "ar", "ash", "ava", "ax", "ir", "or", "ush"],
    },
    "chinese": {
        "label": "Classical Chinese state and people names",
        "primary_sources": [
            "Sima Qian, Shiji",
            "Zuo Zhuan",
            "Guoyu",
        ],
        "seed_names": [
            "Qin",
            "Chu",
            "Qi",
            "Wei",
            "Han",
            "Zhao",
            "Yan",
            "Yue",
            "Liang",
            "Jin",
        ],
        "onsets": ["an", "chu", "han", "jin", "lan", "lin", "qin", "shan", "wei", "yan", "yue", "zhao"],
        "middles": ["a", "ai", "en", "i", "ia", "in", "iu", "o", "ua", "ui", "un", "y"],
        "suffixes": ["an", "en", "ei", "ian", "in", "ing", "iu", "ong", "uan", "un", "uo", "yn"],
    },
}

REAL_NAME_BLOCKLIST = sorted({
    normalized
    for tradition in SOURCE_TRADITIONS.values()
    for normalized in tradition["seed_names"]
})

WORLD_LANGUAGE_SHIFT_SETS = {
    "bright_vowels": (("a", "e"), ("o", "u")),
    "round_vowels": (("e", "i"), ("a", "o")),
    "soften_velars": (("k", "h"), ("g", "gh")),
    "soften_stops": (("t", "s"), ("d", "z")),
    "liquid_shift": (("r", "l"),),
    "nasal_endings": (("an", "en"), ("on", "un")),
    "open_endings": (("nd", "na"), ("nt", "ne"), ("or", "ora")),
    "trim_endings": (("ara", "ar"), ("ium", "im"), ("ush", "ur")),
}

SEMANTIC_ROOT_DOMAINS = (
    "settlement",
    "river",
    "forest",
    "hill",
    "plain",
    "marsh",
    "sea",
    "border",
    "market",
    "fort",
    "sacred",
    "sun",
    "ancestor",
    "ruler",
    "dynasty",
)

SEMANTIC_ROOT_PATTERNS = {
    "settlement": ("compact", "fragment_tail"),
    "river": ("flowing", "compact"),
    "forest": ("leafy", "compact"),
    "hill": ("stone", "compact"),
    "plain": ("open", "compact"),
    "marsh": ("flowing", "fragment_tail"),
    "sea": ("open", "fragment_tail"),
    "border": ("hard", "compact"),
    "market": ("compact", "open"),
    "fort": ("hard", "fragment_tail"),
    "sacred": ("open", "fragment_tail"),
    "sun": ("open", "compact"),
    "ancestor": ("fragment_tail", "compact"),
    "ruler": ("hard", "compact"),
    "dynasty": ("fragment_tail", "open"),
}

AI_FACTION_NAMING_SYSTEM_PROMPT = """You create one original alternative-history culture name inspired by ancient primary-source naming traditions.

Rules:
- Output exactly one culture base name and nothing else.
- The name must be a single word in Title Case.
- It should sound plausible beside ancient Roman, Persian, and Chinese ethnonyms without copying any one directly.
- Do not output a real historical ethnonym, kingdom, tribe, dynasty, or state name.
- Avoid spaces, punctuation, numbers, articles, and government words like Tribe, League, Kingdom, Empire, Republic.
- Keep it pronounceable in English.
- Prefer 6 to 11 letters.
- Make it feel like the name of a people or culture, not a person.
- Avoid overly jagged spellings with too many rare letters like q, x, z, or j unless the result still sounds smooth aloud.
- Prefer names that look natural in English transliteration.
"""


def is_ai_faction_naming_enabled():
    return AI_FACTION_NAMING_ENABLED and bool(os.getenv("OPENAI_API_KEY"))


def get_faction_internal_id(index: int) -> str:
    return f"Faction{index}"


def get_configured_faction_internal_ids(num_factions: int) -> list[str]:
    if num_factions < 1:
        raise ValueError("num_factions must be at least 1.")
    return [get_faction_internal_id(index) for index in range(1, num_factions + 1)]


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z]", "", value.lower())


def _stable_random(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _blend_fragments(rng: random.Random, first: str, second: str) -> str:
    blend_size = min(len(first), max(2, len(first) // 2 + rng.randint(0, 1)))
    tail_start = min(len(second), max(1, len(second) // 2 - rng.randint(0, 1)))
    return first[:blend_size] + second[tail_start:]


def _extract_seed_fragments(seed_name: str) -> list[str]:
    normalized = _normalize_name(seed_name)
    if len(normalized) < 4:
        return [normalized]

    fragments = [
        normalized[:3],
        normalized[:4],
        normalized[-3:],
        normalized[-4:],
        normalized[1:4],
        normalized[max(0, len(normalized) // 2 - 2): max(3, len(normalized) // 2 + 2)],
    ]

    unique_fragments: list[str] = []
    for fragment in fragments:
        if len(fragment) >= 2 and fragment not in unique_fragments:
            unique_fragments.append(fragment)
    return unique_fragments


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _collapse_repeated_letters(value: str) -> str:
    return re.sub(r"(.)\1{2,}", r"\1\1", value)


def _clean_letter_transitions(value: str) -> str:
    value = value.lower()

    for pattern, replacement in (
        ("qj", "qu"),
        ("jq", "qu"),
        ("yy", "y"),
        ("ww", "w"),
        ("iii", "ii"),
        ("uuu", "uu"),
        ("aeo", "ae"),
        ("eoa", "ea"),
        ("iua", "ia"),
    ):
        value = value.replace(pattern, replacement)

    value = re.sub(r"([bcdfghjklmnpqrstvwxyz]{4,})", lambda match: match.group(0)[:3], value)
    value = re.sub(r"([aeiouy]{3,})", lambda match: match.group(0)[:2], value)
    return _collapse_repeated_letters(value)


def _tidy_candidate(candidate: str) -> str:
    candidate = re.sub(r"[^a-z]", "", candidate.lower())
    candidate = _clean_letter_transitions(candidate)
    if len(candidate) < 5:
        candidate += "an"
    if len(candidate) > 11:
        candidate = candidate[:11]
    return candidate.capitalize()


def _is_too_similar(candidate: str, blocked_names: list[str], threshold: float = 0.8) -> bool:
    normalized = _normalize_name(candidate)
    if not normalized:
        return True

    for blocked in blocked_names:
        blocked_normalized = _normalize_name(blocked)
        if normalized == blocked_normalized:
            return True
        if abs(len(normalized) - len(blocked_normalized)) <= 2:
            ratio = SequenceMatcher(None, normalized, blocked_normalized).ratio()
            if ratio >= threshold:
                return True
    return False


def _generate_source_fused_candidate(index: int, naming_seed: str, attempt: int = 0) -> tuple[str, list[str], list[str]]:
    tradition_keys = sorted(SOURCE_TRADITIONS)
    rng = _stable_random(f"{naming_seed}:{index}:{attempt}")

    first_key = tradition_keys[(index + attempt) % len(tradition_keys)]
    second_key = tradition_keys[(index + attempt + 1 + rng.randint(0, len(tradition_keys) - 1)) % len(tradition_keys)]
    if first_key == second_key:
        second_key = tradition_keys[(tradition_keys.index(first_key) + 1) % len(tradition_keys)]

    first = SOURCE_TRADITIONS[first_key]
    second = SOURCE_TRADITIONS[second_key]

    onset = rng.choice(first["onsets"])
    middle = rng.choice(second["middles"])
    suffix = rng.choice(first["suffixes"] + second["suffixes"])
    seed_a = rng.choice(first["seed_names"])
    seed_b = rng.choice(second["seed_names"])
    seed_a_fragments = _extract_seed_fragments(seed_a)
    seed_b_fragments = _extract_seed_fragments(seed_b)

    fused = _blend_fragments(rng, _normalize_name(seed_a), _normalize_name(seed_b))
    fragment_a = rng.choice(seed_a_fragments)
    fragment_b = rng.choice(seed_b_fragments)
    pattern = rng.choice(("onset_fused_suffix", "seed_blend", "hybrid_compound", "softened_seed"))

    if pattern == "onset_fused_suffix":
        candidate = onset + middle + fused[-max(2, len(fused) // 2):] + suffix[: rng.randint(1, len(suffix))]
    elif pattern == "seed_blend":
        candidate = fragment_a + middle + fragment_b[-max(2, len(fragment_b) - 1):]
    elif pattern == "hybrid_compound":
        candidate = onset + fragment_b[: rng.randint(2, len(fragment_b))] + suffix
    else:
        candidate = fragment_a[: rng.randint(2, len(fragment_a))] + fused[max(1, len(fused) // 3):] + suffix[:2]

    if rng.random() < 0.45:
        candidate += rng.choice(["a", "e", "i", "o", "u", "an", "en", "ar"])

    return _tidy_candidate(candidate), [first_key, second_key], [seed_a, seed_b]


def _normalize_family_count(num_factions: int) -> int:
    if num_factions <= 1:
        return 1
    return max(2, min(num_factions, 2 + (num_factions // 3)))


def _apply_replacements(value: str, replacements: tuple[tuple[str, str], ...]) -> str:
    normalized = _normalize_name(value)
    if not normalized:
        return normalized
    for source, target in replacements:
        normalized = normalized.replace(source, target)
    return _clean_letter_transitions(normalized)


def _mutate_family_pool(
    values: list[str],
    replacements: tuple[tuple[str, str], ...],
    *,
    limit: int,
    minimum_length: int,
    maximum_length: int,
) -> list[str]:
    mutated: list[str] = []
    for value in values:
        changed = _apply_replacements(value, replacements)
        if minimum_length <= len(changed) <= maximum_length:
            mutated.append(changed)
        normalized = _normalize_name(value)
        if minimum_length <= len(normalized) <= maximum_length:
            mutated.append(normalized)
    return _dedupe_preserving_order(mutated)[:limit]


def _build_semantic_root_token(
    family: dict,
    concept: str,
    *,
    variant_index: int,
    naming_seed: str,
) -> str:
    rng = _stable_random(
        f"{naming_seed}:semantic_root:{family['family_name']}:{concept}:{variant_index}"
    )
    onsets = family["onsets"] or ["al", "dar", "nor"]
    middles = family["middles"] or ["a", "e", "ia"]
    suffixes = family["suffixes"] or ["an", "ar", "or"]
    fragments = family["seed_fragments"] or _extract_seed_fragments(family["family_name"])
    pattern = rng.choice(SEMANTIC_ROOT_PATTERNS.get(concept, ("compact",)))
    onset = rng.choice(onsets)
    middle = rng.choice(middles)
    suffix = rng.choice(suffixes)
    fragment = rng.choice(fragments)

    if pattern == "fragment_tail":
        token = (
            fragment[: max(2, min(4, len(fragment)))]
            + middle
            + suffix[-max(2, min(3, len(suffix))):]
        )
    elif pattern == "flowing":
        token = onset[: max(2, min(3, len(onset)))] + middle + fragment[-max(2, min(4, len(fragment))):]
    elif pattern == "leafy":
        token = fragment[: max(2, min(3, len(fragment)))] + middle + suffix[: max(2, min(3, len(suffix)))]
    elif pattern == "stone":
        token = onset + fragment[max(1, len(fragment) // 3): max(3, len(fragment) // 3 + 3)]
    elif pattern == "open":
        token = onset[: max(1, min(2, len(onset)))] + middle + suffix
    elif pattern == "hard":
        token = onset + suffix
    else:
        token = onset[: max(2, min(3, len(onset)))] + middle + suffix[: max(2, min(3, len(suffix)))]

    normalized = _clean_letter_transitions(token)
    if len(normalized) < 3:
        normalized = _clean_letter_transitions(normalized + suffix)
    return normalized[:8]


def _build_family_lexical_roots(family: dict, naming_seed: str) -> dict[str, list[str]]:
    lexical_roots: dict[str, list[str]] = {}
    for concept in SEMANTIC_ROOT_DOMAINS:
        roots: list[str] = []
        for variant_index in range(2):
            token = _build_semantic_root_token(
                family,
                concept,
                variant_index=variant_index,
                naming_seed=naming_seed,
            )
            if token:
                roots.append(token)
        lexical_roots[concept] = _dedupe_preserving_order(roots)[:2]
    return lexical_roots


def _build_proto_language_family(
    family_index: int,
    naming_seed: str,
    existing_family_names: list[str],
) -> dict:
    family_name, traditions, inspirations, candidate_pool = _generate_deterministic_culture_name(
        index=family_index + 97,
        naming_seed=f"{naming_seed}:proto_family",
        existing_names=existing_family_names,
    )
    rng = _stable_random(f"{naming_seed}:proto_family:{family_index}:{family_name}")
    shift_keys = sorted(WORLD_LANGUAGE_SHIFT_SETS)
    first_shift = shift_keys[(family_index + rng.randint(0, len(shift_keys) - 1)) % len(shift_keys)]
    second_shift = shift_keys[(family_index + 2 + rng.randint(0, len(shift_keys) - 1)) % len(shift_keys)]
    if second_shift == first_shift:
        second_shift = shift_keys[(shift_keys.index(first_shift) + 1) % len(shift_keys)]
    selected_shift_keys = [first_shift, second_shift]
    replacements = tuple(
        pair
        for shift_key in selected_shift_keys
        for pair in WORLD_LANGUAGE_SHIFT_SETS[shift_key]
    )

    tradition_onsets: list[str] = []
    tradition_middles: list[str] = []
    tradition_suffixes: list[str] = []
    tradition_seeds: list[str] = []
    style_notes: list[str] = []
    for tradition_key in traditions:
        tradition = SOURCE_TRADITIONS[tradition_key]
        tradition_onsets.extend(tradition["onsets"][:10])
        tradition_middles.extend(tradition["middles"][:10])
        tradition_suffixes.extend(tradition["suffixes"][:10])
        tradition_seeds.extend(tradition["seed_names"][:8])
        style_notes.append(tradition["label"])

    family_fragments = _extract_seed_fragments(family_name)
    family_onsets = _mutate_family_pool(
        tradition_onsets + family_fragments,
        replacements,
        limit=14,
        minimum_length=2,
        maximum_length=5,
    )
    family_middles = _mutate_family_pool(
        tradition_middles + family_fragments,
        replacements,
        limit=14,
        minimum_length=1,
        maximum_length=4,
    )
    family_suffixes = _mutate_family_pool(
        tradition_suffixes + family_fragments,
        replacements,
        limit=14,
        minimum_length=2,
        maximum_length=5,
    )
    family_seed_fragments = _dedupe_preserving_order(
        [
            *_extract_seed_fragments(family_name),
            *[_apply_replacements(seed_name, replacements) for seed_name in tradition_seeds],
            *[_apply_replacements(seed_name, replacements) for seed_name in inspirations],
            *[_apply_replacements(seed_name, replacements) for seed_name in candidate_pool[:4]],
        ]
    )[:18]
    provisional_family = {
        "family_name": family_name,
        "onsets": family_onsets or ["al", "ar", "bel", "dar"],
        "middles": family_middles or ["a", "e", "ia", "or"],
        "suffixes": family_suffixes or ["an", "ar", "en", "or"],
        "seed_fragments": family_seed_fragments or _extract_seed_fragments(family_name),
    }

    return {
        "family_name": family_name,
        "traditions": traditions,
        "inspirations": inspirations,
        "candidate_pool": candidate_pool[:8],
        "onsets": provisional_family["onsets"],
        "middles": provisional_family["middles"],
        "suffixes": provisional_family["suffixes"],
        "seed_fragments": provisional_family["seed_fragments"],
        "lexical_roots": _build_family_lexical_roots(provisional_family, naming_seed),
        "style_notes": style_notes[:4],
        "shift_keys": selected_shift_keys,
    }


def _generate_world_language_families(num_factions: int, naming_seed: str) -> list[dict]:
    family_count = _normalize_family_count(num_factions)
    families: list[dict] = []
    existing_family_names: list[str] = []
    for family_index in range(family_count):
        family = _build_proto_language_family(
            family_index,
            naming_seed,
            existing_family_names,
        )
        families.append(family)
        existing_family_names.append(family["family_name"])
    return families


def _get_assigned_language_family(index: int, families: list[dict], naming_seed: str) -> dict:
    if not families:
        raise ValueError("Expected at least one language family.")
    if len(families) == 1:
        return families[0]
    rng = _stable_random(f"{naming_seed}:family_assignment:{index}")
    base_position = (index - 1) % len(families)
    offset = rng.randint(0, min(1, len(families) - 1))
    return families[(base_position + offset) % len(families)]


def _generate_family_candidate(
    index: int,
    naming_seed: str,
    family: dict,
    attempt: int = 0,
) -> tuple[str, list[str], list[str]]:
    rng = _stable_random(f"{naming_seed}:family_candidate:{family['family_name']}:{index}:{attempt}")
    family_fragments = family["seed_fragments"] or _extract_seed_fragments(family["family_name"])
    onset = rng.choice(family["onsets"])
    middle = rng.choice(family["middles"])
    suffix = rng.choice(family["suffixes"])
    fragment_a = rng.choice(family_fragments)
    fragment_b = rng.choice(family_fragments)
    pattern = rng.choice(("family_root", "fragment_compound", "proto_echo", "softened_lineage"))

    if pattern == "family_root":
        candidate = onset + middle + suffix
    elif pattern == "fragment_compound":
        candidate = fragment_a[: rng.randint(2, len(fragment_a))] + middle + fragment_b[-max(2, min(4, len(fragment_b))):]
    elif pattern == "proto_echo":
        proto_root = _normalize_name(family["family_name"])
        candidate = proto_root[: max(2, min(4, len(proto_root)))] + middle + suffix
    else:
        proto_root = _normalize_name(family["family_name"])
        candidate = onset + proto_root[max(1, len(proto_root) // 3): max(3, len(proto_root) // 3 + 3)] + suffix

    if rng.random() < 0.4:
        candidate += rng.choice(["a", "e", "i", "o", "an", "en", "ar", "or"])

    return _tidy_candidate(candidate), list(family["traditions"]), list(family["inspirations"])


def _build_language_profile(
    culture_name: str,
    family: dict,
    candidate_pool: list[str],
) -> LanguageProfile:
    onsets: list[str] = []
    middles: list[str] = []
    suffixes: list[str] = []
    seed_fragments: list[str] = []
    style_notes: list[str] = []

    onsets.extend(family["onsets"][:12])
    middles.extend(family["middles"][:12])
    suffixes.extend(family["suffixes"][:12])
    style_notes.extend(family["style_notes"][:4])

    for seed_name in family["inspirations"] + family["candidate_pool"][:4] + candidate_pool[:4] + [family["family_name"], culture_name]:
        seed_fragments.extend(_extract_seed_fragments(seed_name))

    normalized_culture = _normalize_name(culture_name)
    if len(normalized_culture) >= 3:
        onsets.append(normalized_culture[:3])
        suffixes.append(normalized_culture[-3:])

    lexical_roots = {
        concept: _dedupe_preserving_order(
            list(family.get("lexical_roots", {}).get(concept, []))
        )[:2]
        for concept in SEMANTIC_ROOT_DOMAINS
    }
    culture_fragments = _extract_seed_fragments(culture_name)
    culture_extensions = {
        "ruler": culture_fragments[:1],
        "dynasty": culture_fragments[-1:],
        "ancestor": culture_fragments[:1],
        "settlement": culture_fragments[-1:],
    }
    for concept, extra_roots in culture_extensions.items():
        lexical_roots[concept] = _dedupe_preserving_order(
            lexical_roots.get(concept, []) + extra_roots
        )[:3]

    return LanguageProfile(
        family_name=family["family_name"],
        onsets=_dedupe_preserving_order(onsets)[:12],
        middles=_dedupe_preserving_order(middles)[:12],
        suffixes=_dedupe_preserving_order(suffixes)[:12],
        seed_fragments=_dedupe_preserving_order(seed_fragments)[:16],
        lexical_roots=lexical_roots,
        style_notes=style_notes[:4],
    )


def _count_vowels(value: str) -> int:
    return sum(1 for character in value.lower() if character in "aeiouy")


def _score_candidate_quality(candidate: str) -> float:
    normalized = _normalize_name(candidate)
    if not normalized:
        return -999.0

    vowel_count = _count_vowels(normalized)
    consonant_count = len(normalized) - vowel_count
    vowel_ratio = vowel_count / max(1, len(normalized))

    score = 0.0
    score -= abs(len(normalized) - 8) * 0.25
    score -= abs(vowel_ratio - 0.42) * 2.5

    if normalized.endswith(("a", "an", "ar", "and", "en", "ia", "ian", "in", "ion", "on", "or", "os", "thi", "un")):
        score += 0.8
    if re.search(r"[aeiouy]{2}", normalized):
        score += 0.35
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{3}", normalized):
        score -= 0.35
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{4}", normalized):
        score -= 1.0

    awkward_clusters = (
        "akhm",
        "hmg",
        "rrtn",
        "tnet",
        "xn",
        "qz",
        "zx",
        "jq",
        "qj",
        "vvr",
        "yy",
    )
    for cluster in awkward_clusters:
        if cluster in normalized:
            score -= 1.4

    rare_letter_count = sum(normalized.count(letter) for letter in "qxzj")
    score -= rare_letter_count * 0.2
    if rare_letter_count >= 3:
        score -= 0.8
    score -= len(re.findall(r"q(?!u)", normalized)) * 0.9

    repeated_pairs = len(re.findall(r"(..).*\1", normalized))
    score += min(0.7, repeated_pairs * 0.15)

    if consonant_count > vowel_count + 3:
        score -= 0.9

    return score


def _generate_deterministic_culture_name(index: int, naming_seed: str, existing_names: list[str]) -> tuple[str, list[str], list[str], list[str]]:
    blocked = REAL_NAME_BLOCKLIST + existing_names
    candidates: list[tuple[float, str, list[str], list[str]]] = []

    for attempt in range(48):
        candidate, traditions, inspirations = _generate_source_fused_candidate(index, naming_seed, attempt=attempt)
        if _is_too_similar(candidate, blocked):
            continue
        candidates.append((
            _score_candidate_quality(candidate),
            candidate,
            traditions,
            inspirations,
        ))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, best_candidate, traditions, inspirations = candidates[0]
        candidate_pool = [candidate for _score, candidate, _traditions, _inspirations in candidates[:8]]
        return best_candidate, traditions, inspirations, candidate_pool

    fallback_base, fallback_traditions, fallback_inspirations = _generate_source_fused_candidate(
        index,
        naming_seed,
        attempt=99,
    )
    fallback = f"{fallback_base}{chr(65 + (index - 1) % 26)}"
    return fallback, fallback_traditions, fallback_inspirations, [fallback]


def _generate_family_scoped_culture_name(
    index: int,
    naming_seed: str,
    family: dict,
    existing_names: list[str],
) -> tuple[str, list[str], list[str], list[str]]:
    blocked = REAL_NAME_BLOCKLIST + existing_names + [family["family_name"]]
    candidates: list[tuple[float, str, list[str], list[str]]] = []

    for attempt in range(48):
        candidate, traditions, inspirations = _generate_family_candidate(
            index,
            naming_seed,
            family,
            attempt=attempt,
        )
        if _is_too_similar(candidate, blocked):
            continue
        candidates.append((
            _score_candidate_quality(candidate),
            candidate,
            traditions,
            inspirations,
        ))

    if candidates:
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _best_score, best_candidate, traditions, inspirations = candidates[0]
        candidate_pool = [candidate for _score, candidate, _traditions, _inspirations in candidates[:8]]
        return best_candidate, traditions, inspirations, candidate_pool

    fallback = _tidy_candidate(f"{family['family_name']}{chr(65 + (index - 1) % 26)}")
    return fallback, list(family["traditions"]), list(family["inspirations"]), [fallback]


def _validate_ai_candidate(candidate: str, blocked_names: list[str]) -> str | None:
    cleaned = re.sub(r"[^A-Za-z]", "", candidate or "")
    if not cleaned:
        return None
    if len(cleaned) < 5 or len(cleaned) > 11:
        return None
    cleaned = cleaned.capitalize()
    if _is_too_similar(cleaned, blocked_names):
        return None
    return cleaned


def _passes_ai_quality_gate(candidate: str, fallback_candidate: str) -> bool:
    ai_score = _score_candidate_quality(candidate)
    fallback_score = _score_candidate_quality(fallback_candidate)

    minimum_ai_score = -0.15
    relative_floor = fallback_score - 1.3
    return ai_score >= minimum_ai_score and ai_score >= relative_floor


def _generate_ai_culture_name(
    index: int,
    naming_seed: str,
    blocked_names: list[str],
    candidate_pool: list[str],
    traditions: list[str],
    fallback_candidate: str,
    *,
    family: dict | None = None,
) -> str | None:
    if not is_ai_faction_naming_enabled():
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        rejected_candidates: list[str] = []

        for attempt in range(AI_FACTION_NAMING_MAX_ATTEMPTS):
            prompt_payload = {
                "faction_index": index,
                "naming_seed": naming_seed,
                "attempt": attempt + 1,
                "language_family": family["family_name"] if family is not None else None,
                "family_shift_profile": family["shift_keys"] if family is not None else [],
                "traditions": [SOURCE_TRADITIONS[key]["label"] for key in traditions],
                "candidate_pool": candidate_pool[:6],
                "fallback_candidate": fallback_candidate,
                "blocked_names": blocked_names[:30],
                "rejected_candidates": rejected_candidates,
                "source_examples": {
                    key: SOURCE_TRADITIONS[key]["seed_names"][:6]
                    for key in traditions
                },
            }

            response = client.responses.create(
                model=AI_FACTION_NAMING_MODEL,
                temperature=AI_FACTION_NAMING_TEMPERATURE,
                max_output_tokens=30,
                input=[
                    {"role": "system", "content": AI_FACTION_NAMING_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(prompt_payload, sort_keys=True)},
                ],
            )
            proposed = _extract_response_text(response)
            validated = _validate_ai_candidate(proposed, blocked_names + rejected_candidates)
            if validated is None:
                if proposed:
                    rejected_candidates.append(proposed)
                continue
            if _passes_ai_quality_gate(validated, fallback_candidate):
                return validated
            rejected_candidates.append(validated)
    except Exception:
        return None

    return None


def generate_faction_identity(
    index: int,
    naming_seed: str = "default",
    existing_culture_names: list[str] | None = None,
    language_families: list[dict] | None = None,
) -> FactionIdentity:
    existing_culture_names = existing_culture_names or []
    assigned_family = _get_assigned_language_family(
        index,
        language_families or _generate_world_language_families(max(1, index), naming_seed),
        naming_seed,
    )
    culture_name, traditions, inspirations, candidate_pool = _generate_family_scoped_culture_name(
        index=index,
        naming_seed=naming_seed,
        family=assigned_family,
        existing_names=existing_culture_names,
    )
    blocked = REAL_NAME_BLOCKLIST + existing_culture_names
    ai_candidate = _generate_ai_culture_name(
        index=index,
        naming_seed=naming_seed,
        blocked_names=blocked,
        candidate_pool=candidate_pool,
        traditions=traditions,
        fallback_candidate=culture_name,
        family=assigned_family,
    )
    final_culture_name = ai_candidate or culture_name
    language_profile = _build_language_profile(
        final_culture_name,
        assigned_family,
        candidate_pool,
    )
    return FactionIdentity(
        internal_id=get_faction_internal_id(index),
        culture_name=final_culture_name,
        polity_tier=DEFAULT_POLITY_TIER,
        government_form=DEFAULT_GOVERNMENT_FORM,
        language_profile=language_profile,
        source_traditions=list(assigned_family["traditions"]),
        generation_method="ai_fused_sources" if ai_candidate else "curated_source_fusion",
        ai_generated=bool(ai_candidate),
        inspirations=list(assigned_family["inspirations"]),
        candidate_pool=candidate_pool[:8],
    )


def generate_faction_identities(num_factions: int, naming_seed: str = "default") -> list[FactionIdentity]:
    identities = []
    existing_culture_names: list[str] = []
    language_families = _generate_world_language_families(num_factions, naming_seed)

    for index in range(1, num_factions + 1):
        identity = generate_faction_identity(
            index=index,
            naming_seed=naming_seed,
            existing_culture_names=existing_culture_names,
            language_families=language_families,
        )
        identities.append(identity)
        existing_culture_names.append(identity.culture_name)

    return identities


def serialize_faction_identity(identity: FactionIdentity) -> dict:
    return asdict(identity)
