import random

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
