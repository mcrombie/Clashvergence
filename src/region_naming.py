from __future__ import annotations

import hashlib
import random
import re

from src.models import Faction, LanguageProfile, Region, WorldState
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
TERRAIN_ROOT_CONCEPTS = {
    "riverland": ("river",),
    "forest": ("forest",),
    "hills": ("hill",),
    "mountains": ("hill", "fort"),
    "plains": ("plain",),
    "marsh": ("marsh", "river"),
    "coast": ("sea", "market"),
}


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


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.lower()
        if not value or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(value)
    return ordered


def _get_profile_roots(language_profile: LanguageProfile, concept: str) -> list[str]:
    return list((language_profile.lexical_roots or {}).get(concept, []))


def _collect_region_semantic_roots(language_profile: LanguageProfile, region: Region) -> list[str]:
    roots: list[str] = []
    for terrain_tag in region.terrain_tags or ["plains"]:
        for concept in TERRAIN_ROOT_CONCEPTS.get(terrain_tag, ()):
            roots.extend(_get_profile_roots(language_profile, concept))
    roots.extend(_get_profile_roots(language_profile, "settlement"))
    if region.trade_foreign_partner is not None or region.trade_route_role in {"hub", "corridor", "gateway"}:
        roots.extend(_get_profile_roots(language_profile, "market"))
    return _dedupe_preserving_order([_letters_only(root).capitalize() for root in roots if root])


def _get_naming_language_profile(world: WorldState, faction: Faction) -> LanguageProfile:
    if faction.primary_ethnicity and faction.primary_ethnicity in world.ethnicities:
        return world.ethnicities[faction.primary_ethnicity].language_profile
    if faction.identity is not None:
        return faction.identity.language_profile
    return LanguageProfile(family_name=faction.culture_name)


def _get_naming_root_name(world: WorldState, faction: Faction) -> str:
    if faction.primary_ethnicity:
        return faction.primary_ethnicity
    profile = _get_naming_language_profile(world, faction)
    if profile.family_name:
        return profile.family_name
    return faction.culture_name


def _build_profile(world: WorldState, faction: Faction) -> dict[str, list[str]]:
    place_nouns = list(GENERIC_PLACE_NOUNS)
    settlement_suffixes = ["ford", "gate", "hold", "mere", "stead", "watch"]
    coined_suffixes = ["an", "ara", "en", "or", "um"]
    language_profile = _get_naming_language_profile(world, faction)

    if faction.identity is not None:
        for tradition_key in faction.identity.source_traditions:
            tradition = TRADITIONAL_MORPHOLOGY.get(tradition_key)
            if tradition is None:
                continue
            place_nouns.extend(tradition["place_nouns"])
            settlement_suffixes.extend(tradition["settlement_suffixes"])
            coined_suffixes.extend(tradition["coined_suffixes"])

    if language_profile.suffixes:
        coined_suffixes.extend(language_profile.suffixes[:8])
        settlement_suffixes.extend(
            suffix
            for suffix in language_profile.suffixes[:8]
            if 3 <= len(suffix) <= 6
        )
    if language_profile.seed_fragments:
        settlement_suffixes.extend(
            fragment
            for fragment in language_profile.seed_fragments[:10]
            if 3 <= len(fragment) <= 5
        )
    if language_profile.style_notes:
        place_nouns.extend(
            note.split(",")[0].split()[-1]
            for note in language_profile.style_notes
            if note
        )

    return {
        "place_nouns": _dedupe_preserving_order(place_nouns),
        "settlement_suffixes": _dedupe_preserving_order(settlement_suffixes),
        "coined_suffixes": _dedupe_preserving_order(coined_suffixes),
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
        "terrain_tags": list(terrain_profile["terrain_tags"]),
        "terrain_label": terrain_label,
        "terrain_cues": terrain_cues,
        "place_nouns": place_nouns,
        "settlement_suffixes": settlement_suffixes,
    }


