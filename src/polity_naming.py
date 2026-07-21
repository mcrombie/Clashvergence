from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from src.faction_naming import (
    CULTURE_DIRECTIONAL_PREFIXES,
    CULTURE_GOVERNMENT_SUFFIXES,
    extract_culture_root,
    generate_family_scoped_culture_name,
    get_culture_name_signature,
    is_culture_name_too_similar,
)
from src.models import Faction, LanguageProfile, Region, WorldState


CULTURE_SIMILARITY_THRESHOLD = 0.75

_DIRECTIONAL_PREFIX_PATTERN = re.compile(
    r"^(north(?:ern)?[-\s]+east(?:ern)?|north(?:ern)?[-\s]+west(?:ern)?|"
    r"south(?:ern)?[-\s]+east(?:ern)?|south(?:ern)?[-\s]+west(?:ern)?|"
    r"northeast(?:ern)?|northwest(?:ern)?|southeast(?:ern)?|southwest(?:ern)?|"
    r"north(?:ern)?|south(?:ern)?|east(?:ern)?|west(?:ern)?|"
    r"upper|lower|inner|outer|old|new|greater|lesser)\b",
    re.IGNORECASE,
)

_TERRAIN_QUALIFIERS = (
    (("coast", "coastal", "island", "islands", "sea"), "Coast"),
    (("river", "riverland"), "River"),
    (("marsh", "wetland", "wetlands"), "Marsh"),
    (("mountain", "mountains"), "Mountain"),
    (("hill", "hills", "highland", "highlands", "plateau"), "Highland"),
    (("forest", "woodland", "woodlands"), "Forest"),
    (("desert",), "Desert"),
    (("tundra",), "Tundra"),
    (("plain", "plains", "grassland", "grasslands", "steppe"), "Plain"),
)

_FALLBACK_QUALIFIERS = (
    "New",
    "Outer",
    "Upper",
    "Lower",
    "Highland",
    "River",
    "Forest",
    "Coast",
    "Plain",
)


def _clean_culture_name(value: str) -> str:
    words = re.findall(r"[A-Za-z]+", str(value or ""))
    while words and words[-1].lower() in CULTURE_GOVERNMENT_SUFFIXES:
        words.pop()
    return " ".join(words).strip()


def _active_faction_items(world: WorldState) -> list[tuple[str, Faction]]:
    inactive = set(getattr(world, "inactive_factions", []))
    owned_factions = {
        region.owner
        for region in world.regions.values()
        if region.owner in world.factions
    }
    if not world.regions:
        owned_factions = set(world.factions)
    return [
        (faction_name, faction)
        for faction_name, faction in world.factions.items()
        if faction_name in inactive or faction_name in owned_factions
    ]


def get_culture_registry_keys(culture_name: str) -> set[str]:
    """Return both the shared base and exact qualified identity keys."""
    return {
        key
        for key in (
            extract_culture_root(culture_name),
            get_culture_name_signature(culture_name),
        )
        if key
    }


def refresh_culture_roots(world: WorldState) -> set[str]:
    """Rebuild roots from territorial factions and names reserved for arrivals."""
    roots: set[str] = set()
    for _faction_name, faction in _active_faction_items(world):
        roots.update(get_culture_registry_keys(faction.culture_name))
    world.culture_roots = roots
    return roots


def register_culture_name(world: WorldState, culture_name: str) -> None:
    if not hasattr(world, "culture_roots"):
        world.culture_roots = set()
    world.culture_roots.update(get_culture_registry_keys(culture_name))


def _active_culture_names(
    world: WorldState,
    *,
    exclude_faction_name: str | None = None,
) -> list[str]:
    return [
        faction.culture_name
        for faction_name, faction in _active_faction_items(world)
        if faction_name != exclude_faction_name
    ]


