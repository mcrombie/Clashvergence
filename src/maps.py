MAPS = {
    "seven_region_ring": {
        "description": "Seven regions and three factions, each faction starts bordering three unoccupied regions.",
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
}