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
}