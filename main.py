#Tinkering with basic territory map models
map_data = {
    "Territory_1": {"owner": None, "armies": 0, "neighbors": ["Territory_2"]},
    "Territory_2": {"owner": None, "armies": 0, "neighbors": ["Territory_1", "Territory_3"]},
    "Territory_3": {"owner": None, "armies": 0, "neighbors": ["Territory_2"]},
}

def print_map():
    for territory, details in map_data.items():
        print(f"{territory}: Owner={details['owner']}, Armies={details['armies']}, Neighbors={details['neighbors']}")

if __name__ == "__main__":
    print_map()