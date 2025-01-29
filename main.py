from src.rules import game_rules
from src.map_data import greater_virginia_territory_map, simplified_territory_map
import networkx as nx
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap

import geopandas as gpd
import matplotlib.pyplot as plt

# # Load shapefile for U.S. states
shapefile_path = r"C:\Users\Michael\Downloads\shapefiles\tl_2024_us_state.shp"
print(shapefile_path)
us_states = gpd.read_file(shapefile_path)

# Inspect the data
print(us_states.head())

# List of states in Greater Virginia
greater_virginia_states = [
    "Virginia", "West Virginia", "Maryland", "Delaware",
    "Ohio", "Kentucky", "Tennessee", "North Carolina",
    "Pennsylvania", "New Jersey"
]

# Filter the states
greater_virginia = us_states[us_states["NAME"].isin(greater_virginia_states)]

import matplotlib.pyplot as plt

# Plot the filtered states
fig, ax = plt.subplots(figsize=(10, 10))
greater_virginia.plot(ax=ax, color="lightgray", edgecolor="black")
plt.title("Greater Virginia Region")
plt.show()