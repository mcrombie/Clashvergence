from src.models import Region, Faction, WorldState


def create_initial_world() -> WorldState:
    '''Seven Regions and three Factions, where each Faction starts bordering three unoccupied regions'''
    regions = {
        "A": Region("A", ["B", "F", "M"], "Faction1", 2),
        "B": Region("B", ["A", "C", "M"], None, 2),
        "C": Region("C", ["B", "D", "M"], "Faction2", 2),
        "D": Region("D", ["C", "E", "M"], None, 2),
        "E": Region("E", ["D", "F", "M"], "Faction3", 2),
        "F": Region("F", ["E", "A", "M"], None, 2),
        "M": Region("M", ["A", "B", "C", "D", "E", "F"], None, 3),
    }

    factions = {
        "Faction1": Faction("Faction1", "expansionist"),
        "Faction2": Faction("Faction2", "balanced"),
        "Faction3": Faction("Faction3", "economic"),
    }

    return WorldState(regions=regions, factions=factions)