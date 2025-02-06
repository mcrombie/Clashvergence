import random

def roll_dice(num_dice):
    """Rolls a given number of 6-sided dice and returns a sorted list."""
    return sorted([random.randint(1, 6) for _ in range(num_dice)], reverse=True)

def battle(attacker, defender, map_data):
    """
    Simulates a battle between two territories.
    - attacker: Attacking territory name (string)
    - defender: Defending territory name (string)
    - map_data: Dictionary containing territory information
    """
    
    # Get army counts
    attacker_armies = map_data[attacker]["armies"]
    defender_armies = map_data[defender]["armies"]

    print(attacker_armies)

    if attacker_armies < 2:
        print("Not enough armies to attack!")
        return
    
    # Attacker rolls up to 3 dice (cannot roll more dice than they have armies - 1)
    attacker_dice = min(attacker_armies - 1, 3)
    defender_dice = min(defender_armies, 2)

    attacker_rolls = roll_dice(attacker_dice)
    defender_rolls = roll_dice(defender_dice)

    print(f"{attacker} attacks {defender}!")
    print(f"Attacker rolls: {attacker_rolls}")
    print(f"Defender rolls: {defender_rolls}")

    # Compare dice rolls
    for attack, defend in zip(attacker_rolls, defender_rolls):
        if attack > defend:
            defender_armies -= 1  # Defender loses an army
        else:
            attacker_armies -= 1  # Attacker loses an army

    # Update the map data
    map_data[attacker]["armies"] = attacker_armies
    map_data[defender]["armies"] = defender_armies

    print(f"Result: {attacker} now has {attacker_armies} armies, {defender} has {defender_armies}")

    # If defender is wiped out, attacker captures the territory
    if defender_armies == 0:
        print(f"{attacker} has captured {defender}!")
        map_data[defender]["owner"] = map_data[attacker]["owner"]
        map_data[defender]["armies"] = attacker_armies - 1  # Move at least one army
        map_data[attacker]["armies"] = 1  # Leave one behind