def _candidate_names(
    world: WorldState,
    faction: Faction,
    region: Region,
    is_homeland: bool,
) -> list[tuple[str, str]]:
    root_name = _get_naming_root_name(world, faction)
    variants = _derive_root_variants(root_name)
    profile = _build_profile(world, faction)
    language_profile = _get_naming_language_profile(world, faction)
    terrain_profile = _build_terrain_naming_profile(region)
    rng = _stable_random(f"{faction.internal_id}:{region.name}:{root_name}")

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
    language_fragment = ""
    if language_profile.seed_fragments:
        language_fragment = rng.choice(language_profile.seed_fragments)
    elif language_profile.onsets:
        language_fragment = rng.choice(language_profile.onsets)
    semantic_roots = _collect_region_semantic_roots(language_profile, region)
    semantic_root = rng.choice(semantic_roots) if semantic_roots else ""

    candidates: list[tuple[str, str]] = []
    if is_homeland:
        candidates.append((variants["root"], "homeland_root"))

    terrain_label = terrain_profile["terrain_label"]
    terrain_cues = terrain_profile["terrain_cues"]
    has_distinct_terrain_identity = terrain_profile["terrain_tags"] != ["plains"]
    if terrain_label and has_distinct_terrain_identity and not is_homeland:
        candidates.extend([
            (f"{variants['root']} {place_noun}", "terrain_root_place"),
            (f"{variants['adjectival']} {alt_place_noun}", "terrain_adjectival_place"),
        ])
        if terrain_cues:
            cue = rng.choice(terrain_cues)
            candidates.append((f"{variants['root']} {cue}", "terrain_cue_place"))
    if language_fragment:
        fragment = _letters_only(language_fragment).capitalize()
        if fragment:
            candidates.extend([
                (f"{fragment}{settlement_suffix}", "ethnicity_fragment_settlement"),
                (f"{fragment} {place_noun}", "ethnicity_fragment_place"),
            ])
    if semantic_root:
        candidates.extend([
            (f"{variants['stem']}{semantic_root.lower()}", "semantic_compound"),
            (f"{semantic_root} {place_noun}", "semantic_place"),
        ])

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
    for candidate, pattern in _candidate_names(world, faction, region, is_homeland=is_homeland):
        if candidate.lower() not in existing_names:
            chosen_name = candidate
            chosen_pattern = pattern
            break

    if chosen_name is None:
        chosen_name = f"{_derive_root_variants(_get_naming_root_name(world, faction))['root']} {region.name}"

    region.founding_name = chosen_name
    region.display_name = chosen_name
    region.original_namer_faction_id = faction.internal_id
    region.name_metadata = {
        "pattern": chosen_pattern,
        "is_homeland": is_homeland,
        "named_from": _get_naming_root_name(world, faction),
        "named_from_ethnicity": faction.primary_ethnicity,
        "terrain_label": get_terrain_profile(region)["terrain_label"],
        "terrain_tags": list(region.terrain_tags),
        "name_layers": [
            {
                "type": "founding",
                "name": chosen_name,
                "pattern": chosen_pattern,
                "faction_id": faction.internal_id,
                "faction_name": faction_name,
                "turn": getattr(world, "turn", 0),
            }
        ],
        "current_name_reason": "founding",
    }
    return chosen_name


def _get_region_name_layers(region: Region) -> list[dict]:
    layers = region.name_metadata.get("name_layers")
    if isinstance(layers, list):
        return layers
    layers = []
    region.name_metadata["name_layers"] = layers
    return layers


def _record_region_name_layer(
    region: Region,
    *,
    layer_type: str,
    name: str,
    pattern: str,
    faction_id: str | None,
    faction_name: str | None,
    turn: int,
) -> None:
    layers = _get_region_name_layers(region)
    if layers and layers[-1].get("name") == name and layers[-1].get("type") == layer_type:
        return
    layers.append(
        {
            "type": layer_type,
            "name": name,
            "pattern": pattern,
            "faction_id": faction_id,
            "faction_name": faction_name,
            "turn": turn,
        }
    )


def _split_place_tokens(place_name: str) -> tuple[str, str | None]:
    parts = [part for part in place_name.split() if part]
    if not parts:
        return "", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[-1]


