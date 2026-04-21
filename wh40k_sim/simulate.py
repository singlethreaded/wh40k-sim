"""
Monte Carlo damage simulator for 40k 10e. Runs `n_iter` trials of a single
attacker firing all its weapons at a single defender unit and aggregates into
a `SimResult` shaped like librarian's `UnitDamageResult`.

Per-iteration model: resolve each weapon attacks → hit → wound → save →
damage → FNP → unit HP pool. Weapons share the HP pool so excess damage on the
currently-wounded model is lost (10e spill-loss). No turn-phase sequencing.

Keywords: Sustained Hits N, Lethal Hits, Devastating Wounds, Twin-linked,
Anti-X N+, Torrent, Heavy, Lance, Rapid Fire N, Blast, Melta N, Ignores Cover.
Rapid Fire / Melta assume half range, Heavy assumes stationary, Lance assumes
charging — matching librarian's calc/core.py.

AP is stored negative (librarian convention): AP-1 → `ap = -1`.
"""
import random
import re
from dataclasses import dataclass
from .profiles import SimAttacker, SimDefender, SimResult, SimWeapon


_DICE_RE = re.compile(r"^\s*(\d*)[dD](\d+)\s*([+-]\s*\d+)?\s*$")
_ANTI_RE = re.compile(r"^Anti-([A-Za-z]+)\s*(\d)\+?$")


def roll_expr(expr: str, rng: random.Random) -> int:
    """Roll a dice expression like '2', 'D6', '2D3+1'. Unparseable → 1."""
    s = expr.strip()
    if s.isdigit():
        return int(s)
    m = _DICE_RE.match(s)
    if not m:
        return 1
    n = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    mod = int(m.group(3).replace(" ", "")) if m.group(3) else 0
    return sum(rng.randint(1, sides) for _ in range(n)) + mod


def _wound_target(strength: int, toughness: int) -> int:
    if strength >= toughness * 2: return 2
    if strength > toughness:       return 3
    if strength == toughness:      return 4
    if strength * 2 <= toughness:  return 6
    return 5


def _find_kw(keywords: list[str], prefix: str) -> str | None:
    return next((k for k in keywords if k.lower().startswith(prefix.lower())), None)


def _parse_trailing_int(kw: str | None, default: int = 0) -> int:
    """Extract trailing integer from 'Sustained Hits 2' / 'Melta 3'. Bare keyword → default."""
    if kw is None:
        return default
    m = re.search(r"(\d+)", kw)
    return int(m.group(1)) if m else default


# --------------------------------------------------------------- plan build ---

@dataclass
class _WeaponPlan:
    """Per-weapon fixed data for a simulation run. Computed once in `simulate()`
    so the inner trial loop touches no regex or keyword lookups."""
    weapon: SimWeapon
    is_melee: bool
    # Keyword flags
    torrent: bool
    lethal: bool
    devastating: bool
    twin_linked: bool
    sustained_n: int               # 0 = not sustained
    rapid_fire_n: int              # 0 = not rapid fire (ranged only)
    melta_bonus: int               # 0 = no melta (ranged only)
    blast: bool                    # adds unit_size // 5 per weapon (ranged only)
    # Precomputed thresholds / modifiers
    hit_threshold: int             # 2..7; 7 means auto-fail
    wound_threshold: int           # 2..6
    crit_wound_threshold: int      # default 6; Anti-X narrows it
    save_threshold: int            # 2..7; 7 means auto-fail saves
    damage_reduction: int          # per-wound damage minus this, floored at 1


