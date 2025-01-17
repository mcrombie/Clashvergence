from src.rules import game_rules
from src.map_data import greater_virginia_territory_map, simplified_territory_map
import random
import networkx as nx
import matplotlib.pyplot as plt



#Tinkering with basic territory map models
# map_data = {
#     "Territory_1": {"owner": None, "armies": 0, "neighbors": ["Territory_2"]},
#     "Territory_2": {"owner": None, "armies": 0, "neighbors": ["Territory_1", "Territory_3"]},
#     "Territory_3": {"owner": None, "armies": 0, "neighbors": ["Territory_2"]},
# }

def print_map():
    for territory, details in greater_virginia_territory_map.items():
        print(f"{territory}: Owner={details['owner']}, Armies={details['armies']}, Neighbors={details['neighbors']}")

# if __name__ == "__main__":
#     print_map()

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

# Test victory check
# print(check_victory(50, 100, 0))  # Output: Victory by eliminating all opponents

def create_graph(map_data):
    G = nx.Graph()

    # Add nodes and edges
    for territory, details in map_data.items():
        G.add_node(territory)
        for neighbor in details["neighbors"]:
            G.add_edge(territory, neighbor)

    return G


active_map = simplified_territory_map

# Create the graph
graph = create_graph(active_map)

def plot_graph(G):
 # Determine node colors based on ownership
    def get_node_colors():
        color_map = []
        for territory, details in active_map.items():
            if details["owner"] == "Player 1":
                color_map.append("blue")
            elif details["owner"] == "Player 2":
                color_map.append("red")
            else:
                color_map.append("gray")  # Neutral territory
        return color_map

    # Determine node sizes based on armies
    def get_node_sizes():
        return [
            active_map[node]["armies"] * 100 + 500 if node in active_map else 500
            for node in graph.nodes
        ]


    # Add edge labels (optional)
    edge_labels = {edge: "1" for edge in G.edges}  # Example: Terrain difficulty of 1

    # Generate positions for nodes
    pos = nx.spring_layout(G)  # Layout algorithm for graph visualization

    # Draw the graph
    nx.draw(
        G,
        pos,
        with_labels=True,
        node_color=get_node_colors(),
        node_size=get_node_sizes(),
        font_size=10,
        font_color="black",
        edge_color="black",
    )
    
    # Draw edge labels (optional)
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

    # Display the graph
    plt.show()

# Plot the graph
plot_graph(graph)

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

# Example usage:
result = resolve_combat(attacker_armies=5, defender_armies=3)
print(result)  # {'attacker_remaining': 4, 'defender_remaining': 0}