import random
from shared import Target, DiceRolls

def grenade_damage():
    return 1

def ranged_damage():
    return 2

def axe_damage():
    return 3

scenarios = 50000
target_died = 0
models_left = {
}

for _ in range(scenarios):
    target = Target(3, 5, 2, 4, 5)

    target.attack(2 * 3, 2, 4, 1, ranged_damage)

    amGrenades = 3 * int(target.models / 5) + DiceRolls(3).total()
    target.attack(amGrenades, 2, 4, 1, grenade_damage)

    target.attack(3 * 4, 2, 9, 1, axe_damage, 5, sustained=True)
    #target.attack(3 * 5, 2, 7, 2, ranged_damage, 5, sustained=True)

    if target.models <= 0:
        target_died += 1

    models_left[target.models] = models_left.get(target.models, 0) + 1

print(f'{target_died} units died ({round(target_died / scenarios * 100, 1)}%)')

print('unit alive with:')
for x, y in sorted(models_left.items()):
    if x != 0:
        print(f'{x} {round(y / scenarios * 100, 1)}%')
