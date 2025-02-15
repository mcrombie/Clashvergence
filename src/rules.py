# Basic Game Rules
game_rules = {
    # Turn order and game flow
    "game_flow": {
        "turn_order": ["Player_1", "Player_2", "Player_3"],  # Adjust based on players
        "max_turns": 50,  # Optional: maximum number of turns before a draw
    },

    # Map settings
    "map": {
        "territories_per_player": 10,  # Number of territories each player starts with
        "region_bonus": {  # Bonuses for controlling regions
            "Region_A": 5,
            "Region_B": 3,
            "Region_C": 7,
        },
    },

    # Reinforcement rules
    "reinforcements": {
        "base_rate": 3,  # Minimum armies received per turn
        "territory_bonus_rate": 3,  # 1 reinforcement per X territories
    },

    # Combat rules
    "combat": {
        "combat_mechanics": "winner-take-all",  # How battles are resolved
    },

    # Movement rules
    "movement": {
        "allowed_once_per_turn": True,  # Can armies move only once per turn?
        "requires_connection": True,  # Armies can only move through connected territories
    },

    # Victory conditions
    "victory_conditions": {
        "control_all_territories": True,  # Win by controlling the whole map
        "eliminate_opponents": True,  # Win by eliminating all opponents
        "optional_score_threshold": 70,  # Optional: Control 70% of the map for victory
    },
}

continent_bonuses = {
    "Virginia": 5,
    "West Virginia": 2,
    "Maryland": 3,
    "Delaware": 2,
    "Ohio": 4,
    "Kentucky": 3,
    "Tennessee": 4,
    "North Carolina": 5,
    "Pennsylvania": 5,
    "New Jersey": 3
}