def culture_name_conflicts(
    world: WorldState,
    candidate: str,
    *,
    exclude_faction_name: str | None = None,
    allow_shared_root: bool = False,
    check_similarity: bool = True,
) -> bool:
    """Check exact qualified identity, shared-root, and optional near-name collisions."""
    signature = get_culture_name_signature(candidate)
    root = extract_culture_root(candidate)
    if not signature or not root:
        return True

    existing_names = _active_culture_names(
        world,
        exclude_faction_name=exclude_faction_name,
    )
    existing_signatures = {
        get_culture_name_signature(name)
        for name in existing_names
    }
    if signature in existing_signatures:
        return True

    existing_roots = [extract_culture_root(name) for name in existing_names]
    registry = set(getattr(world, "culture_roots", set()))
    if exclude_faction_name in world.factions:
        own_keys = get_culture_registry_keys(
            world.factions[exclude_faction_name].culture_name
        )
        other_keys = culture_roots_for_names(existing_names)
        registry.difference_update(own_keys - other_keys)
    if signature in registry:
        return True
    if allow_shared_root:
        return False
    if root in registry or root in existing_roots:
        return True
    return check_similarity and is_culture_name_too_similar(
        root,
        sorted(set(existing_roots) | registry),
        threshold=CULTURE_SIMILARITY_THRESHOLD,
    )


def _region_source_name(region: Region | None) -> str:
    if region is None:
        return ""
    metadata = region.name_metadata if isinstance(region.name_metadata, dict) else {}
    return str(
        metadata.get("authored_name")
        or region.display_name
        or region.founding_name
        or region.name
        or ""
    ).strip()


def _directional_region_candidate(region: Region | None, base_name: str) -> str | None:
    source_name = _region_source_name(region)
    match = _DIRECTIONAL_PREFIX_PATTERN.match(source_name)
    if match is None:
        return None
    if extract_culture_root(source_name) == extract_culture_root(base_name):
        candidate = _clean_culture_name(source_name)
        return candidate or None
    qualifier = " ".join(
        token.capitalize()
        for token in re.findall(r"[A-Za-z]+", match.group(1))
    )
    return f"{qualifier} {base_name}".strip()


def _terrain_qualifiers(region: Region | None) -> list[str]:
    if region is None:
        return []
    normalized_tags = {
        str(tag).strip().lower().replace("_", "-")
        for tag in (region.terrain_tags or [])
    }
    qualifiers: list[str] = []
    for terrain_tokens, qualifier in _TERRAIN_QUALIFIERS:
        if any(
            token in normalized_tags
            or any(token in tag.split("-") for tag in normalized_tags)
            for token in terrain_tokens
        ):
            qualifiers.append(qualifier)
    return qualifiers


def get_faction_naming_region(
    world: WorldState,
    faction_name: str,
) -> Region | None:
    faction = world.factions.get(faction_name)
    if faction is None:
        return None
    for region_name in (
        faction.capital_region,
        faction.doctrine_state.homeland_region,
    ):
        if region_name and region_name in world.regions:
            return world.regions[region_name]
    owned_regions = sorted(
        (
            region
            for region in world.regions.values()
            if region.owner == faction_name
        ),
        key=lambda region: region.name,
    )
    return owned_regions[0] if owned_regions else None


def derive_geographic_qualifier(
    world: WorldState,
    *,
    region: Region | None = None,
    faction_name: str | None = None,
) -> str:
    if region is None and faction_name is not None:
        region = get_faction_naming_region(world, faction_name)
    source_name = _region_source_name(region)
    directional_match = _DIRECTIONAL_PREFIX_PATTERN.match(source_name)
    if directional_match is not None:
        return " ".join(
            token.capitalize()
            for token in re.findall(r"[A-Za-z]+", directional_match.group(1))
        )
    terrain = _terrain_qualifiers(region)
    return terrain[0] if terrain else "New"


def _display_name_conflicts(
    world: WorldState,
    candidate: str,
    *,
    exclude_faction_name: str | None,
) -> bool:
    normalized = " ".join(str(candidate or "").lower().split())
    if not normalized:
        return True
    for faction_name, faction in world.factions.items():
        if faction_name == exclude_faction_name:
            continue
        if " ".join(faction.display_name.lower().split()) == normalized:
            return True
    return normalized in {
        " ".join(faction_name.lower().split())
        for faction_name in world.factions
        if faction_name != exclude_faction_name
    }


