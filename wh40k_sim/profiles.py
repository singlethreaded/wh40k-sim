"""
Input/output dataclasses for the simulator.

The field names on `SimDefender` and `SimResult` deliberately mirror
librarian's `UnitProfile` / `UnitDamageResult` so librarian can extract fields
directly into these dataclasses without a translation layer.

AP convention follows librarian: stored as a negative int (AP-1 is -1).
"""
from dataclasses import dataclass, field


@dataclass
class SimWeapon:
    name: str
    attacks: str            # "2", "D6", "2D3+1"
    skill: int              # BS/WS as int (3 for 3+)
    strength: int
    ap: int                 # negative: -1 means AP-1 (raises target's save threshold by 1)
    damage: str             # "1", "D3", "D6+1"
    count: int = 1          # number of weapons firing (already accounts for models carrying)
    keywords: list[str] = field(default_factory=list)
    weapon_type: str = "ranged"   # "ranged" | "melee"
    # Ability-granted offensive modifiers (attacker-side, applied per-weapon)
    hit_bonus: int = 0             # +N to hit roll (lowers threshold)
    wound_bonus: int = 0           # +N to wound roll (lowers threshold)
    reroll_hits: str = ""          # "" | "1" | "all"
    reroll_wounds: str = ""        # "" | "1" | "all"


@dataclass
class SimAttacker:
    name: str
    model_count: int
    weapons: list[SimWeapon] = field(default_factory=list)


@dataclass
class SimDefender:
    name: str
    toughness: int
    save: int                       # 3 means 3+
    wounds: int = 1                 # wounds per model
    unit_size: int = 1
    invuln_ranged: int = 0          # 0 = none
    invuln_melee: int = 0
    fnp: int = 0
    fnp_mortal: int = 0
    fnp_psychic: int = 0
    keywords: list[str] = field(default_factory=list)
    # Defensive modifiers (raise attacker's roll thresholds)
    hit_penalty_ranged: int = 0
    hit_penalty_melee: int = 0
    wound_penalty_ranged: int = 0
    wound_penalty_melee: int = 0
    damage_reduction_ranged: int = 0
    damage_reduction_melee: int = 0
    save_bonus_ranged: int = 0        # +N to save roll (e.g. cover = 1). Negated by Ignores Cover.
    save_bonus_melee: int = 0


@dataclass
class SimResult:
    """Superset of librarian.src.calc.unit_damage.UnitDamageResult: the same
    fields with identical semantics, plus `n_iter` for reporting the Monte
    Carlo trial count. `per_wound_through_dist` (Markov-internal) is omitted.

    `avg_damage` is capped by the defender's HP pool (spill-loss respected).
    `avg_damage_uncapped` ignores the cap — useful when comparing to a scalar
    pipeline.
    """
    avg_damage: float
    avg_damage_uncapped: float
    avg_kills: float
    p_wipe: float
    p_kills: list[float]
    avg_damage_per_model: float
    n_iter: int = 0
