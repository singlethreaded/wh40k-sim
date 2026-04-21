import random

class DiceRolls:
    def __init__(self, amount: int, max_roll=6):
        self.rolls = {
            1: 0,
            2: 0,
            3: 0,
            4: 0,
            5: 0,
            6: 0
        }

        for _ in range(amount):
            roll = random.randint(1,max_roll)
            self.rolls[roll] = self.rolls[roll] + 1

    def less_than(self, roll: int):
        total = 0
        for x in range(1, roll):
            total = total + self.rolls[x]
        return total
    
    def plus(self, roll: int):
        total = 0
        for x in range(roll, 7):
            total = total + self.rolls[x]
        return total
    
    def range(self, start: int, stop: int):
        total = 0
        for x in range(start, stop):
            total = total + self.rolls[x]
        return total

    def total(self):
        total = 0
        for x in self.rolls.keys():
            total += x * self.rolls[x]
        return total

    def print(self):
        for x in range(1, 7):
            print(f'{x}: {self.rolls[x]}')

class Target:
    def __init__(self, wounds: int, toughness: int, save: int, invul: int, models = 1):
        self.initial_wounds = wounds
        self.wounds = wounds
        self.toughness = toughness
        self.save = save
        self.invul = invul
        self.models = models

    def wounds_on(self, strength: int):
        if self.toughness * 2 <= strength:
            return 2
        
        if self.toughness < strength:
            return 3
        
        if self.toughness == strength:
            return 4
        
        if self.toughness < 2 * strength:
            return 5
        
        if self.toughness >= 2 * strength:
            return 6
    
    def attack(self, amount: int, skill: int, strength: int, ap: int, dmg, hits_crit_on = 6, lethal = False, sustained = False, sustained_bonus = 1, twin_linked = False, wound_bonus = 0, wounds_crit_on = 6, devastating = False) -> int:
        hits = 0
        wounds = 0

        hit_rolls = DiceRolls(amount)
        hits = hit_rolls.range(skill, hits_crit_on)

        if lethal:
            wounds = hit_rolls.plus(hits_crit_on)
        else:
            hits = hits + hit_rolls.plus(hits_crit_on)
            if sustained:
                hits += hit_rolls.plus(hits_crit_on) * sustained_bonus

        wound_rolls = DiceRolls(hits)
        wounds_on = min(self.wounds_on(strength) - wound_bonus, wounds_crit_on)
        devs = 0 if devastating == False else wound_rolls.plus(wounds_crit_on)
        if wounds_on < 2:
            wounds_on = 2
        wounds = wounds + wound_rolls.plus(wounds_on) - devs

        if twin_linked:
            wound_rerolls = hits - wound_rolls.plus(self.wounds_on(strength))
            rerolls = DiceRolls(wound_rerolls)
            wounds += rerolls.plus(self.wounds_on(strength))

        saves_on = self.save + ap
        if saves_on < self.invul:
            saves_on = self.invul

        save_rolls = DiceRolls(wounds)
        saves = save_rolls.plus(saves_on)

        total_dmg = 0

        for _ in range(wounds - saves + devs):
            damage = dmg()
            total_dmg += damage
            self.wounds -= damage
            if self.wounds <= 0:
                self.models = self.models - 1 if self.models > 0 else 0
                if self.models > 0:
                    self.wounds = self.initial_wounds

        return total_dmg

