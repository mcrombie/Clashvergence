from src.map_builder import build_multi_ring_symmetry


def _copy_regions_with_terrain(
    regions,
    terrain_lookup,
    climate_lookup=None,
    default_tags=("plains",),
    default_climate="temperate",
):
    copied = {}
    for region_name, region_data in regions.items():
        copied[region_name] = {
            "neighbors": list(region_data["neighbors"]),
            "owner": region_data["owner"],
            "resources": region_data["resources"],
            "terrain_tags": list(terrain_lookup.get(region_name, default_tags)),
            "climate": (climate_lookup or {}).get(region_name, default_climate),
        }
    return copied


def _build_single_ring_terrain(outer_names, center_name):
    cycle = [
        ["coast", "forest"],
        ["plains"],
        ["forest"],
        ["hills", "forest"],
    ]
    terrain_lookup = {}
    for index, region_name in enumerate(outer_names):
        terrain_lookup[region_name] = cycle[index % len(cycle)]
    terrain_lookup[center_name] = ["riverland", "plains"]
    return terrain_lookup


def _build_three_ring_terrain(outer_names, middle_names, inner_names, center_name):
    terrain_lookup = {}

    outer_cycle = [
        ["coast", "forest"],
        ["coast", "plains"],
        ["coast", "marsh"],
        ["coast", "forest"],
    ]
    for index, region_name in enumerate(outer_names):
        terrain_lookup[region_name] = outer_cycle[index % len(outer_cycle)]

    middle_cycle = [
        ["plains"],
        ["forest"],
        ["riverland", "plains"],
        ["hills", "forest"],
    ]
    for index, region_name in enumerate(middle_names):
        terrain_lookup[region_name] = middle_cycle[index % len(middle_cycle)]

    inner_cycle = [
        ["highland", "forest"],
        ["highland", "plains"],
        ["riverland", "hills"],
        ["highland", "forest"],
    ]
    for index, region_name in enumerate(inner_names):
        terrain_lookup[region_name] = inner_cycle[index % len(inner_cycle)]

    terrain_lookup[center_name] = ["riverland", "plains"]
    return terrain_lookup


def _build_three_ring_climate(outer_names, middle_names, inner_names, center_name):
    climate_lookup = {}

    for region_name in outer_names:
        climate_lookup[region_name] = "oceanic"

    for region_name in middle_names:
        climate_lookup[region_name] = "temperate"

    for region_name in inner_names:
        climate_lookup[region_name] = "cold"

    climate_lookup[center_name] = "temperate"
    return climate_lookup


def _build_asymmetric_frontier_terrain():
    return {
        "A": ["plains"],
        "B": ["forest"],
        "C": ["riverland", "forest"],
        "D": ["hills"],
        "E": ["riverland", "plains"],
        "F": ["marsh"],
        "G": ["highland", "forest"],
        "H": ["forest", "hills"],
        "I": ["plains"],
        "J": ["highland", "steppe"],
        "K": ["riverland", "forest"],
        "L": ["marsh", "forest"],
    }


SEVEN_REGION_RING_REGIONS = {
    "A": {"neighbors": ["B", "F", "M"], "owner": "Faction1", "resources": 2},
    "B": {"neighbors": ["A", "C", "M"], "owner": None, "resources": 2},
    "C": {"neighbors": ["B", "D", "M"], "owner": "Faction2", "resources": 2},
    "D": {"neighbors": ["C", "E", "M"], "owner": None, "resources": 2},
    "E": {"neighbors": ["D", "F", "M"], "owner": "Faction3", "resources": 2},
    "F": {"neighbors": ["E", "A", "M"], "owner": None, "resources": 2},
    "M": {"neighbors": ["A", "B", "C", "D", "E", "F"], "owner": None, "resources": 2},
}

