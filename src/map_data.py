old_simplified_territory_map = {
    "Northern Virginia": {"neighbors": ["Shenandoah Valley", "Central Virginia", "Washington, D.C."], "owner": None, "armies": 1},
    "Shenandoah Valley": {"neighbors": ["Northern Virginia", "Central Virginia", "Southwestern Virginia", "West Virginia"], "owner": None, "armies": 2},
    "Tidewater": {"neighbors": ["Central Virginia", "Southside"], "owner": None, "armies": 3},
    "Southside": {"neighbors": ["Central Virginia", "Tidewater", "Southwestern Virginia"], "owner": None, "armies": 4},
    "Central Virginia": {"neighbors": ["Northern Virginia", "Shenandoah Valley", "Tidewater", "Southside"], "owner": None, "armies": 5},
    "Southwestern Virginia": {"neighbors": ["Shenandoah Valley", "Southside", "West Virginia"], "owner": None, "armies": 6},
    "Washington, D.C.": {"neighbors": ["Northern Virginia"], "owner": None, "armies": 100},
    "West Virginia": {"neighbors": ["Shenandoah Valley", "Southwestern Virginia"], "owner": None, "armies": 3},

}

simplified_territory_map = {
    # Virginia
    "Northern Virginia": {
        "neighbors": ["Shenandoah Valley", "Central Virginia", "Washington, D.C."],
        "owner": None,
        "armies": 1,
        "coords": (-77.5, 38.8),
    },
    "Shenandoah Valley": {
        "neighbors": ["Northern Virginia", "Central Virginia", "Southwestern Virginia"],
        "owner": None,
        "armies": 2,
        "coords": (-78.7, 38.2),
    },
    "Tidewater": {
        "neighbors": ["Central Virginia", "Southside"],
        "owner": None,
        "armies": 3,
        "coords": (-76.3, 37.1),
    },
    "Southside": {
        "neighbors": ["Central Virginia", "Tidewater", "Southwestern Virginia"],
        "owner": None,
        "armies": 0,
        "coords": (-78.9, 36.7),
    },
    "Central Virginia": {
        "neighbors": ["Northern Virginia", "Shenandoah Valley", "Tidewater", "Southside"],
        "owner": None,
        "armies": 0,
        "coords": (-78.0, 37.5),
    },
    "Southwestern Virginia": {
        "neighbors": ["Shenandoah Valley", "Southside"],
        "owner": None,
        "armies": 0,
        "coords": (-81.1, 37.3),
    },
    # Washington, D.C.
    "Washington, D.C.": {
        "neighbors": ["Northern Virginia"],
        "owner": None,
        "armies": 0,
        "coords": (-77.0, 38.9),
    },
}