def choose_unique_culture_name(
    world: WorldState,
    desired_name: str,
    *,
    region: Region | None = None,
    faction_name: str | None = None,
    language_profile: LanguageProfile | None = None,
    naming_seed: str | None = None,
    display_name_builder: Callable[[str], str] | None = None,
) -> str:
    """Choose a deterministic active-polity-safe culture name.

    An authored direction is retained first, followed by terrain/descriptive
    qualifiers. Only freshly coined roots use fuzzy matching; approved
    geographic compounds intentionally share their historical base.
    """
    if not getattr(world, "culture_roots", None):
        refresh_culture_roots(world)
    desired = _clean_culture_name(desired_name) or "New Culture"

    def display_is_free(candidate: str) -> bool:
        return display_name_builder is None or not _display_name_conflicts(
            world,
            display_name_builder(candidate),
            exclude_faction_name=faction_name,
        )

    if not culture_name_conflicts(
        world,
        desired,
        exclude_faction_name=faction_name,
    ) and display_is_free(desired):
        return desired

    bare_root = extract_culture_root(desired)
    base_name = " ".join(word.capitalize() for word in bare_root.split()) or desired
    candidates: list[str] = []
    directional_candidate = _directional_region_candidate(region, base_name)
    if directional_candidate:
        candidates.append(directional_candidate)
    candidates.extend(
        f"{qualifier} {base_name}"
        for qualifier in _terrain_qualifiers(region)
    )
    candidates.extend(f"{qualifier} {base_name}" for qualifier in _FALLBACK_QUALIFIERS)

    seen: set[str] = set()
    for candidate in candidates:
        signature = get_culture_name_signature(candidate)
        if not signature or signature in seen:
            continue
        seen.add(signature)
        if culture_name_conflicts(
            world,
            candidate,
            exclude_faction_name=faction_name,
            allow_shared_root=True,
            check_similarity=False,
        ):
            continue
        if display_is_free(candidate):
            return candidate

    profile = language_profile or LanguageProfile(family_name=base_name)
    existing_names = _active_culture_names(
        world,
        exclude_faction_name=faction_name,
    )
    seed = naming_seed or (
        f"{getattr(world, 'random_seed', None)}:{world.map_name}:{world.turn}:"
        f"{base_name}:{region.name if region is not None else faction_name or ''}"
    )
    for attempt in range(24):
        candidate = generate_family_scoped_culture_name(
            profile,
            naming_seed=f"{seed}:{attempt}",
            existing_names=existing_names,
            index=len(world.factions) + attempt + 1,
        )
        if culture_name_conflicts(
            world,
            candidate,
            exclude_faction_name=faction_name,
        ):
            continue
        if display_is_free(candidate):
            return candidate

    # This path is intentionally alphabetic rather than numeric so UI names do
    # not regress to "Rebels 2" style labels even under pathological fixtures.
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        candidate = f"Far {base_name} {letter}"
        if not culture_name_conflicts(
            world,
            candidate,
            exclude_faction_name=faction_name,
            allow_shared_root=True,
            check_similarity=False,
        ) and display_is_free(candidate):
            return candidate
    raise RuntimeError(f"Unable to derive a unique culture name from {desired_name!r}.")


def ensure_unique_faction_display_name(
    world: WorldState,
    faction_name: str,
    *,
    region: Region | None = None,
    display_name_builder: Callable[[str], str] | None = None,
) -> str:
    """Qualify a faction culture, if needed, before committing a display name."""
    faction = world.factions[faction_name]
    if faction.identity is None:
        return faction.display_name
    region = region or get_faction_naming_region(world, faction_name)
    builder = display_name_builder or (
        lambda culture_name: f"{culture_name} {faction.government_type}".strip()
    )
    culture_name = choose_unique_culture_name(
        world,
        faction.culture_name,
        region=region,
        faction_name=faction_name,
        language_profile=faction.identity.language_profile,
        display_name_builder=builder,
    )
    faction.identity.culture_name = culture_name
    faction.identity.display_name = builder(culture_name)
    refresh_culture_roots(world)
    return faction.identity.display_name


def culture_roots_for_names(names: Iterable[str]) -> set[str]:
    roots: set[str] = set()
    for name in names:
        roots.update(get_culture_registry_keys(name))
    return roots