def _build_plan(weapon: SimWeapon, defender: SimDefender) -> _WeaponPlan:
    is_melee = weapon.weapon_type == "melee"
    kws = weapon.keywords

    heavy = _find_kw(kws, "Heavy") is not None
    lance = _find_kw(kws, "Lance") is not None
    hit_bonus = weapon.hit_bonus + (1 if heavy and not is_melee else 0)
    wound_bonus = weapon.wound_bonus + (1 if lance and is_melee else 0)

    hit_penalty   = defender.hit_penalty_melee   if is_melee else defender.hit_penalty_ranged
    wound_penalty = defender.wound_penalty_melee if is_melee else defender.wound_penalty_ranged

    # Hit threshold: BS/WS adjusted by bonuses and defender penalties. 7+ means no roll can succeed.
    hit_threshold = min(7, max(2, weapon.skill - hit_bonus + hit_penalty))
    wound_threshold = min(7, max(2, _wound_target(weapon.strength, defender.toughness) - wound_bonus + wound_penalty))

    # Save: AP + cover; Ignores Cover (ranged only) cancels the cover bonus; invuln never gets cover.
    save_bonus = defender.save_bonus_melee if is_melee else defender.save_bonus_ranged
    if not is_melee and _find_kw(kws, "Ignores Cover"):
        save_bonus = 0
    armour_thr = defender.save - weapon.ap - save_bonus
    invuln = defender.invuln_melee if is_melee else defender.invuln_ranged
    save_threshold = min(7, invuln if 0 < invuln < armour_thr else armour_thr)

    # Anti-X N+ narrows the wound-crit threshold when defender has keyword X.
    crit_wound_threshold = 6
    for kw in kws:
        m = _ANTI_RE.match(kw)
        if not m:
            continue
        target_kw = m.group(1).lower()
        defender_kws = {k.lower() for k in defender.keywords}
        if target_kw in defender_kws or target_kw.rstrip("s") in defender_kws:
            crit_wound_threshold = int(m.group(2))
            break

    return _WeaponPlan(
        weapon=weapon,
        is_melee=is_melee,
        torrent=_find_kw(kws, "Torrent") is not None,
        lethal=_find_kw(kws, "Lethal") is not None,
        devastating=_find_kw(kws, "Devastating") is not None,
        twin_linked=(_find_kw(kws, "Twin-linked") is not None
                     or _find_kw(kws, "Twin linked") is not None),
        sustained_n=_parse_trailing_int(_find_kw(kws, "Sustained"), default=1) if _find_kw(kws, "Sustained") else 0,
        rapid_fire_n=(_parse_trailing_int(_find_kw(kws, "Rapid Fire")) if not is_melee else 0),
        melta_bonus=(_parse_trailing_int(_find_kw(kws, "Melta"))       if not is_melee else 0),
        blast=(_find_kw(kws, "Blast") is not None and not is_melee),
        hit_threshold=hit_threshold,
        wound_threshold=wound_threshold,
        crit_wound_threshold=crit_wound_threshold,
        save_threshold=save_threshold,
        damage_reduction=(defender.damage_reduction_melee if is_melee
                          else defender.damage_reduction_ranged),
    )


# ------------------------------------------------------------ roll helpers ---

def _roll_d6_rerolled(threshold: int, rng: random.Random, mode: str) -> int:
    """Single d6 with a reroll mode ('' | '1' | 'all'). Returns final face value."""
    r = rng.randint(1, 6)
    if mode == "all" and r < threshold:
        r = rng.randint(1, 6)
    elif mode == "1" and r == 1:
        r = rng.randint(1, 6)
    return r


# ---------------------------------------------------------- trial pipeline ---

