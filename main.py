#Tinkering with basic territory map models
map_data = {
    "Territory_1": {"owner": None, "armies": 0, "neighbors": ["Territory_2"]},
    "Territory_2": {"owner": None, "armies": 0, "neighbors": ["Territory_1", "Territory_3"]},
    "Territory_3": {"owner": None, "armies": 0, "neighbors": ["Territory_2"]},
}

def print_map():
    for territory, details in map_data.items():
        print(f"{territory}: Owner={details['owner']}, Armies={details['armies']}, Neighbors={details['neighbors']}")

if __name__ == "__main__":
    print_map()

    import random

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
        "max_attacker_dice": 3,  # Maximum dice the attacker can roll
        "max_defender_dice": 2,  # Maximum dice the defender can roll
        "combat_mechanics": "highest_roll",  # How battles are resolved
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


def calculate_reinforcements(player_territories):
    base_rate = game_rules["reinforcements"]["base_rate"]
    territory_bonus = player_territories // game_rules["reinforcements"]["territory_bonus_rate"]
    return base_rate + territory_bonus

# Test reinforcement calculation
player_territories = 12
print(f"Reinforcements: {calculate_reinforcements(player_territories)}")  # Output: Reinforcements: 7

import random

def resolve_battle(attacker_armies, defender_armies):
    max_attacker_dice = min(attacker_armies, game_rules["combat"]["max_attacker_dice"])
    max_defender_dice = min(defender_armies, game_rules["combat"]["max_defender_dice"])
    
    attacker_rolls = sorted([random.randint(1, 6) for _ in range(max_attacker_dice)], reverse=True)
    defender_rolls = sorted([random.randint(1, 6) for _ in range(max_defender_dice)], reverse=True)
    
    losses = {"attacker": 0, "defender": 0}
    for a, d in zip(attacker_rolls, defender_rolls):
        if a > d:
            losses["defender"] += 1
        else:
            losses["attacker"] += 1
    return losses

# Test combat resolution
print(resolve_battle(5, 3))  # Output: Example: {'attacker': 1, 'defender': 2}

def check_victory(player_territories, total_territories, opponents_remaining):
    if game_rules["victory_conditions"]["control_all_territories"]:
        if player_territories == total_territories:
            return "Victory by controlling all territories"
    
    if game_rules["victory_conditions"]["eliminate_opponents"]:
        if opponents_remaining == 0:
            return "Victory by eliminating all opponents"
    
    if game_rules["victory_conditions"]["optional_score_threshold"]:
        threshold = game_rules["victory_conditions"]["optional_score_threshold"]
        if (player_territories / total_territories) * 100 >= threshold:
            return f"Victory by controlling {threshold}% of the map"
    
    return "No victory yet"

# Test victory check
print(check_victory(50, 100, 0))  # Output: Victory by eliminating all opponents

