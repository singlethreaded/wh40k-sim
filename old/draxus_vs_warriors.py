import random
from shared import Target, DiceRolls

def grenade_damage():
    return 1

def ranged_damage():
    return 2

def axe_damage():
    return 3

scenarios = 50#000
target_died = 0
models_left = {
}

for _ in range(scenarios):
    target = Target(1, 4, 4, 4, 20)

    # Allarus
    #grenades = DiceRolls(5).total() + int(target.models / 5) * 5
    #target.attack(grenades, 2, 4, 1, grenade_damage, twin_linked=True)
    #target.attack(10, 2, 4, 1, ranged_damage, twin_linked=True)

    # Draxus
    target.attack(8, 2, 4, 0, ranged_damage, wounds_crit_on=4, devastating=True, twin_linked=True)
    target.attack(12, 2, 6, 0, ranged_damage, sustained=True, sustained_bonus=2, twin_linked=True)

    # Guard
    target.attack(20, 2, 4, 1, ranged_damage, twin_linked=True)

    # Reanimation
    reanimations = DiceRolls(2, 3).total() if target.models > 0 else 0
    target.models = min(20, target.models + reanimations)
    print(f'reanimated {reanimations} up to {target.models}')

    if target.models <= 0:
        target_died += 1

    models_left[target.models] = models_left.get(target.models, 0) + 1

print(f'{target_died} units died ({round(target_died / scenarios * 100, 1)}%)')

print('unit alive with:')
for x, y in sorted(models_left.items()):
    if x != 0:
        print(f'{x} {round(y / scenarios * 100, 1)}%')