def _simulate_once(plans: list[_WeaponPlan], defender: SimDefender, rng: random.Random) -> tuple[int, int, int]:
    """One trial. Returns (effective_damage, uncapped_damage, kills)."""
    S, W = defender.unit_size, defender.wounds
    current_hp = [W] * S
    kills = 0
    uncapped_damage = 0

    for p in plans:
        w = p.weapon

        # Attacks: rolled per weapon instance, plus flat Rapid Fire / Blast bonuses.
        total_attacks = sum(roll_expr(w.attacks, rng) for _ in range(w.count))
        total_attacks += p.rapid_fire_n * w.count
        if p.blast:
            total_attacks += (defender.unit_size // 5) * w.count

        # --- Hit phase ---
        hits = 0
        lethal_auto_wounds = 0
        for _ in range(total_attacks):
            if p.torrent:
                # Autohit; roll only to detect crit-trigger (Sustained / Lethal / Devastating).
                is_crit = (rng.randint(1, 6) == 6)
            else:
                r = _roll_d6_rerolled(p.hit_threshold, rng, w.reroll_hits)
                is_crit = (r == 6)                                      # unmodified 6 always crits
                if not is_crit and r < p.hit_threshold:
                    continue                                            # miss
            if is_crit and p.lethal:
                lethal_auto_wounds += 1
            else:
                hits += 1
                if is_crit and p.sustained_n:
                    hits += p.sustained_n

        # --- Wound phase ---
        wounds = 0
        devastating_mortals = 0
        for _ in range(hits):
            r = _roll_d6_rerolled(p.wound_threshold, rng, w.reroll_wounds)
            is_crit = (r >= p.crit_wound_threshold)
            success = is_crit or r >= p.wound_threshold
            if p.twin_linked and not success:
                r = rng.randint(1, 6)
                is_crit = (r >= p.crit_wound_threshold)
                success = is_crit or r >= p.wound_threshold
            if not success:
                continue
            if is_crit and p.devastating:
                devastating_mortals += 1
            else:
                wounds += 1
        wounds += lethal_auto_wounds                                    # lethal skips the wound roll

        # --- Save phase (devastating mortals bypass saves) ---
        unsaved = 0
        if p.save_threshold >= 7:
            unsaved = wounds                                            # no save possible
        else:
            for _ in range(wounds):
                if rng.randint(1, 6) < p.save_threshold:
                    unsaved += 1

        # --- Damage + FNP + HP pool ---
        for _ in range(unsaved + devastating_mortals):
            raw = roll_expr(w.damage, rng) + p.melta_bonus
            eff = max(1, raw - p.damage_reduction)                      # 10e: damage floors at 1
            if defender.fnp > 0:
                # FNP applies per point of damage independently.
                eff = sum(1 for _ in range(eff) if rng.randint(1, 6) < defender.fnp)
            if eff <= 0:
                continue
            uncapped_damage += eff
            if kills >= S:
                continue                                                # spill-loss: HP pool already empty
            if current_hp[kills] <= eff:
                kills += 1                                              # overkill wasted
            else:
                current_hp[kills] -= eff

    effective = kills * W + (W - current_hp[kills]) if kills < S else S * W
    return effective, uncapped_damage, kills


# ----------------------------------------------------------------- public ---

def simulate(
    attacker: SimAttacker,
    defender: SimDefender,
    n_iter: int = 10000,
    seed: int | None = None,
) -> SimResult:
    """Monte Carlo estimate of damage output for `attacker` vs `defender`.
    Pass `seed` for reproducible runs."""
    rng = random.Random(seed)
    plans = [_build_plan(w, defender) for w in attacker.weapons]
    S = defender.unit_size

    kill_counts = [0] * (S + 1)
    sum_effective = 0
    sum_uncapped = 0

    for _ in range(n_iter):
        eff, uncap, kills = _simulate_once(plans, defender, rng)
        sum_effective += eff
        sum_uncapped += uncap
        kill_counts[min(kills, S)] += 1

    p_kills = [c / n_iter for c in kill_counts]
    avg_damage = sum_effective / n_iter

    return SimResult(
        avg_damage=round(avg_damage, 4),
        avg_damage_uncapped=round(sum_uncapped / n_iter, 4),
        avg_kills=round(sum(k * p for k, p in enumerate(p_kills)), 4),
        p_wipe=round(p_kills[S], 5),
        p_kills=[round(p, 5) for p in p_kills],
        avg_damage_per_model=round(avg_damage / S, 4),
        n_iter=n_iter,
    )
