from __future__ import annotations

import hashlib
import random
import re

from src.models import Faction, Region, WorldState
from src.terrain import get_terrain_profile


TRADITIONAL_MORPHOLOGY = {
    "roman": {
        "coined_suffixes": ["ara", "ent", "ium", "ora", "unum"],
        "settlement_suffixes": ["ford", "gate", "hold", "mark", "stead"],
        "place_nouns": ["March", "Reach", "Vale", "Watch"],
    },
    "persian": {
        "coined_suffixes": ["abad", "ara", "dar", "stan", "var"],
        "settlement_suffixes": ["dar", "gard", "hold", "var", "zar"],
        "place_nouns": ["Crown", "March", "Pass", "Reach"],
    },
    "chinese": {
        "coined_suffixes": ["he", "lin", "shan", "yuan", "zhou"],
        "settlement_suffixes": ["gate", "lin", "pass", "shan", "zhou"],
        "place_nouns": ["Field", "Gate", "Pass", "Reach"],
    },
}

GENERIC_PLACE_NOUNS = [
    "Crossing",
    "Edge",
    "Ford",
    "Gate",
    "Hollow",
    "March",
    "Reach",
    "Vale",
    "Watch",
]
GENERIC_DIRECTIONS = ["North", "South", "East", "West", "Upper", "Lower"]


