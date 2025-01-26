import random
from rules import game_rules


def resolve_combat(attacker_armies, defender_armies):
    """
    Simulates combat between attacker and defender using dice rolls.
    
    Args:
        attacker_armies (int): Number of armies attacking.
        defender_armies (int): Number of armies defending.
    
    Returns:
        dict: Remaining armies for attacker and defender.
    """
    # Ensure both sides roll the correct number of dice
    attacker_rolls = sorted([random.randint(1, 6) for _ in range(min(attacker_armies, 3))], reverse=True)
    defender_rolls = sorted([random.randint(1, 6) for _ in range(min(defender_armies, 2))], reverse=True)
    
    # Compare rolls
    attacker_losses = 0
    defender_losses = 0
    for attack, defend in zip(attacker_rolls, defender_rolls):
        if attack > defend:
            defender_losses += 1
        else:
            attacker_losses += 1

    return {
        "attacker_remaining": attacker_armies - attacker_losses,
        "defender_remaining": defender_armies - defender_losses,
    }


def calculate_reinforcements(player_territories):
    base_rate = game_rules["reinforcements"]["base_rate"]
    territory_bonus = player_territories // game_rules["reinforcements"]["territory_bonus_rate"]
    return base_rate + territory_bonus

# Test reinforcement calculation
player_territories = 12
# print(f"Reinforcements: {calculate_reinforcements(player_territories)}")  # Output: Reinforcements: 7

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
# print(resolve_battle(5, 3))  # Output: Example: {'attacker': 1, 'defender': 2}

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