TEN_REGION_RING_REGIONS = {
    "A": {"neighbors": ["B", "I", "M"], "owner": "Faction1", "resources": 2},
    "B": {"neighbors": ["A", "C", "M"], "owner": None, "resources": 2},
    "C": {"neighbors": ["B", "D", "M"], "owner": None, "resources": 2},
    "D": {"neighbors": ["C", "E", "M"], "owner": "Faction2", "resources": 2},
    "E": {"neighbors": ["D", "F", "M"], "owner": None, "resources": 2},
    "F": {"neighbors": ["E", "G", "M"], "owner": None, "resources": 2},
    "G": {"neighbors": ["F", "H", "M"], "owner": "Faction3", "resources": 2},
    "H": {"neighbors": ["G", "I", "M"], "owner": None, "resources": 2},
    "I": {"neighbors": ["H", "A", "M"], "owner": None, "resources": 2},
    "M": {"neighbors": ["A", "B", "C", "D", "E", "F", "G", "H", "I"], "owner": None, "resources": 2},
}

THIRTEEN_REGION_RING_REGIONS = {
    "A": {"neighbors": ["B", "L", "M"], "owner": "Faction1", "resources": 2},
    "B": {"neighbors": ["A", "C", "M"], "owner": None, "resources": 2},
    "C": {"neighbors": ["B", "D", "M"], "owner": None, "resources": 2},
    "D": {"neighbors": ["C", "E", "M"], "owner": "Faction2", "resources": 2},
    "E": {"neighbors": ["D", "F", "M"], "owner": None, "resources": 2},
    "F": {"neighbors": ["E", "G", "M"], "owner": None, "resources": 2},
    "G": {"neighbors": ["F", "H", "M"], "owner": "Faction3", "resources": 2},
    "H": {"neighbors": ["G", "I", "M"], "owner": None, "resources": 2},
    "I": {"neighbors": ["H", "J", "M"], "owner": None, "resources": 2},
    "J": {"neighbors": ["I", "K", "M"], "owner": "Faction4", "resources": 2},
    "K": {"neighbors": ["J", "L", "M"], "owner": None, "resources": 2},
    "L": {"neighbors": ["K", "A", "M"], "owner": None, "resources": 2},
    "M": {
        "neighbors": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"],
        "owner": None,
        "resources": 2,
    },
}

SEVENTEEN_REGION_RING_REGIONS = {
    "A": {"neighbors": ["B", "P", "Q"], "owner": "Faction1", "resources": 2},
    "B": {"neighbors": ["A", "C", "Q"], "owner": None, "resources": 2},
    "C": {"neighbors": ["B", "D", "Q"], "owner": None, "resources": 2},
    "D": {"neighbors": ["C", "E", "Q"], "owner": None, "resources": 2},
    "E": {"neighbors": ["D", "F", "Q"], "owner": "Faction2", "resources": 2},
    "F": {"neighbors": ["E", "G", "Q"], "owner": None, "resources": 2},
    "G": {"neighbors": ["F", "H", "Q"], "owner": None, "resources": 2},
    "H": {"neighbors": ["G", "I", "Q"], "owner": None, "resources": 2},
    "I": {"neighbors": ["H", "J", "Q"], "owner": "Faction3", "resources": 2},
    "J": {"neighbors": ["I", "K", "Q"], "owner": None, "resources": 2},
    "K": {"neighbors": ["J", "L", "Q"], "owner": None, "resources": 2},
    "L": {"neighbors": ["K", "M", "Q"], "owner": None, "resources": 2},
    "M": {"neighbors": ["L", "N", "Q"], "owner": "Faction4", "resources": 2},
    "N": {"neighbors": ["M", "O", "Q"], "owner": None, "resources": 2},
    "O": {"neighbors": ["N", "P", "Q"], "owner": None, "resources": 2},
    "P": {"neighbors": ["O", "A", "Q"], "owner": None, "resources": 2},
    "Q": {
        "neighbors": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P"],
        "owner": None,
        "resources": 2,
    },
}