def _stable_random(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _letters_only(value: str) -> str:
    return re.sub(r"[^A-Za-z]", "", value or "")


def _tidy_place_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    return " ".join(word.capitalize() for word in cleaned.split())


def _derive_root_variants(culture_name: str) -> dict[str, str]:
    root = _letters_only(culture_name)
    if not root:
        return {"root": "Frontier", "stem": "Front", "adjectival": "Frontian"}

    stem = root
    for ending in ("ia", "ium", "ian", "an", "a", "e", "i", "o", "u"):
        if stem.lower().endswith(ending) and len(stem) - len(ending) >= 4:
            stem = stem[: -len(ending)]
            break

    if len(stem) < 4:
        stem = root[: max(4, min(len(root), 6))]

    adjectival = root
    if root.lower().endswith(("a", "e", "i", "o", "u")):
        adjectival = f"{root}n"
    elif not root.lower().endswith("ian"):
        adjectival = f"{root}ian"

    return {
        "root": root.capitalize(),
        "stem": stem.capitalize(),
        "adjectival": adjectival.capitalize(),
    }


def _build_profile(faction: Faction) -> dict[str, list[str]]:
    place_nouns = list(GENERIC_PLACE_NOUNS)
    settlement_suffixes = ["ford", "gate", "hold", "mere", "stead", "watch"]
    coined_suffixes = ["an", "ara", "en", "or", "um"]

    if faction.identity is not None:
        for tradition_key in faction.identity.source_traditions:
            tradition = TRADITIONAL_MORPHOLOGY.get(tradition_key)
            if tradition is None:
                continue
            place_nouns.extend(tradition["place_nouns"])
            settlement_suffixes.extend(tradition["settlement_suffixes"])
            coined_suffixes.extend(tradition["coined_suffixes"])

    return {
        "place_nouns": sorted(set(place_nouns)),
        "settlement_suffixes": sorted(set(settlement_suffixes)),
        "coined_suffixes": sorted(set(coined_suffixes)),
        "directions": list(GENERIC_DIRECTIONS),
    }


def _build_terrain_naming_profile(region: Region) -> dict[str, list[str] | str]:
    terrain_profile = get_terrain_profile(region)
    terrain_cues = list(terrain_profile["name_cues"])
    terrain_label = terrain_profile["terrain_label"]

    place_nouns = list(terrain_cues)
    settlement_suffixes = []

    suffix_overrides = {
        "Ford": "ford",
        "Gate": "gate",
        "Grove": "grove",
        "Hollow": "hollow",
        "Wood": "wood",
        "Hill": "hill",
        "Height": "height",
        "Ridge": "ridge",
        "Bay": "bay",
        "Cape": "cape",
        "Bog": "bog",
        "Fen": "fen",
        "Mire": "mire",
        "Field": "field",
        "Plain": "plain",
        "Wash": "wash",
        "Banks": "bank",
    }

    for cue in terrain_cues:
        if cue in suffix_overrides:
            settlement_suffixes.append(suffix_overrides[cue])

    return {
        "terrain_label": terrain_label,
        "terrain_cues": terrain_cues,
        "place_nouns": place_nouns,
        "settlement_suffixes": settlement_suffixes,
    }


def _candidate_names(
    faction: Faction,
    region: Region,
    is_homeland: bool,
) -> list[tuple[str, str]]:
    variants = _derive_root_variants(faction.culture_name)
    profile = _build_profile(faction)
    terrain_profile = _build_terrain_naming_profile(region)
    rng = _stable_random(f"{faction.internal_id}:{region.name}:{faction.culture_name}")

    place_noun_pool = profile["place_nouns"] + list(terrain_profile["place_nouns"])
    settlement_suffix_pool = profile["settlement_suffixes"] + list(terrain_profile["settlement_suffixes"])
    if not place_noun_pool:
        place_noun_pool = list(profile["place_nouns"])
    if not settlement_suffix_pool:
        settlement_suffix_pool = list(profile["settlement_suffixes"])

    place_noun = rng.choice(place_noun_pool)
    alt_place_noun = rng.choice(place_noun_pool)
    direction = rng.choice(profile["directions"])
    settlement_suffix = rng.choice(settlement_suffix_pool)
    coined_suffix = rng.choice(profile["coined_suffixes"])
    other_direction = rng.choice(profile["directions"])

    candidates: list[tuple[str, str]] = []
    if is_homeland:
        candidates.append((variants["root"], "homeland_root"))

    terrain_label = terrain_profile["terrain_label"]
    terrain_cues = terrain_profile["terrain_cues"]
    if terrain_label and not is_homeland:
        candidates.extend([
            (f"{variants['root']} {place_noun}", "terrain_root_place"),
            (f"{variants['adjectival']} {alt_place_noun}", "terrain_adjectival_place"),
        ])
        if terrain_cues:
            cue = rng.choice(terrain_cues)
            candidates.append((f"{variants['root']} {cue}", "terrain_cue_place"))

    candidates.extend([
        (f"New {variants['root']}", "new_root"),
        (f"{variants['root']} {place_noun}", "root_place"),
        (f"{variants['adjectival']} {alt_place_noun}", "adjectival_place"),
        (f"{variants['stem']}{settlement_suffix}", "stem_settlement"),
        (f"{direction} {variants['root']}", "directional_root"),
        (f"{other_direction} {variants['stem']}{settlement_suffix}", "directional_settlement"),
        (f"{variants['stem']}{coined_suffix}", "coined"),
    ])

    deduped: list[tuple[str, str]] = []
    seen = set()
    for candidate, pattern in candidates:
        tidy_candidate = _tidy_place_name(candidate)
        normalized = tidy_candidate.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append((tidy_candidate, pattern))
    return deduped


def get_region_display_name(region: Region) -> str:
    return region.ui_name


def format_region_reference(region: Region, include_code: bool = False) -> str:
    display_name = get_region_display_name(region)
    if include_code and display_name != region.name:
        return f"{display_name} ({region.name})"
    return display_name


def assign_region_founding_name(
    world: WorldState,
    region_name: str,
    faction_name: str,
    *,
    is_homeland: bool = False,
) -> str:
    region = world.regions[region_name]
    if region.founding_name:
        if not region.display_name:
            region.display_name = region.founding_name
        if region.original_namer_faction_id is None and faction_name in world.factions:
            region.original_namer_faction_id = world.factions[faction_name].internal_id
        return region.founding_name

    faction = world.factions[faction_name]
    existing_names = {
        other_region.display_name.lower()
        for other_region in world.regions.values()
        if other_region.display_name
    }

    chosen_name = None
    chosen_pattern = "fallback"
    for candidate, pattern in _candidate_names(faction, region, is_homeland=is_homeland):
        if candidate.lower() not in existing_names:
            chosen_name = candidate
            chosen_pattern = pattern
            break

    if chosen_name is None:
        chosen_name = f"{_derive_root_variants(faction.culture_name)['root']} {region.name}"

    region.founding_name = chosen_name
    region.display_name = chosen_name
    region.original_namer_faction_id = faction.internal_id
    region.name_metadata = {
        "pattern": chosen_pattern,
        "is_homeland": is_homeland,
        "named_from": faction.culture_name,
        "terrain_label": get_terrain_profile(region)["terrain_label"],
        "terrain_tags": list(region.terrain_tags),
    }
    return chosen_name
