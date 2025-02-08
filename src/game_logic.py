import random

def roll_dice(num_dice):
    """Rolls a given number of 6-sided dice and returns a sorted list."""
    return sorted([random.randint(1, 6) for _ in range(num_dice)], reverse=True)


def battle(attacker, defender, map_data):
    """
    Simulates a battle between two territories.
    - `attacker`: Attacking territory name (string)
    - `defender`: Defending territory name (string)
    - `map_data`: Dictionary containing territory information
    """
    
    # Get army counts
    attacker_armies = map_data[attacker]["armies"]
    defender_armies = map_data[defender]["armies"]

    if attacker_armies < 2:
        print("Not enough armies to attack!")
        return

    # Determine dice rolls
    attacker_dice = min(attacker_armies - 1, 3)
    defender_dice = min(defender_armies, 2)

    attacker_rolls = roll_dice(attacker_dice)
    defender_rolls = roll_dice(defender_dice)

    print(f"\n{attacker} attacks {defender}!")
    print(f"Attacker rolls: {attacker_rolls}")
    print(f"Defender rolls: {defender_rolls}")

    # Resolve battle
    for attack, defend in zip(attacker_rolls, defender_rolls):
        if attack > defend:
            defender_armies -= 1  # Defender loses an army
        else:
            attacker_armies -= 1  # Attacker loses an army

    # Update army counts in map data
    map_data[attacker]["armies"] = attacker_armies
    map_data[defender]["armies"] = defender_armies

    print(f"Result: {attacker} now has {attacker_armies} armies, {defender} has {defender_armies}")

    # Check if defender is defeated
    if defender_armies == 0:
        print(f"{attacker} has captured {defender}!")
        map_data[defender]["owner"] = map_data[attacker]["owner"]
        map_data[defender]["armies"] = attacker_armies - 1  # Move armies to new territory
        map_data[attacker]["armies"] = 1  # Leave one army behind


def take_turn(player, map_data):
    """
    Handles a single turn for a player.
    - `player`: The player taking the turn (e.g., "Player 1").
    - `map_data`: The game state dictionary.
    """
    print(f"\n{player}'s turn!")

    # 1. Reinforcement Phase (Basic: Add 3 armies to a random territory)
    owned_territories = [t for t, v in map_data.items() if v["owner"] == player]
    if owned_territories:
        chosen_territory = random.choice(owned_territories)
        map_data[chosen_territory]["armies"] += 3
        print(f"{player} reinforced {chosen_territory} with 3 armies.")

    # 2. Attack Phase (Basic: Pick a random valid attack)
    possible_attacks = [
        (t, n)
        for t in owned_territories
        for n in map_data[t]["neighbors"]
        if map_data[n]["owner"] != player and map_data[t]["armies"] > 1
    ]
    if possible_attacks:
        attack_from, attack_to = random.choice(possible_attacks)
        battle(attack_from, attack_to, map_data)

    # 3. Fortify Phase (Basic: Move 2 armies from one owned territory to another)
    if len(owned_territories) > 1:
        from_territory, to_territory = random.sample(owned_territories, 2)
        if map_data[from_territory]["armies"] > 1:
            map_data[from_territory]["armies"] -= 2
            map_data[to_territory]["armies"] += 2
            print(f"{player} fortified {to_territory} from {from_territory}.")


