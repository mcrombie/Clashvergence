def _add_bidirectional_neighbor(regions, region_name, neighbor_name):
    """Adds an undirected connection between two regions."""
    if neighbor_name not in regions[region_name]["neighbors"]:
        regions[region_name]["neighbors"].append(neighbor_name)
    if region_name not in regions[neighbor_name]["neighbors"]:
        regions[neighbor_name]["neighbors"].append(region_name)


def _build_multi_ring_symmetry():
    """Builds a large symmetric map with three rings and a single center."""
    regions = {}

    outer_names = [f"O{i}" for i in range(1, 17)]
    middle_names = [f"M{i}" for i in range(1, 13)]
    inner_names = [f"I{i}" for i in range(1, 9)]
    center_name = "C"

    starting_owners = {
        "O1": "Faction1",
        "O5": "Faction2",
        "O9": "Faction3",
        "O13": "Faction4",
    }

    for region_name in outer_names:
        regions[region_name] = {
            "neighbors": [],
            "owner": starting_owners.get(region_name),
            "resources": 2,
        }

    for region_name in middle_names:
        regions[region_name] = {"neighbors": [], "owner": None, "resources": 2}

    for region_name in inner_names:
        regions[region_name] = {"neighbors": [], "owner": None, "resources": 3}

    regions[center_name] = {"neighbors": [], "owner": None, "resources": 3}

    for ring_names in (outer_names, middle_names, inner_names):
        ring_size = len(ring_names)
        for index, region_name in enumerate(ring_names):
            next_region = ring_names[(index + 1) % ring_size]
            _add_bidirectional_neighbor(regions, region_name, next_region)

    for inner_name in inner_names:
        _add_bidirectional_neighbor(regions, inner_name, center_name)

    for quadrant_index in range(4):
        outer_offset = quadrant_index * 4
        middle_offset = quadrant_index * 3
        inner_offset = quadrant_index * 2

        outer_a = outer_names[outer_offset]
        outer_b = outer_names[outer_offset + 1]
        outer_c = outer_names[outer_offset + 2]
        outer_d = outer_names[outer_offset + 3]

        middle_a = middle_names[middle_offset]
        middle_b = middle_names[middle_offset + 1]
        middle_c = middle_names[middle_offset + 2]

        inner_a = inner_names[inner_offset]
        inner_b = inner_names[inner_offset + 1]

        _add_bidirectional_neighbor(regions, outer_a, middle_a)
        _add_bidirectional_neighbor(regions, outer_b, middle_a)
        _add_bidirectional_neighbor(regions, outer_b, middle_b)
        _add_bidirectional_neighbor(regions, outer_c, middle_b)
        _add_bidirectional_neighbor(regions, outer_c, middle_c)
        _add_bidirectional_neighbor(regions, outer_d, middle_c)

        _add_bidirectional_neighbor(regions, middle_a, inner_a)
        _add_bidirectional_neighbor(regions, middle_b, inner_a)
        _add_bidirectional_neighbor(regions, middle_b, inner_b)
        _add_bidirectional_neighbor(regions, middle_c, inner_b)

    return regions


MAPS = {
    "seven_region_ring": {
        "description": "Seven regions and three factions, where each faction starts bordering three unoccupied regions.",
        "regions": {
            "A": {"neighbors": ["B", "F", "M"], "owner": "Faction1", "resources": 2},
            "B": {"neighbors": ["A", "C", "M"], "owner": None, "resources": 2},
            "C": {"neighbors": ["B", "D", "M"], "owner": "Faction2", "resources": 2},
            "D": {"neighbors": ["C", "E", "M"], "owner": None, "resources": 2},
            "E": {"neighbors": ["D", "F", "M"], "owner": "Faction3", "resources": 2},
            "F": {"neighbors": ["E", "A", "M"], "owner": None, "resources": 2},
            "M": {"neighbors": ["A", "B", "C", "D", "E", "F"], "owner": None, "resources": 2},
        },
    },

    "ten_region_ring": {
        "description": "Ten regions with a nine-region outer ring and one center region.",
        "regions": {
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
        },
    },

    "thirteen_region_ring": {
        "description": "Thirteen regions with a twelve-region outer ring and one center region, designed for four factions.",
        "regions": {
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
        },
    },

    "asymmetric_frontier": {
        "description": "A non-ring asymmetric map with chokepoints, uneven connectivity, and uneven four-faction starting positions.",
        "regions": {
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
        },
    },

    "multi_ring_symmetry": {
        "description": (
            "Thirty-seven regions arranged in three concentric rings around a single center, "
            "with four factions equally spaced on the outer ring."
        ),
        "regions": _build_multi_ring_symmetry(),
    },
}
