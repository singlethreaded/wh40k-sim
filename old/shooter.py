import random
from shared import DiceRolls, Target

def grav_tank_damage():
    return 2 + random.randint(1,6)

def salvo_damage():
    return 1 + random.randint(1,6)

def lance_damage():
    return 2

def captain_damage():
    return 3

def missile_dmg():
    return random.randint(1,6)

scenarios = 50000
target_died = 0
raider_shot = 0
bikes_shot = 0
bikes_charged = 0

tank_dmg = 0
raider_dmg = 0
bike_salvo_dmg = 0
bike_melee_dmg = 0

am_tanks = 1
am_bikes = 3

def run_scenario() -> Target:
    global tank_dmg, raider_shot, raider_dmg, bikes_shot, bike_salvo_dmg, bikes_charged, bike_melee_dmg

    target = Target(16, 12, 2, 6)
    tank_dmg += target.attack(4 * am_tanks, 2, 12, 3, grav_tank_damage, lethal=True, twin_linked=True)

    if target.models <= 0:
        return target

    raider_shot += 1
    raider_dmg += target.attack(4, 2, 12, 3, salvo_damage)
    raider_dmg += target.attack(1, 2, 14, 3, missile_dmg)

    if target.models <= 0:
        return target

    bikes_shot += 1
    bike_salvo_dmg += target.attack(am_bikes, 2, 10, 3, salvo_damage, twin_linked=True)
    # captain
    bike_salvo_dmg += target.attack(1, 2, 10, 3, salvo_damage, twin_linked=True)

    if target.models <= 0:
        return target

    bikes_charged += 1
    bike_melee_dmg += target.attack(am_bikes * 5, 2, 7, 2, lance_damage, hits_crit_on=5, sustained=True, wound_bonus = 1)
    bike_melee_dmg += target.attack(6, 2, 8, 2, captain_damage, hits_crit_on=5, sustained=True, wound_bonus = 1)

    return target

for _ in range(scenarios):
    target = run_scenario()
    if target.models <= 0:
        target_died += 1

print(f'{target_died} targets died ({round(target_died / scenarios * 100, 1)}%)')
print(f'raider shot: {raider_shot} ({round(raider_shot / scenarios * 100, 1)}%)')
print(f'bikes shot: {bikes_shot} ({round(bikes_shot / scenarios * 100, 1)}%)')
print(f'bikes charged: {bikes_charged} ({round(bikes_charged / scenarios * 100, 1)}%)')

print(f'Average tank damage: {round(tank_dmg / scenarios)}')
print(f'Raider damage: {round(raider_dmg / raider_shot)}')
print(f'Salvo damage: {round(bike_salvo_dmg / bikes_shot)}')
print(f'Melee damage: {round(bike_melee_dmg / bikes_charged)}')
