from src.rules import game_rules
from src.map_data import greater_virginia_territory_map, simplified_territory_map
import networkx as nx
import matplotlib.pyplot as plt
from src.utils import resolve_combat

from mpl_toolkits.basemap import Basemap

import geopandas as gpd
import matplotlib.pyplot as plt

# Load shapefile for U.S. states
# us_states = gpd.read_file("path/to/shapefile.shp")
# TO DO: Figure out how these shapefiles to make accurate terriroties based on county and state maps.

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

plot_graph_on_map(graph, simplified_territory_map)