THIRTY_SEVEN_REGION_RING_REGIONS = {
    "O1": {"neighbors": ["O16", "O2", "M1"], "owner": None, "resources": 2},
    "O2": {"neighbors": ["O1", "O3", "M1", "M2"], "owner": None, "resources": 2},
    "O3": {"neighbors": ["O2", "O4", "M2", "M3"], "owner": None, "resources": 2},
    "O4": {"neighbors": ["O3", "O5", "M3"], "owner": None, "resources": 2},
    "O5": {"neighbors": ["O4", "O6", "M4"], "owner": None, "resources": 2},
    "O6": {"neighbors": ["O5", "O7", "M4", "M5"], "owner": None, "resources": 2},
    "O7": {"neighbors": ["O6", "O8", "M5", "M6"], "owner": None, "resources": 2},
    "O8": {"neighbors": ["O7", "O9", "M6"], "owner": None, "resources": 2},
    "O9": {"neighbors": ["O8", "O10", "M7"], "owner": None, "resources": 2},
    "O10": {"neighbors": ["O9", "O11", "M7", "M8"], "owner": None, "resources": 2},
    "O11": {"neighbors": ["O10", "O12", "M8", "M9"], "owner": None, "resources": 2},
    "O12": {"neighbors": ["O11", "O13", "M9"], "owner": None, "resources": 2},
    "O13": {"neighbors": ["O12", "O14", "M10"], "owner": None, "resources": 2},
    "O14": {"neighbors": ["O13", "O15", "M10", "M11"], "owner": None, "resources": 2},
    "O15": {"neighbors": ["O14", "O16", "M11", "M12"], "owner": None, "resources": 2},
    "O16": {"neighbors": ["O15", "O1", "M12"], "owner": None, "resources": 2},
    "M1": {"neighbors": ["M12", "M2", "O1", "O2", "I1", "I2"], "owner": "Faction1", "resources": 2},
    "M2": {"neighbors": ["M1", "M3", "O2", "O3", "I2"], "owner": None, "resources": 2},
    "M3": {"neighbors": ["M2", "M4", "O3", "O4", "I2", "I3"], "owner": None, "resources": 2},
    "M4": {"neighbors": ["M3", "M5", "O5", "O6", "I3", "I4"], "owner": "Faction2", "resources": 2},
    "M5": {"neighbors": ["M4", "M6", "O6", "O7", "I4"], "owner": None, "resources": 2},
    "M6": {"neighbors": ["M5", "M7", "O7", "O8", "I4", "I5"], "owner": None, "resources": 2},
    "M7": {"neighbors": ["M6", "M8", "O9", "O10", "I5", "I6"], "owner": "Faction3", "resources": 2},
    "M8": {"neighbors": ["M7", "M9", "O10", "O11", "I6"], "owner": None, "resources": 2},
    "M9": {"neighbors": ["M8", "M10", "O11", "O12", "I6", "I7"], "owner": None, "resources": 2},
    "M10": {"neighbors": ["M9", "M11", "O13", "O14", "I7", "I8"], "owner": "Faction4", "resources": 2},
    "M11": {"neighbors": ["M10", "M12", "O14", "O15", "I8"], "owner": None, "resources": 2},
    "M12": {"neighbors": ["M11", "M1", "O15", "O16", "I8", "I1"], "owner": None, "resources": 2},
    "I1": {"neighbors": ["I8", "I2", "M1", "M12", "C"], "owner": None, "resources": 2},
    "I2": {"neighbors": ["I1", "I3", "M1", "M2", "M3", "C"], "owner": None, "resources": 2},
    "I3": {"neighbors": ["I2", "I4", "M3", "M4", "C"], "owner": None, "resources": 2},
    "I4": {"neighbors": ["I3", "I5", "M4", "M5", "M6", "C"], "owner": None, "resources": 2},
    "I5": {"neighbors": ["I4", "I6", "M6", "M7", "C"], "owner": None, "resources": 2},
    "I6": {"neighbors": ["I5", "I7", "M7", "M8", "M9", "C"], "owner": None, "resources": 2},
    "I7": {"neighbors": ["I6", "I8", "M9", "M10", "C"], "owner": None, "resources": 2},
    "I8": {"neighbors": ["I7", "I1", "M10", "M11", "M12", "C"], "owner": None, "resources": 2},
    "C": {"neighbors": ["I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"], "owner": None, "resources": 2},
}

