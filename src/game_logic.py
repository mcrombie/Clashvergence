import random
from src.rules import continent_bonuses


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
    print(f"\n{player}'s turn!")

    reinforce(player, map_data)

    if is_human:
        # Player manually chooses attack (unchanged)
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
        # AI uses new attack strategy
        attacker, defender = choose_attack(player, map_data)
        if attacker and defender:
            battle(attacker, defender, map_data)
        fortify(player, map_data)


def reinforce(player, map_data):
    """Reinforce based on controlled territories and continent bonuses."""
    owned_territories = [t for t, v in map_data.items() if v["owner"] == player]

    if not owned_territories:
        return

    # Base reinforcement: 1 army per 3 territories (minimum 3)
    reinforcement_count = max(3, len(owned_territories) // 3)

    # Check for continent bonuses
    player_territories = {t: v for t, v in map_data.items() if v["owner"] == player}
    controlled_continents = []

    for continent, bonus in continent_bonuses.items():
        continent_territories = [t for t in player_territories if continent in t]
        if len(continent_territories) == sum(1 for t in map_data if continent in t):
            controlled_continents.append((continent, bonus))

    # Add continent bonuses
    for continent, bonus in controlled_continents:
        reinforcement_count += bonus
        print(f"{player} received a {bonus} army bonus for controlling {continent}.")

    # Add reinforcements to the weakest territory
    weakest_territory = min(owned_territories, key=lambda t: map_data[t]["armies"])
    map_data[weakest_territory]["armies"] += reinforcement_count

    print(f"{player} reinforced {weakest_territory} with {reinforcement_count} armies.")


def choose_attack(player, map_data):
    """AI prioritizes attacking weak enemy territories with a high chance of success."""
    possible_attacks = [
        (t, n)
        for t in map_data
        if map_data[t]["owner"] == player and map_data[t]["armies"] > 1
        for n in map_data[t]["neighbors"]
        if map_data[n]["owner"] != player
    ]

    if not possible_attacks:
        return None, None

    # Prioritize targets based on army strength: AI should attack weaker targets first
    best_attack = min(
        possible_attacks, 
        key=lambda x: map_data[x[1]]["armies"] - map_data[x[0]]["armies"]
    )

    # Only attack if AI has more armies than the target (adjust this threshold if needed)
    if map_data[best_attack[0]]["armies"] > map_data[best_attack[1]]["armies"]:
        return best_attack
    
    return None, None  # Skip attack if no good targets



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
