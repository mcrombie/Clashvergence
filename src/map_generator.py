from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import math
import random
from typing import Mapping


GENERATED_MAP_NAMES = {
    "generated",
    "generated_world",
    "generated_ring",
    "generated_frontier",
    "generated_basin",
    "generated_archipelago",
    "generated_continent",
    "generated_highlands",
}

MAP_GENERATION_STYLES = (
    "continent",
    "frontier",
    "basin",
    "archipelago",
    "highlands",
)

CLIMATE_MODES = (
    "temperate",
    "varied",
    "arid",
    "cold",
    "tropical",
)

START_STRATEGIES = (
    "balanced",
    "coastal",
    "heartland",
    "frontier",
)

TERRAIN_TAGS = (
    "coast",
    "plains",
    "forest",
    "hills",
    "highland",
    "riverland",
    "marsh",
    "steppe",
)


@dataclass(frozen=True)
class MapGenerationConfig:
    style: str = "continent"
    seed: str = "generated"
    region_count: int = 48
    landmass_count: int = 1
    water_level: float = 0.28
    river_count: int = 3
    mountain_spines: int = 2
    climate_mode: str = "varied"
    resource_richness: float = 1.0
    chokepoint_density: float = 0.45
    terrain_diversity: float = 0.65
    start_strategy: str = "balanced"


def is_generated_map_name(map_name: str) -> bool:
    return map_name in GENERATED_MAP_NAMES or map_name.startswith("generated_")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _coerce_float(value: object, fallback: float, low: float, high: float) -> float:
    try:
        return round(_clamp(float(value), low, high), 3)
    except (TypeError, ValueError):
        return fallback


def _coerce_int(value: object, fallback: int, low: int, high: int) -> int:
    try:
        return _clamp_int(int(value), low, high)
    except (TypeError, ValueError):
        return fallback


def _style_from_map_name(map_name: str) -> str:
    if "frontier" in map_name:
        return "frontier"
    if "basin" in map_name:
        return "basin"
    if "archipelago" in map_name:
        return "archipelago"
    if "highland" in map_name:
        return "highlands"
    return "continent"


