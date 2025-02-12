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


def take_turn(player, map_data, is_human=False):
    """Handles a turn for either a human player or AI."""
    print(f"\n{player}'s turn!")

    if is_human:
        # Human-controlled reinforcement
        print("Your territories:", [t for t, v in map_data.items() if v["owner"] == player])
        chosen_territory = input("Choose a territory to reinforce: ")
        if chosen_territory in map_data and map_data[chosen_territory]["owner"] == player:
            map_data[chosen_territory]["armies"] += 3
            print(f"You reinforced {chosen_territory} with 3 armies.")
        else:
            print("Invalid choice. Skipping reinforcement.")

        # Human-controlled attack
        attack_choice = input("Do you want to attack? (yes/no): ").lower()
        if attack_choice == "yes":
            attacker = input("Choose your attacking territory: ")
            defender = input("Choose the enemy territory to attack: ")
            if (
                attacker in map_data and defender in map_data and
                map_data[attacker]["owner"] == player and
                map_data[defender]["owner"] != player and
                map_data[attacker]["armies"] > 1
            ):
                battle(attacker, defender, map_data)
            else:
                print("Invalid attack. Skipping.")

        # Human-controlled fortify
        fortify_choice = input("Do you want to fortify? (yes/no): ").lower()
        if fortify_choice == "yes":
            from_territory = input("Choose the territory to move armies from: ")
            to_territory = input("Choose the territory to move armies to: ")
            if (
                from_territory in map_data and to_territory in map_data and
                map_data[from_territory]["owner"] == player and
                map_data[to_territory]["owner"] == player and
                map_data[from_territory]["armies"] > 1
            ):
                map_data[from_territory]["armies"] -= 2
                map_data[to_territory]["armies"] += 2
                print(f"You fortified {to_territory} from {from_territory}.")
            else:
                print("Invalid fortification. Skipping.")

    else:
        # AI plays automatically
        reinforce(player, map_data)
        attacker, defender = choose_attack(player, map_data)
        if attacker and defender:
            battle(attacker, defender, map_data)
        fortify(player, map_data)



def reinforce(player, map_data):
    """AI selects the weakest owned territory and reinforces it."""
    owned_territories = [t for t, v in map_data.items() if v["owner"] == player]
    
    if not owned_territories:
        return
    
    # Find the territory with the fewest armies
    weakest_territory = min(owned_territories, key=lambda t: map_data[t]["armies"])
    
    # Add 3 armies
    map_data[weakest_territory]["armies"] += 3
    print(f"{player} reinforced {weakest_territory} with 3 armies.")


def choose_attack(player, map_data):
    """AI selects the best attack: prioritize weak enemy territories."""
    possible_attacks = [
        (t, n)
        for t in map_data
        if map_data[t]["owner"] == player and map_data[t]["armies"] > 1
        for n in map_data[t]["neighbors"]
        if map_data[n]["owner"] != player
    ]
    
    if not possible_attacks:
        return None, None
    
    # Prioritize attacking the enemy territory with the least armies
    best_attack = min(possible_attacks, key=lambda x: map_data[x[1]]["armies"])
    return best_attack


def fortify(player, map_data):
    """AI moves armies from safe territories to frontlines."""
    owned_territories = [t for t, v in map_data.items() if v["owner"] == player]
    
    if len(owned_territories) < 2:
        return  # No fortification needed if only one territory

    # Identify frontline territories (those bordering enemy-controlled regions)
    frontline_territories = [
        t for t in owned_territories 
        if any(map_data[n]["owner"] != player for n in map_data[t]["neighbors"])
    ]

    # Identify safe territories (those surrounded by friendly territories)
    safe_territories = [
        t for t in owned_territories 
        if all(map_data[n]["owner"] == player for n in map_data[t]["neighbors"])
    ]

    if not frontline_territories or not safe_territories:
        return  # No valid fortifications

    # Pick a safe territory with extra armies
    from_territory = max(safe_territories, key=lambda t: map_data[t]["armies"], default=None)
    
    # Pick a frontline territory to reinforce
    to_territory = min(frontline_territories, key=lambda t: map_data[t]["armies"], default=None)

    if from_territory and to_territory and map_data[from_territory]["armies"] > 1:
        # Move 2 armies to the frontline
        map_data[from_territory]["armies"] -= 2
        map_data[to_territory]["armies"] += 2
        print(f"{player} fortified {to_territory} from {from_territory}.")

def check_victory(map_data):
    """Checks if a single player controls all territories."""
    owners = set(v["owner"] for v in map_data.values())
    
    if len(owners) == 1:  # Only one player owns all territories
        winner = owners.pop()
        print(f"\n🏆 {winner} has won the game! 🏆")
        return True
    
    return False