#"Greater Virginia Map"
greater_virginia_territory_map = {
    # Virginia
    "Northern Virginia": {"neighbors": ["Shenandoah Valley", "Central Virginia", "Washington, D.C.", "Maryland"], "owner": None, "armies": 1},
    "Shenandoah Valley": {"neighbors": ["Northern Virginia", "Central Virginia", "Southwestern Virginia", "West Virginia"], "owner": None, "armies": 2},
    "Tidewater": {"neighbors": ["Central Virginia", "Southside", "Delaware"], "owner": None, "armies": 3},
    "Southside": {"neighbors": ["Central Virginia", "Tidewater", "Southwestern Virginia", "North Carolina"], "owner": None, "armies": 0},
    "Central Virginia": {"neighbors": ["Northern Virginia", "Shenandoah Valley", "Tidewater", "Southside"], "owner": None, "armies": 0},
    "Southwestern Virginia": {"neighbors": ["Shenandoah Valley", "Southside", "West Virginia", "Tennessee"], "owner": None, "armies": 0},

    # West Virginia
    "Northern Panhandle": {"neighbors": ["Eastern Panhandle", "Kanawha Valley", "Pennsylvania"], "owner": None, "armies": 0},
    "Eastern Panhandle": {"neighbors": ["Northern Panhandle", "Shenandoah Valley", "Maryland"], "owner": None, "armies": 0},
    "Kanawha Valley": {"neighbors": ["Northern Panhandle", "Southern Coalfields", "Southwestern Virginia"], "owner": None, "armies": 0},
    "Southern Coalfields": {"neighbors": ["Kanawha Valley", "Southwestern Virginia", "Kentucky"], "owner": None, "armies": 0},

    # Maryland
    "Western Maryland": {"neighbors": ["West Virginia", "Baltimore Metro", "Pennsylvania"], "owner": None, "armies": 0},
    "Baltimore Metro": {"neighbors": ["Southern Maryland", "Eastern Shore", "Western Maryland", "Philadelphia Metro"], "owner": None, "armies": 0},
    "Eastern Shore": {"neighbors": ["Baltimore Metro", "Delaware"],    "owner": None, "armies": 0},
    "Southern Maryland": {"neighbors": ["Baltimore Metro", "Washington, D.C.", "Northern Virginia"], "owner": None, "armies": 0},

    # Washington, D.C.
    "Washington, D.C.": {"neighbors": ["Northern Virginia", "Southern Maryland"], "owner": None, "armies": 0},

    # Delaware
    "New Castle": {"neighbors": ["Maryland", "Kent"], "owner": None, "armies": 0},
    "Kent": {"neighbors": ["New Castle", "Sussex"], "owner": None, "armies": 0},
    "Sussex": {"neighbors": ["Kent", "Tidewater"], "owner": None, "armies": 0},

    # Ohio
    "Northern Ohio": {"neighbors": ["Central Ohio", "Pennsylvania"], "owner": None, "armies": 0},
    "Central Ohio": {"neighbors": ["Northern Ohio", "Southwest Ohio", "Appalachian Ohio"], "owner": None, "armies": 0},
    "Appalachian Ohio": {"neighbors": ["Central Ohio", "Southwest Ohio", "West Virginia"], "owner": None, "armies": 0},
    "Northwest Ohio": {"neighbors": ["Central Ohio"], "owner": None, "armies": 0},
    "Southwest Ohio": {"neighbors": ["Central Ohio", "Appalachian Ohio", "Kentucky"], "owner": None, "armies": 0},

    # Kentucky
    "Bluegrass Region": {"neighbors": ["Eastern Coalfields", "Northern Kentucky", "Southwest Ohio"], "owner": None, "armies": 0},
    "Eastern Coalfields": {"neighbors": ["Bluegrass Region", "Southern Coalfields"], "owner": None, "armies": 0},
    "Jackson Purchase": {"neighbors": ["Pennyroyal Plateau", "Tennessee"], "owner": None, "armies": 0},
    "Pennyroyal Plateau": {"neighbors": ["Jackson Purchase", "Northern Kentucky"], "owner": None, "armies": 0},
    "Northern Kentucky": {"neighbors": ["Bluegrass Region", "Pennyroyal Plateau", "Southwest Ohio"], "owner": None, "armies": 0},

    # Tennessee
    "West Tennessee": {"neighbors": ["Middle Tennessee", "Jackson Purchase"], "owner": None, "armies": 0},
    "Middle Tennessee": {"neighbors": ["West Tennessee", "East Tennessee", "Cumberland Plateau"], "owner": None, "armies": 0},
    "East Tennessee": {"neighbors": ["Middle Tennessee", "Cumberland Plateau", "North Carolina"], "owner": None, "armies": 0},
    "Great Smoky Mountains": {"neighbors": ["East Tennessee", "North Carolina"], "owner": None, "armies": 0},
    "Cumberland Plateau": {"neighbors": ["Middle Tennessee", "East Tennessee", "Southwestern Virginia"], "owner": None, "armies": 0},

    # North Carolina
    "Coastal Plain": {"neighbors": ["Outer Banks", "Piedmont", "Sandhills"], "owner": None, "armies": 0},
    "Outer Banks": {"neighbors": ["Coastal Plain"], "owner": "Player 1", "armies": 10},
    "Piedmont": {"neighbors": ["Coastal Plain", "Charlotte Metro", "Appalachian Mountains"], "owner": None, "armies": 0},
    "Sandhills": {"neighbors": ["Coastal Plain", "Charlotte Metro"], "owner": None, "armies": 0},
    "Charlotte Metro": {"neighbors": ["Piedmont", "Sandhills", "Appalachian Mountains"], "owner": None, "armies": 0},
    "Appalachian Mountains": {"neighbors": ["Piedmont", "Charlotte Metro", "Great Smoky Mountains"], "owner": None, "armies": 0},

    # Pennsylvania
    "Philadelphia Metro": {"neighbors": ["Baltimore Metro", "Lehigh Valley", "New Jersey"], "owner": None, "armies": 0},
    "Lehigh Valley": {"neighbors": ["Philadelphia Metro", "Central Pennsylvania"], "owner": None, "armies": 0},
    "Pittsburgh Metro": {"neighbors": ["Central Pennsylvania", "Northern Panhandle"], "owner": None, "armies": 0},
    "Central Pennsylvania": {"neighbors": ["Lehigh Valley", "Pittsburgh Metro", "Northern Panhandle"], "owner": None, "armies": 0},
    "Erie": {"neighbors": ["Northern Ohio"], "owner": None, "armies": 0},

    # New Jersey
    "North Jersey": {"neighbors": ["Central Jersey", "New York"], "owner": None, "armies": 0},
    "Central Jersey": {"neighbors": ["North Jersey", "South Jersey", "Philadelphia Metro"], "owner": None, "armies": 0},
    "South Jersey": {"neighbors": ["Central Jersey", "Delaware"], "owner": None, "armies": 0},
}
