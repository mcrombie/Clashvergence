from src.world import create_initial_world
from src.actions import expand, invest


world = create_initial_world()

print(world.regions["A"].resources)  # 2
print(world.regions["A"].owner)  # 2
print(world.regions["B"].owner)  # 2

invest("Faction1", "A", world)
expand("Faction1", "B", world)
print(world.regions["B"].owner)  # 2

print(world.regions["A"].resources)  # 3

for _ in range(10):
    invest("Faction1", "A", world)

print(world.regions["A"].resources)  # should stop at 5