def _default_region_count(num_factions: int, style: str) -> int:
    base = 36 if num_factions <= 4 else num_factions * 8
    if style == "archipelago":
        base += max(6, num_factions)
    elif style == "frontier":
        base += max(4, num_factions // 2)
    elif style == "basin":
        base += 8
    elif style == "highlands":
        base += 4
    return _clamp_int(base, max(24, num_factions * 4), 96)


def _default_landmass_count(num_factions: int, style: str) -> int:
    if style == "archipelago":
        return _clamp_int(max(3, num_factions // 2), 2, 8)
    if style == "frontier":
        return 2 if num_factions >= 5 else 1
    return 1


def build_generation_config(
    map_name: str,
    num_factions: int,
    overrides: Mapping[str, object] | None = None,
) -> MapGenerationConfig:
    overrides = dict(overrides or {})
    style = str(overrides.get("style") or _style_from_map_name(map_name))
    if style not in MAP_GENERATION_STYLES:
        style = "continent"

    seed = str(overrides.get("seed") or f"{map_name}:{num_factions}")
    region_count = _coerce_int(
        overrides.get("region_count", overrides.get("regions")),
        _default_region_count(num_factions, style),
        max(18, num_factions * 3),
        120,
    )
    landmass_count = _coerce_int(
        overrides.get("landmass_count", overrides.get("landmasses")),
        _default_landmass_count(num_factions, style),
        1,
        min(10, max(1, region_count // 8)),
    )
    water_default = {
        "continent": 0.26,
        "frontier": 0.34,
        "basin": 0.18,
        "archipelago": 0.62,
        "highlands": 0.22,
    }[style]
    river_default = {
        "continent": max(3, num_factions // 2),
        "frontier": max(2, num_factions // 3),
        "basin": max(4, num_factions // 2 + 1),
        "archipelago": max(2, landmass_count),
        "highlands": max(3, num_factions // 2),
    }[style]
    mountain_default = {
        "continent": 2,
        "frontier": 2,
        "basin": 3,
        "archipelago": 1,
        "highlands": 5,
    }[style]

    climate_mode = str(overrides.get("climate_mode", overrides.get("climate")) or "varied")
    if climate_mode not in CLIMATE_MODES:
        climate_mode = "varied"
    start_strategy = str(overrides.get("start_strategy", overrides.get("starts")) or "balanced")
    if start_strategy not in START_STRATEGIES:
        start_strategy = "balanced"

    return MapGenerationConfig(
        style=style,
        seed=seed,
        region_count=region_count,
        landmass_count=landmass_count,
        water_level=_coerce_float(overrides.get("water_level", overrides.get("water")), water_default, 0.0, 0.9),
        river_count=_coerce_int(overrides.get("river_count", overrides.get("rivers")), river_default, 0, 12),
        mountain_spines=_coerce_int(
            overrides.get("mountain_spines", overrides.get("mountains")),
            mountain_default,
            0,
            10,
        ),
        climate_mode=climate_mode,
        resource_richness=_coerce_float(
            overrides.get("resource_richness", overrides.get("richness")),
            1.0,
            0.45,
            1.8,
        ),
        chokepoint_density=_coerce_float(
            overrides.get("chokepoint_density", overrides.get("chokepoints")),
            0.45,
            0.0,
            1.0,
        ),
        terrain_diversity=_coerce_float(
            overrides.get("terrain_diversity", overrides.get("diversity")),
            0.65,
            0.0,
            1.0,
        ),
        start_strategy=start_strategy,
    )


def _add_bidirectional_neighbor(
    regions: dict[str, dict],
    region_name: str,
    neighbor_name: str,
) -> None:
    if neighbor_name == region_name:
        return
    if neighbor_name not in regions[region_name]["neighbors"]:
        regions[region_name]["neighbors"].append(neighbor_name)
    if region_name not in regions[neighbor_name]["neighbors"]:
        regions[neighbor_name]["neighbors"].append(region_name)


def _dedupe_tags(tags: list[str]) -> list[str]:
    deduped: list[str] = []
    for tag in tags:
        if tag in TERRAIN_TAGS and tag not in deduped:
            deduped.append(tag)
    return deduped or ["plains"]


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _distance_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    length_squared = (dx * dx) + (dy * dy)
    if length_squared <= 0:
        return _distance(point, start)
    t = _clamp(((px - sx) * dx + (py - sy) * dy) / length_squared, 0.0, 1.0)
    return _distance(point, (sx + t * dx, sy + t * dy))


def _allocate_landmass_sizes(config: MapGenerationConfig, rng: random.Random) -> list[int]:
    if config.landmass_count == 1:
        return [config.region_count]
    weights = []
    for index in range(config.landmass_count):
        if config.style == "archipelago":
            weight = rng.uniform(0.75, 1.35)
        else:
            weight = 1.8 if index == 0 else rng.uniform(0.45, 1.0)
        weights.append(weight)
    total_weight = sum(weights)
    sizes = [
        max(3, int(round(config.region_count * weight / total_weight)))
        for weight in weights
    ]
    while sum(sizes) > config.region_count:
        largest = max(range(len(sizes)), key=lambda index: sizes[index])
        sizes[largest] -= 1
    while sum(sizes) < config.region_count:
        smallest = min(range(len(sizes)), key=lambda index: sizes[index])
        sizes[smallest] += 1
    return sizes


def _landmass_centers(config: MapGenerationConfig) -> list[tuple[float, float]]:
    if config.landmass_count == 1:
        return [(0.5, 0.52)]
    centers = []
    radius = 0.27 if config.style == "archipelago" else 0.22
    for index in range(config.landmass_count):
        angle = (2.0 * math.pi * index / config.landmass_count) - (math.pi / 2.0)
        centers.append((
            0.5 + math.cos(angle) * radius,
            0.5 + math.sin(angle) * radius * 0.78,
        ))
    return centers


def _generate_region_points(
    config: MapGenerationConfig,
    rng: random.Random,
) -> dict[str, dict]:
    regions: dict[str, dict] = {}
    sizes = _allocate_landmass_sizes(config, rng)
    centers = _landmass_centers(config)

    for landmass_index, size in enumerate(sizes):
        center_x, center_y = centers[landmass_index]
        landmass_scale = math.sqrt(size / max(1, config.region_count))
        if config.style == "archipelago":
            radius_x = 0.18 * landmass_scale + 0.04
            radius_y = 0.15 * landmass_scale + 0.035
        else:
            radius_x = 0.36 * landmass_scale + 0.08
            radius_y = 0.27 * landmass_scale + 0.07
        wobble_phase = rng.uniform(0, math.tau)

        for local_index in range(size):
            angle = (math.tau * local_index / size) + rng.uniform(-0.16, 0.16)
            ring = math.sqrt((local_index + 0.65) / size)
            radius_noise = 0.82 + rng.random() * 0.32
            x = center_x + math.cos(angle) * radius_x * ring * radius_noise
            y = center_y + math.sin(angle + math.sin(angle + wobble_phase) * 0.18) * radius_y * ring * radius_noise
            x += rng.uniform(-0.018, 0.018)
            y += rng.uniform(-0.018, 0.018)
            region_name = f"W{len(regions) + 1}"
            regions[region_name] = {
                "neighbors": [],
                "owner": None,
                "resources": 2,
                "position": {
                    "x": round(_clamp(x, 0.06, 0.94), 4),
                    "y": round(_clamp(y, 0.06, 0.94), 4),
                },
                "landmass": landmass_index,
            }
    return regions


def _build_land_graph(
    regions: dict[str, dict],
    config: MapGenerationConfig,
    rng: random.Random,
) -> None:
    by_landmass: dict[int, list[str]] = {}
    for region_name, region in regions.items():
        by_landmass.setdefault(int(region["landmass"]), []).append(region_name)

    for names in by_landmass.values():
        positions = {
            name: (regions[name]["position"]["x"], regions[name]["position"]["y"])
            for name in names
        }
        connected = {names[0]}
        unconnected = set(names[1:])
        while unconnected:
            best_edge = None
            best_distance = float("inf")
            for connected_name in connected:
                for candidate_name in unconnected:
                    distance = _distance(positions[connected_name], positions[candidate_name])
                    if distance < best_distance:
                        best_distance = distance
                        best_edge = (connected_name, candidate_name)
            assert best_edge is not None
            _add_bidirectional_neighbor(regions, best_edge[0], best_edge[1])
            connected.add(best_edge[1])
            unconnected.remove(best_edge[1])

        extra_edge_budget = 2 + int(round((1.0 - config.chokepoint_density) * 3))
        for region_name in names:
            nearest = sorted(
                (
                    (_distance(positions[region_name], positions[other_name]), other_name)
                    for other_name in names
                    if other_name != region_name
                ),
                key=lambda item: item[0],
            )
            for distance, other_name in nearest[:extra_edge_budget]:
                if other_name in regions[region_name]["neighbors"]:
                    continue
                if distance < 0.34 and rng.random() < (0.72 - config.chokepoint_density * 0.32):
                    _add_bidirectional_neighbor(regions, region_name, other_name)

    if len(by_landmass) <= 1:
        return

    landmass_names = list(by_landmass)
    bridge_factor = 1 if config.chokepoint_density >= 0.55 else 2
    for index, landmass in enumerate(landmass_names):
        next_landmass = landmass_names[(index + 1) % len(landmass_names)]
        for _ in range(bridge_factor):
            best_pair = min(
                (
                    (
                        _distance(
                            (regions[first]["position"]["x"], regions[first]["position"]["y"]),
                            (regions[second]["position"]["x"], regions[second]["position"]["y"]),
                        ),
                        first,
                        second,
                    )
                    for first in by_landmass[landmass]
                    for second in by_landmass[next_landmass]
                ),
                key=lambda item: item[0],
            )
            _add_bidirectional_neighbor(regions, best_pair[1], best_pair[2])


def _build_spines(
    config: MapGenerationConfig,
    rng: random.Random,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    spines = []
    for _ in range(config.mountain_spines):
        if config.style == "basin":
            angle = rng.uniform(0, math.tau)
            start = (0.5 + math.cos(angle) * 0.33, 0.5 + math.sin(angle) * 0.26)
            end = (0.5 + math.cos(angle + math.pi) * 0.33, 0.5 + math.sin(angle + math.pi) * 0.26)
        else:
            angle = rng.uniform(-0.7, 0.7) + (math.pi / 2 if rng.random() < 0.5 else 0.0)
            center = (rng.uniform(0.28, 0.72), rng.uniform(0.28, 0.72))
            length = rng.uniform(0.35, 0.75)
            start = (
                center[0] - math.cos(angle) * length / 2,
                center[1] - math.sin(angle) * length / 2,
            )
            end = (
                center[0] + math.cos(angle) * length / 2,
                center[1] + math.sin(angle) * length / 2,
            )
        spines.append((start, end))
    return spines


def _build_river_paths(
    regions: dict[str, dict],
    config: MapGenerationConfig,
    spines: list[tuple[tuple[float, float], tuple[float, float]]],
    rng: random.Random,
) -> list[list[str]]:
    if config.river_count <= 0:
        return []

    positions = {
        name: (region["position"]["x"], region["position"]["y"])
        for name, region in regions.items()
    }
    elevation = {
        name: _get_elevation(positions[name], spines, int(regions[name]["landmass"]))
        for name in regions
    }
    river_sources = sorted(regions, key=lambda name: elevation[name], reverse=True)
    used_sources: set[str] = set()
    paths = []

    for source_name in river_sources:
        if len(paths) >= config.river_count:
            break
        if source_name in used_sources:
            continue
        path = [source_name]
        used_sources.add(source_name)
        current = source_name
        seen = {source_name}
        for _ in range(12):
            neighbors = [
                neighbor
                for neighbor in regions[current]["neighbors"]
                if neighbor not in seen
                and int(regions[neighbor]["landmass"]) == int(regions[source_name]["landmass"])
            ]
            if not neighbors:
                break
            current_position = positions[current]
            neighbors.sort(
                key=lambda name: (
                    elevation[name],
                    -_distance(current_position, positions[name]),
                    rng.random(),
                )
            )
            current = neighbors[0]
            path.append(current)
            seen.add(current)
            if _is_coastal_position(positions[current], config.water_level):
                break
        if len(path) >= 3:
            paths.append(path)
    return paths


def _is_coastal_position(position: tuple[float, float], water_level: float) -> bool:
    x, y = position
    edge_distance = min(x, y, 1.0 - x, 1.0 - y)
    return edge_distance < (0.08 + water_level * 0.08)


def _get_elevation(
    position: tuple[float, float],
    spines: list[tuple[tuple[float, float], tuple[float, float]]],
    landmass: int,
) -> float:
    if not spines:
        return 0.28
    spine_distance = min(_distance_to_segment(position, start, end) for start, end in spines)
    ridge = max(0.0, 1.0 - spine_distance / 0.18)
    noise = ((math.sin((position[0] * 19.7) + landmass) + math.cos(position[1] * 17.1)) + 2.0) / 8.0
    return _clamp((ridge * 0.82) + noise, 0.0, 1.0)


def _choose_climate(
    position: tuple[float, float],
    tags: list[str],
    config: MapGenerationConfig,
) -> str:
    if config.climate_mode != "varied":
        if config.climate_mode == "arid" and "riverland" in tags:
            return "steppe"
        return config.climate_mode
    latitude = abs(position[1] - 0.5) * 2.0
    if "highland" in tags and latitude > 0.35:
        return "cold"
    if latitude > 0.78:
        return "cold"
    if latitude < 0.22 and ("marsh" in tags or "forest" in tags):
        return "tropical"
    if "steppe" in tags:
        return "steppe"
    if "coast" in tags:
        return "oceanic"
    return "temperate"


def _assign_terrain_and_climate(
    regions: dict[str, dict],
    config: MapGenerationConfig,
    rng: random.Random,
) -> list[list[str]]:
    spines = _build_spines(config, rng)
    river_paths = _build_river_paths(regions, config, spines, rng)
    river_regions = {region_name for path in river_paths for region_name in path}

    for region_name, region in regions.items():
        position = (region["position"]["x"], region["position"]["y"])
        elevation = _get_elevation(position, spines, int(region["landmass"]))
        moisture = (
            0.42
            + (0.22 if region_name in river_regions else 0.0)
            + (0.16 if _is_coastal_position(position, config.water_level) else 0.0)
            + (math.sin(position[0] * math.tau * 2.0) * 0.08)
            - (0.18 if elevation > 0.72 else 0.0)
        )
        moisture += rng.uniform(-0.08, 0.08) * config.terrain_diversity
        tags: list[str] = []
        if _is_coastal_position(position, config.water_level) or config.style == "archipelago":
            if rng.random() < (0.42 + config.water_level * 0.58):
                tags.append("coast")
        if region_name in river_regions:
            tags.append("riverland")
        if elevation > 0.78:
            tags.append("highland")
        elif elevation > 0.56:
            tags.append("hills")
        if moisture > 0.72 and ("coast" in tags or "riverland" in tags) and elevation < 0.48:
            tags.append("marsh")
        elif moisture > 0.56 and elevation < 0.68:
            tags.append("forest")
        elif moisture < 0.32 and elevation < 0.58:
            tags.append("steppe")
        else:
            tags.append("plains")
        if config.style == "highlands" and "highland" not in tags and rng.random() < 0.28:
            tags = ["hills", *tags]
        if config.style == "basin" and _distance(position, (0.5, 0.5)) < 0.18:
            tags = ["riverland", "plains"]

        region["terrain_tags"] = _dedupe_tags(tags)
        region["climate"] = _choose_climate(position, region["terrain_tags"], config)

    return river_paths


def _resource_value_for_region(
    region: dict,
    config: MapGenerationConfig,
    rng: random.Random,
) -> int:
    tags = region["terrain_tags"]
    value = 2.0
    if "riverland" in tags:
        value += 0.8
    if "coast" in tags:
        value += 0.35
    if "hills" in tags or "highland" in tags:
        value += 0.35
    if "marsh" in tags:
        value -= 0.35
    if "steppe" in tags:
        value -= 0.1
    value *= config.resource_richness
    value += rng.uniform(-0.45, 0.55)
    return _clamp_int(int(round(value)), 1, 5)


def _graph_distances(regions: dict[str, dict], start: str) -> dict[str, int]:
    distances = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in regions[current]["neighbors"]:
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + 1
            queue.append(neighbor)
    return distances


def _start_score(
    regions: dict[str, dict],
    region_name: str,
    chosen: list[str],
    strategy: str,
) -> float:
    region = regions[region_name]
    tags = region["terrain_tags"]
    score = float(region["resources"]) * 0.9
    if strategy == "coastal" and "coast" in tags:
        score += 2.0
    elif strategy == "heartland" and "coast" not in tags:
        score += 1.2
    elif strategy == "frontier" and len(region["neighbors"]) <= 3:
        score += 1.4
    elif strategy == "balanced":
        score += min(1.5, len(region["neighbors"]) * 0.25)
    if "marsh" in tags:
        score -= 0.8
    if "riverland" in tags:
        score += 0.7
    if chosen:
        distances = [_graph_distances(regions, existing).get(region_name, 0) for existing in chosen]
        score += min(distances) * 0.9
    return score


def _assign_starting_regions(
    regions: dict[str, dict],
    num_factions: int,
    config: MapGenerationConfig,
) -> None:
    candidates = [
        name
        for name, region in regions.items()
        if region["resources"] >= 2 and len(region["neighbors"]) >= 2
    ]
    chosen: list[str] = []
    for faction_index in range(num_factions):
        available = [name for name in candidates if name not in chosen]
        if not available:
            break
        best = max(
            available,
            key=lambda name: (_start_score(regions, name, chosen, config.start_strategy), name),
        )
        chosen.append(best)
        regions[best]["owner"] = f"Faction{faction_index + 1}"
        regions[best]["resources"] = max(3, int(regions[best]["resources"]))


def _build_links(
    regions: dict[str, dict],
    river_paths: list[list[str]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    river_edges = set()
    for path in river_paths:
        for index in range(len(path) - 1):
            river_edges.add(tuple(sorted((path[index], path[index + 1]))))

    sea_links = set()
    for region_name, region in regions.items():
        for neighbor_name in region["neighbors"]:
            if region_name > neighbor_name:
                continue
            neighbor = regions[neighbor_name]
            if int(region["landmass"]) != int(neighbor["landmass"]):
                sea_links.add((region_name, neighbor_name))
            elif "coast" in region["terrain_tags"] and "coast" in neighbor["terrain_tags"]:
                sea_links.add((region_name, neighbor_name))

    return sorted(sea_links), sorted(river_edges)


def _validate_generated_map(definition: dict, num_factions: int) -> None:
    regions = definition["regions"]
    if not regions:
        raise ValueError("Generated map has no regions.")
    expected_owners = {f"Faction{index}" for index in range(1, num_factions + 1)}
    actual_owners = {
        region["owner"]
        for region in regions.values()
        if region["owner"] is not None
    }
    if actual_owners != expected_owners:
        raise ValueError("Generated map did not assign exactly one start per configured faction.")
    first_name = next(iter(regions))
    if len(_graph_distances(regions, first_name)) != len(regions):
        raise ValueError("Generated map graph is not connected.")
    for region_name, region in regions.items():
        if not region["neighbors"]:
            raise ValueError(f"Generated region {region_name} has no neighbors.")
        for neighbor_name in region["neighbors"]:
            if region_name not in regions[neighbor_name]["neighbors"]:
                raise ValueError(f"Generated edge {region_name}-{neighbor_name} is not bidirectional.")


def build_generated_map_definition(
    map_name: str,
    num_factions: int,
    config: MapGenerationConfig | Mapping[str, object] | None = None,
) -> dict:
    if num_factions < 1:
        raise ValueError("Generated maps require at least one faction.")

    generation_config = (
        config
        if isinstance(config, MapGenerationConfig)
        else build_generation_config(map_name, num_factions, config)
    )
    rng = random.Random(generation_config.seed)
    regions = _generate_region_points(generation_config, rng)
    _build_land_graph(regions, generation_config, rng)
    river_paths = _assign_terrain_and_climate(regions, generation_config, rng)

    for region in regions.values():
        region["resources"] = _resource_value_for_region(region, generation_config, rng)

    _assign_starting_regions(regions, num_factions, generation_config)
    for region in regions.values():
        region["neighbors"] = sorted(region["neighbors"], key=lambda name: (len(name), name))

    sea_links, river_links = _build_links(regions, river_paths)
    definition = {
        "description": (
            f"Generated {generation_config.style} world with {len(regions)} regions, "
            f"{generation_config.landmass_count} landmass(es), {num_factions} faction homelands, "
            f"{len(river_paths)} river system(s), and geography-driven terrain."
        ),
        "generated": True,
        "style": generation_config.style,
        "seed": generation_config.seed,
        "config": asdict(generation_config),
        "sea_links": sea_links,
        "river_links": river_links,
        "regions": regions,
    }
    _validate_generated_map(definition, num_factions)
    return definition
