from src.rules import game_rules
from src.map_data import greater_virginia_territory_map, simplified_territory_map
import networkx as nx
import matplotlib.pyplot as plt
from src.utils import resolve_combat

from mpl_toolkits.basemap import Basemap


positions = {
    "Northern Virginia": (1, 5),
    "Shenandoah Valley": (2, 4),
    "Central Virginia": (3, 3),
    # Add more...
}

def create_graph(map_data):
    G = nx.Graph()
    for territory, details in map_data.items():
        G.add_node(territory, coords=details["coords"])
        for neighbor in details["neighbors"]:
            G.add_edge(territory, neighbor)
    return G

graph = create_graph(simplified_territory_map)

def setup_basemap():
    # Define map boundaries (approximate for Greater Virginia)
    m = Basemap(
        projection="merc",  # Mercator projection
        llcrnrlat=35,       # Lower-left corner latitude
        urcrnrlat=40,       # Upper-right corner latitude
        llcrnrlon=-85,      # Lower-left corner longitude
        urcrnrlon=-75,      # Upper-right corner longitude
        resolution="i",     # Intermediate resolution
    )
    
    # Add map features
    m.drawcoastlines()
    m.drawcountries()
    m.drawstates()
    m.fillcontinents(color="lightgray", lake_color="aqua")
    m.drawmapboundary(fill_color="aqua")
    
    return m

def plot_graph_on_map(G, map_data):
    # Set up the Basemap
    m = setup_basemap()

    # Extract node positions from territory data
    node_positions = {node: m(*map_data[node]["coords"]) for node in G.nodes}

    # Define node colors and sizes
    node_colors = [
        "blue" if map_data[node]["owner"] == "Player 1" else
        "red" if map_data[node]["owner"] == "Player 2" else
        "gray"
        for node in G.nodes
    ]
    node_sizes = [map_data[node]["armies"] * 100 + 500 for node in G.nodes]

    # Draw nodes and edges on the map
    nx.draw(
        G,
        pos=node_positions,
        with_labels=False,
        node_color=node_colors,
        node_size=node_sizes,
        edge_color="black",
        connectionstyle="arc3,rad=0.2",  # Curved edges for clarity
    )

    # Add labels for nodes (territory names and armies)
    labels = {
        node: f"{node}\n({map_data[node]['armies']} armies)"
        for node in G.nodes
    }
    nx.draw_networkx_labels(G, pos=node_positions, labels=labels, font_size=10)

    # Show the map
    plt.show()

# Example usage
plot_graph_on_map(graph, simplified_territory_map)


# # Convert latitude/longitude to x/y and draw graph nodes/edges
# for node, (lon, lat) in positions.items():
#     x, y = m(lon, lat)
#     plt.plot(x, y, 'o', markersize=10, label=node)

# plt.legend()
# plt.show()


# def create_graph(map_data):
#     G = nx.Graph()

#     # Add nodes and edges
#     for territory, details in map_data.items():
#         G.add_node(territory)
#         for neighbor in details["neighbors"]:
#             G.add_edge(territory, neighbor)

#     return G


# active_map = simplified_territory_map

# # Create the graph
# graph = create_graph(active_map)

# def plot_graph(G):
#  # Determine node colors based on ownership
#     def get_node_colors():
#         color_map = []
#         for territory, details in active_map.items():
#             if details["owner"] == "Player 1":
#                 color_map.append("blue")
#             elif details["owner"] == "Player 2":
#                 color_map.append("red")
#             else:
#                 color_map.append("gray")  # Neutral territory
#         return color_map

#     # Determine node sizes based on armies
#     def get_node_sizes():
#         return [
#             active_map[node]["armies"] * 100 + 500 if node in active_map else 500
#             for node in graph.nodes
#         ]
    
#     # Add edge labels (optional)
#     edge_labels = {edge: "1" for edge in G.edges}  # Example: Terrain difficulty of 1

#     # Generate positions for nodes
#     pos = nx.spring_layout(G)  # Layout algorithm for graph visualization

#     # Draw the graph
#     nx.draw(
#         G,
#         pos,
#         with_labels=True,
#         node_color=get_node_colors(),
#         node_size=get_node_sizes(),
#         font_size=10,
#         font_color="black",
#         edge_color="black",
#     )
    
#     # Draw edge labels (optional)
#     nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

#     # Display the graph
#     plt.show()

# # Plot the graph
# plot_graph(graph)