def _build_layered_conquest_candidates(
    world: WorldState,
    faction: Faction,
    region: Region,
    prior_name: str,
) -> list[tuple[str, str]]:
    root_name = _get_naming_root_name(world, faction)
    variants = _derive_root_variants(root_name)
    profile = _build_profile(world, faction)
    language_profile = _get_naming_language_profile(world, faction)
    rng = _stable_random(f"{faction.internal_id}:{region.name}:{prior_name}:layered")
    prior_root, prior_noun = _split_place_tokens(prior_name)
    prior_root_letters = _letters_only(prior_root).capitalize()
    direction = rng.choice(profile["directions"])
    place_noun = prior_noun or rng.choice(profile["place_nouns"])
    semantic_roots = _collect_region_semantic_roots(language_profile, region)
    semantic_root = rng.choice(semantic_roots).lower() if semantic_roots else ""
    candidates: list[tuple[str, str]] = []

    if prior_noun:
        candidates.extend(
            [
                (f"{variants['root']} {prior_noun}", "conqueror_root_old_noun"),
                (f"{variants['adjectival']} {prior_noun}", "conqueror_adjectival_old_noun"),
            ]
        )
    if prior_root_letters and semantic_root:
        candidates.extend(
            [
                (f"{prior_root_letters}{semantic_root}", "substrate_semantic_compound"),
                (f"{semantic_root.capitalize()} {place_noun}", "semantic_overlay_place"),
            ]
        )
    candidates.extend(
        [
            (f"{direction} {prior_name}", "directional_overlay"),
            (f"New {prior_name}", "new_overlay"),
        ]
    )
    if prior_root_letters:
        candidates.append((f"{variants['stem']}{prior_root_letters.lower()}", "dynastic_overlay"))

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for candidate, pattern in candidates:
        tidy_candidate = _tidy_place_name(candidate)
        normalized = tidy_candidate.lower()
        if not normalized or normalized == prior_name.lower() or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append((tidy_candidate, pattern))
    return deduped


def apply_region_name_layer(
    world: WorldState,
    region_name: str,
    faction_name: str,
    *,
    reason: str = "conquest",
) -> dict[str, str | bool | None]:
    region = world.regions[region_name]
    if not region.founding_name:
        assigned_name = assign_region_founding_name(world, region_name, faction_name, is_homeland=False)
        return {
            "name": assigned_name,
            "previous_name": None,
            "changed": True,
            "layer_type": "founding",
            "pattern": region.name_metadata.get("pattern"),
        }

    faction = world.factions[faction_name]
    prior_name = region.display_name or region.founding_name
    original_namer_id = region.original_namer_faction_id
    if original_namer_id == faction.internal_id:
        region.display_name = region.founding_name
        region.name_metadata["current_name_reason"] = "restoration"
        _record_region_name_layer(
            region,
            layer_type="restoration",
            name=region.display_name,
            pattern="restore_founding",
            faction_id=faction.internal_id,
            faction_name=faction_name,
            turn=getattr(world, "turn", 0),
        )
        return {
            "name": region.display_name,
            "previous_name": prior_name,
            "changed": region.display_name != prior_name,
            "layer_type": "restoration",
            "pattern": "restore_founding",
        }

    existing_names = {
        other_region.display_name.lower()
        for other_region in world.regions.values()
        if other_region is not region and other_region.display_name
    }
    chosen_name = prior_name
    chosen_pattern = "preserved"
    for candidate, pattern in _build_layered_conquest_candidates(world, faction, region, prior_name):
        if candidate.lower() not in existing_names:
            chosen_name = candidate
            chosen_pattern = pattern
            break

    region.display_name = chosen_name
    region.name_metadata["current_name_reason"] = reason
    region.name_metadata["current_pattern"] = chosen_pattern
    region.name_metadata["current_named_from"] = _get_naming_root_name(world, faction)
    region.name_metadata["current_named_from_ethnicity"] = faction.primary_ethnicity
    _record_region_name_layer(
        region,
        layer_type=reason,
        name=chosen_name,
        pattern=chosen_pattern,
        faction_id=faction.internal_id,
        faction_name=faction_name,
        turn=getattr(world, "turn", 0),
    )
    return {
        "name": chosen_name,
        "previous_name": prior_name,
        "changed": chosen_name != prior_name,
        "layer_type": reason,
        "pattern": chosen_pattern,
    }