ASYMMETRIC_FRONTIER_REGIONS = {
    "A": {"neighbors": ["B", "C"], "owner": "Faction1", "resources": 2},
    "B": {"neighbors": ["A", "D", "E"], "owner": None, "resources": 1},
    "C": {"neighbors": ["A", "E", "F"], "owner": None, "resources": 3},
    "D": {"neighbors": ["B", "E", "G"], "owner": "Faction2", "resources": 2},
    "E": {"neighbors": ["B", "C", "D", "F", "H"], "owner": None, "resources": 2},
    "F": {"neighbors": ["C", "E", "I"], "owner": None, "resources": 1},
    "G": {"neighbors": ["D", "H", "J"], "owner": None, "resources": 3},
    "H": {"neighbors": ["E", "G", "I", "K"], "owner": None, "resources": 2},
    "I": {"neighbors": ["F", "H", "L"], "owner": "Faction3", "resources": 2},
    "J": {"neighbors": ["G", "K"], "owner": "Faction4", "resources": 1},
    "K": {"neighbors": ["H", "J", "L"], "owner": None, "resources": 3},
    "L": {"neighbors": ["I", "K"], "owner": None, "resources": 2},
}

MULTI_RING_SYMMETRY_REGIONS = build_multi_ring_symmetry()


MAPS = {
    "seven_region_ring": {
        "description": "Seven regions and three factions, where each faction starts bordering three unoccupied regions.",
        "regions": _copy_regions_with_terrain(
            SEVEN_REGION_RING_REGIONS,
            _build_single_ring_terrain(["A", "B", "C", "D", "E", "F"], "M"),
        ),
    },

    "ten_region_ring": {
        "description": "Ten regions with a nine-region outer ring and one center region.",
        "regions": _copy_regions_with_terrain(
            TEN_REGION_RING_REGIONS,
            _build_single_ring_terrain(["A", "B", "C", "D", "E", "F", "G", "H", "I"], "M"),
        ),
    },

    "thirteen_region_ring": {
        "description": "Thirteen regions with a twelve-region outer ring and one center region, designed for four factions.",
        "regions": _copy_regions_with_terrain(
            THIRTEEN_REGION_RING_REGIONS,
            _build_single_ring_terrain(["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"], "M"),
        ),
    },

    "seventeen_region_ring": {
        "description": "Seventeen regions with a sixteen-region outer ring and one center region, designed for four factions.",
        "regions": _copy_regions_with_terrain(
            SEVENTEEN_REGION_RING_REGIONS,
            _build_single_ring_terrain(
                ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P"],
                "Q",
            ),
        ),
    },

    "thirty_seven_region_ring": {
        "description": "Thirty-seven regions arranged as a sixteen-region outer ring, a twelve-region middle ring, an eight-region inner ring, and one center region.",
        "regions": _copy_regions_with_terrain(
            THIRTY_SEVEN_REGION_RING_REGIONS,
            _build_three_ring_terrain(
                [f"O{i}" for i in range(1, 17)],
                [f"M{i}" for i in range(1, 13)],
                [f"I{i}" for i in range(1, 9)],
                "C",
            ),
            _build_three_ring_climate(
                [f"O{i}" for i in range(1, 17)],
                [f"M{i}" for i in range(1, 13)],
                [f"I{i}" for i in range(1, 9)],
                "C",
            ),
        ),
    },

    "asymmetric_frontier": {
        "description": "A non-ring asymmetric map with chokepoints, uneven connectivity, and uneven four-faction starting positions.",
        "regions": _copy_regions_with_terrain(
            ASYMMETRIC_FRONTIER_REGIONS,
            _build_asymmetric_frontier_terrain(),
        ),
    },

    "multi_ring_symmetry": {
        "description": (
            "Thirty-seven regions arranged in three concentric rings around a single center, "
            "with four factions equally spaced on the outer ring."
        ),
        "regions": _copy_regions_with_terrain(
            MULTI_RING_SYMMETRY_REGIONS,
            _build_three_ring_terrain(
                [f"O{i}" for i in range(1, 17)],
                [f"M{i}" for i in range(1, 13)],
                [f"I{i}" for i in range(1, 9)],
                "C",
            ),
            _build_three_ring_climate(
                [f"O{i}" for i in range(1, 17)],
                [f"M{i}" for i in range(1, 13)],
                [f"I{i}" for i in range(1, 9)],
                "C",
            ),
        ),
    },
}
