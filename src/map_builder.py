def add_bidirectional_neighbor(regions, region_name, neighbor_name):
    """Adds an undirected connection between two regions."""
    if neighbor_name not in regions[region_name]["neighbors"]:
        regions[region_name]["neighbors"].append(neighbor_name)
    if region_name not in regions[neighbor_name]["neighbors"]:
        regions[neighbor_name]["neighbors"].append(region_name)


def build_multi_ring_symmetry():
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
        regions[region_name] = {"neighbors": [], "owner": None, "resources": 2}

    regions[center_name] = {"neighbors": [], "owner": None, "resources": 2}

    for ring_names in (outer_names, middle_names, inner_names):
        ring_size = len(ring_names)
        for index, region_name in enumerate(ring_names):
            next_region = ring_names[(index + 1) % ring_size]
            add_bidirectional_neighbor(regions, region_name, next_region)

    for inner_name in inner_names:
        add_bidirectional_neighbor(regions, inner_name, center_name)

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

        add_bidirectional_neighbor(regions, outer_a, middle_a)
        add_bidirectional_neighbor(regions, outer_b, middle_a)
        add_bidirectional_neighbor(regions, outer_b, middle_b)
        add_bidirectional_neighbor(regions, outer_c, middle_b)
        add_bidirectional_neighbor(regions, outer_c, middle_c)
        add_bidirectional_neighbor(regions, outer_d, middle_c)

        add_bidirectional_neighbor(regions, middle_a, inner_a)
        add_bidirectional_neighbor(regions, middle_b, inner_a)
        add_bidirectional_neighbor(regions, middle_b, inner_b)
        add_bidirectional_neighbor(regions, middle_c, inner_b)

    return regions
