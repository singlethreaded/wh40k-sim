"""
wh40k_sim — Monte Carlo damage simulator for 40k 10e.

Intended consumer: librarian's Markov-chain unit-damage calculator, as a
validation backstop. Field names on SimDefender / SimResult mirror librarian's
UnitProfile / UnitDamageResult so extraction is a direct field copy.
"""
from .profiles import SimAttacker, SimDefender, SimWeapon, SimResult
from .simulate import simulate, roll_expr

__all__ = ["SimAttacker", "SimDefender", "SimWeapon", "SimResult", "simulate", "roll_expr"]
