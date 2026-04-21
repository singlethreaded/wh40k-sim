"""
Tests for wh40k_sim.simulate. Most cases compare a Monte Carlo average against
an analytic expectation to within a fixed tolerance. n_iter is large enough
that a healthy tolerance (±0.10) won't be flaky, but still catches logic bugs.
"""
import random
import pytest

from wh40k_sim import SimAttacker, SimDefender, SimWeapon, simulate
from wh40k_sim.simulate import roll_expr, _build_plan


N = 20_000            # trial count; ~3σ tolerance of 0.1 on a unit-variance per-trial mean
TOL = 0.10
SEED = 12345


# --- factories -------------------------------------------------------------

def mk_weapon(**kw) -> SimWeapon:
    defaults = dict(name="W", attacks="1", skill=3, strength=4, ap=0,
                    damage="1", count=1, keywords=[], weapon_type="ranged")
    defaults.update(kw)
    return SimWeapon(**defaults)


def mk_defender(**kw) -> SimDefender:
    defaults = dict(name="D", toughness=4, save=4, wounds=1, unit_size=10)
    defaults.update(kw)
    return SimDefender(**defaults)


def run(weapon: SimWeapon, defender: SimDefender, count_attackers: int = 1):
    attacker = SimAttacker(name="A", model_count=count_attackers, weapons=[weapon])
    return simulate(attacker, defender, n_iter=N, seed=SEED)


# --- dice parser -----------------------------------------------------------

class TestRollExpr:
    def test_fixed_value(self):
        rng = random.Random(0)
        assert all(roll_expr("3", rng) == 3 for _ in range(20))

    def test_d6_range(self):
        rng = random.Random(0)
        rolls = [roll_expr("D6", rng) for _ in range(1000)]
        assert min(rolls) >= 1 and max(rolls) <= 6
        assert 3.2 < sum(rolls) / len(rolls) < 3.8      # avg ~3.5

    def test_multi_dice_with_mod(self):
        rng = random.Random(0)
        rolls = [roll_expr("2D3+1", rng) for _ in range(1000)]
        assert min(rolls) >= 3 and max(rolls) <= 7
        assert 4.7 < sum(rolls) / len(rolls) < 5.3      # avg 2*2 + 1 = 5

    def test_unparseable_returns_one(self):
        assert roll_expr("garbage", random.Random(0)) == 1


# --- happy path ------------------------------------------------------------

def test_happy_path_matches_analytic():
    """10 attacks, BS3+ (4/6), S4 vs T3 (3+ wound, 4/6), Sv5+ AP-1 → 6+ (fail 5/6), D1."""
    w = mk_weapon(attacks="2", skill=3, strength=4, ap=-1, damage="1", count=5)
    d = mk_defender(toughness=3, save=5, unit_size=10)
    expected = 10 * (4/6) * (4/6) * (5/6)    # ≈ 3.70
    r = run(w, d)
    assert abs(r.avg_damage - expected) < TOL


def test_reproducible_with_seed():
    w = mk_weapon(attacks="D6", damage="D3", count=3)
    d = mk_defender()
    assert simulate(SimAttacker("A", 1, [w]), d, n_iter=500, seed=7).avg_damage \
        == simulate(SimAttacker("A", 1, [w]), d, n_iter=500, seed=7).avg_damage


# --- per-keyword expectations ---------------------------------------------

def test_sustained_hits_adds_extra_hits_on_crit():
    """Sustained Hits 1: avg hits gains 1/6 per attack."""
    baseline = run(mk_weapon(attacks="6", skill=3, strength=4, ap=0), mk_defender())
    with_sus = run(mk_weapon(attacks="6", skill=3, strength=4, ap=0, keywords=["Sustained Hits 1"]),
                   mk_defender())
    # Baseline hits avg = 6 * 4/6 = 4; sustained adds 6 * 1/6 = 1 → 5 hits → damage scales ×5/4.
    assert with_sus.avg_damage > baseline.avg_damage * 1.15     # at least ~25% uplift, leave tolerance


def test_lethal_hits_bypass_wound_roll():
    """S3 vs T8 (wound on 6+). Lethal turns 1/6 of hits into auto-wounds regardless of wound roll."""
    w = mk_weapon(attacks="6", skill=3, strength=3, ap=0, damage="1", keywords=["Lethal Hits"])
    d = mk_defender(toughness=8, save=7, unit_size=20)  # save 7+ so every unsaved wound dealt
    # hits = 6 * 3/6 (non-crit successes on 3-5) + 6 * 1/6 (crits → auto-wound). Wound 6+ on non-crit hits.
    # Non-crit hits: 6 * 3/6 = 3; wounds from them: 3 * 1/6 = 0.5. Lethal wounds: 6 * 1/6 = 1. Total wounds: 1.5.
    r = run(w, d)
    assert abs(r.avg_damage - 1.5) < TOL


def test_devastating_wounds_bypass_saves():
    """Devastating: critical wounds become mortals, skipping saves. With Sv2+ the difference is dramatic."""
    plain = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0), mk_defender(save=2))
    devs  = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0, keywords=["Devastating Wounds"]),
                mk_defender(save=2))
    assert devs.avg_damage > plain.avg_damage * 1.5


def test_twin_linked_rerolls_failed_wounds():
    """Twin-linked roughly doubles the failed-wound conversion."""
    plain = run(mk_weapon(attacks="12", skill=3, strength=3, ap=0), mk_defender(toughness=4, save=7))
    twin  = run(mk_weapon(attacks="12", skill=3, strength=3, ap=0, keywords=["Twin-linked"]),
                mk_defender(toughness=4, save=7))
    # Wound 5+: success 2/6; with reroll 2/6 + 4/6 * 2/6 = 14/36 ≈ 0.389 vs 0.333. ~17% uplift.
    assert twin.avg_damage > plain.avg_damage * 1.10


def test_anti_x_narrows_crit_threshold():
    """Anti-Infantry 4+ against Infantry: crit-wounds at 4+, combined with Devastating to make it observable."""
    w = mk_weapon(attacks="12", skill=3, strength=3, ap=0,
                  keywords=["Anti-Infantry 4+", "Devastating Wounds"])
    d = mk_defender(toughness=4, save=2, keywords=["Infantry"])
    # Without Anti-X: crit 6+ → 1/6. With: 4+ → 3/6 → many devastating mortals bypass Sv2+.
    r = run(w, d)
    # 12 * 4/6 hits = 8; crit-wound prob 3/6 → ~4 mortals. Plus normal wounds on 5+ (non-crit 2/6) * (1/6 fail save).
    # Rough floor check: mortals alone deliver ≥2 damage; total should beat 3.
    assert r.avg_damage > 3.0


def test_anti_x_no_match_means_default_crit():
    """Anti-Vehicle against Infantry: should behave like no anti-keyword."""
    plain = run(mk_weapon(attacks="12", skill=3, strength=3, ap=0, keywords=["Devastating Wounds"]),
                mk_defender(toughness=4, save=2, keywords=["Infantry"]))
    antix = run(mk_weapon(attacks="12", skill=3, strength=3, ap=0,
                          keywords=["Anti-Vehicle 4+", "Devastating Wounds"]),
                mk_defender(toughness=4, save=2, keywords=["Infantry"]))
    assert abs(plain.avg_damage - antix.avg_damage) < TOL


def test_torrent_auto_hits():
    w = mk_weapon(attacks="6", skill=6, strength=4, ap=0, keywords=["Torrent"])   # BS6+ but Torrent bypasses
    d = mk_defender(toughness=3, save=7)
    # 6 hits (auto) * wound 3+ (4/6) = 4 wounds, saves auto-fail → 4 damage
    r = run(w, d)
    assert abs(r.avg_damage - 4.0) < TOL


def test_heavy_adds_hit_bonus_ranged():
    """Heavy: +1 to hit if stationary. BS4+ with Heavy behaves as 3+."""
    baseline = run(mk_weapon(attacks="6", skill=4, strength=4, ap=0), mk_defender(toughness=3, save=7))
    heavy    = run(mk_weapon(attacks="6", skill=4, strength=4, ap=0, keywords=["Heavy"]),
                   mk_defender(toughness=3, save=7))
    # 3+ vs 4+: 4/6 vs 3/6, damage scales ~1.33x
    assert heavy.avg_damage > baseline.avg_damage * 1.15


def test_heavy_ignored_on_melee_weapons():
    base_kw = mk_weapon(attacks="6", skill=4, strength=4, ap=0, weapon_type="melee")
    with_kw = mk_weapon(attacks="6", skill=4, strength=4, ap=0, weapon_type="melee", keywords=["Heavy"])
    d = mk_defender(toughness=3, save=7)
    assert abs(run(base_kw, d).avg_damage - run(with_kw, d).avg_damage) < TOL


def test_lance_adds_wound_bonus_melee():
    baseline = run(mk_weapon(attacks="6", skill=3, strength=3, ap=0, weapon_type="melee"),
                   mk_defender(toughness=4, save=7))
    lance    = run(mk_weapon(attacks="6", skill=3, strength=3, ap=0, weapon_type="melee",
                             keywords=["Lance"]),
                   mk_defender(toughness=4, save=7))
    # Wound 5+ → 4+ with Lance: 2/6 → 3/6.
    assert lance.avg_damage > baseline.avg_damage * 1.25


def test_rapid_fire_adds_flat_attacks():
    """Rapid Fire 2: +2 attacks per weapon. 2 attacks → 4 attacks, damage ~doubles."""
    base = run(mk_weapon(attacks="2", skill=3, strength=4, ap=0), mk_defender(toughness=3, save=7))
    rf   = run(mk_weapon(attacks="2", skill=3, strength=4, ap=0, keywords=["Rapid Fire 2"]),
               mk_defender(toughness=3, save=7))
    assert rf.avg_damage > base.avg_damage * 1.7


def test_blast_scales_with_unit_size():
    """Blast against 15-model unit adds +3 attacks (15 // 5)."""
    base = run(mk_weapon(attacks="3", skill=3, strength=4, ap=0),
               mk_defender(toughness=3, save=7, unit_size=15))
    blast = run(mk_weapon(attacks="3", skill=3, strength=4, ap=0, keywords=["Blast"]),
                mk_defender(toughness=3, save=7, unit_size=15))
    assert blast.avg_damage > base.avg_damage * 1.8


def test_melta_adds_damage_bonus():
    base = run(mk_weapon(attacks="6", skill=3, strength=8, ap=-3, damage="2"),
               mk_defender(toughness=4, save=3, wounds=10, unit_size=1))
    melta = run(mk_weapon(attacks="6", skill=3, strength=8, ap=-3, damage="2",
                          keywords=["Melta 3"]),
                mk_defender(toughness=4, save=3, wounds=10, unit_size=1))
    # Use uncapped to see the raw damage bonus — avg_damage hits the 10-wound HP cap.
    assert melta.avg_damage_uncapped > base.avg_damage_uncapped * 2.0    # 2 → 5 dmg per wound


def test_cover_improves_save():
    no_cover = run(mk_weapon(attacks="12", skill=3, strength=4, ap=-1, damage="1"),
                   mk_defender(toughness=3, save=5))
    cover    = run(mk_weapon(attacks="12", skill=3, strength=4, ap=-1, damage="1"),
                   mk_defender(toughness=3, save=5, save_bonus_ranged=1))
    # 6+ save (no cover) → 5+ save (with cover): fail 5/6 → 4/6, damage ~0.8x
    assert cover.avg_damage < no_cover.avg_damage * 0.85


def test_ignores_cover_negates_save_bonus():
    defender = mk_defender(toughness=3, save=5, save_bonus_ranged=1)
    plain = run(mk_weapon(attacks="12", skill=3, strength=4, ap=-1, damage="1"), defender)
    ic    = run(mk_weapon(attacks="12", skill=3, strength=4, ap=-1, damage="1",
                          keywords=["Ignores Cover"]), defender)
    assert ic.avg_damage > plain.avg_damage * 1.15


# --- edge cases ------------------------------------------------------------

def test_ap_makes_save_impossible():
    """Sv3+ vs AP-5 → save would be 8+, clipped to 7+ which auto-fails."""
    r = run(mk_weapon(attacks="6", skill=3, strength=4, ap=-5, damage="1"),
            mk_defender(toughness=3, save=3, invuln_ranged=0))
    # 6 * 4/6 hit * 4/6 wound = 2.67, all go through
    assert abs(r.avg_damage - 2.67) < TOL


def test_invuln_preferred_over_armour():
    """Sv2+ AP-4 → 6+ armour vs 4++ invuln; invuln wins."""
    r = run(mk_weapon(attacks="12", skill=3, strength=4, ap=-4, damage="1"),
            mk_defender(toughness=3, save=2, invuln_ranged=4))
    # 12 * 4/6 * 4/6 = 5.33 wounds; save 4+ fails 3/6 → 2.67
    assert abs(r.avg_damage - 2.67) < TOL


def test_invuln_never_gets_cover():
    """Cover applies to armour only; a target with cover + invuln4 still fails invuln at 3/6."""
    no_inv = mk_defender(toughness=3, save=3, save_bonus_ranged=1)       # 3+ → 2+ with cover
    has_inv = mk_defender(toughness=3, save=3, save_bonus_ranged=1, invuln_ranged=4)
    w = mk_weapon(attacks="12", skill=3, strength=4, ap=-2, damage="1")  # vs 2+ armour → 4+
    r1 = run(w, no_inv)
    r2 = run(w, has_inv)
    # Both should land on 4+ save (cover makes armour 4+ equivalent to invuln 4+). Equal.
    assert abs(r1.avg_damage - r2.avg_damage) < TOL


def test_damage_reduction_floors_at_one():
    """D1 damage - 1 reduction → still 1 per wound (can't go below 1)."""
    r = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0, damage="1"),
            mk_defender(toughness=3, save=7, damage_reduction_ranged=5))
    # 12 * 4/6 * 4/6 = 5.33 damage at 1 each
    assert abs(r.avg_damage - 5.33) < TOL


def test_fnp_reduces_effective_damage():
    no_fnp  = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0),
                  mk_defender(toughness=3, save=7))
    fnp_5   = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0),
                  mk_defender(toughness=3, save=7, fnp=5))
    # FNP 5+ ignores 2/6 of damage → ~2/3 remains
    assert abs(fnp_5.avg_damage / no_fnp.avg_damage - 2/3) < 0.05


def test_fnp_mortal_applies_only_to_devastating_mortals():
    """fnp_mortal shields Dev-Wounds mortals; normal unsaved wounds ignore it."""
    # Weapon without Devastating: fnp_mortal must have no effect.
    plain_w = mk_weapon(attacks="12", skill=3, strength=4, ap=0)
    base    = run(plain_w, mk_defender(toughness=3, save=7))
    plain_m = run(plain_w, mk_defender(toughness=3, save=7, fnp_mortal=5))
    assert abs(plain_m.avg_damage - base.avg_damage) < TOL

    # Weapon with Devastating: ~1/6 of wounds become mortals. fnp_mortal 5+ should
    # save ~2/6 of those. Baseline fnp=0 means normals take full damage.
    dev_w = mk_weapon(attacks="60", skill=3, strength=4, ap=0, keywords=["Devastating Wounds"])
    d = mk_defender(toughness=3, save=7, unit_size=100)
    no_fm   = run(dev_w, d)
    with_fm = run(dev_w, mk_defender(toughness=3, save=7, unit_size=100, fnp_mortal=5))
    # 60 hits → 60*4/6 = 40 wounds; 1/6 of those → 6.67 mortal, 33.33 normal.
    # fnp_mortal 5+ saves 2/6 of mortals: 6.67 * 2/6 ≈ 2.22 shielded.
    expected_drop = (40 * 1/6) * (2/6)
    assert abs((no_fm.avg_damage - with_fm.avg_damage) - expected_drop) < 0.8


def test_fnp_psychic_applies_only_when_weapon_is_psychic():
    """fnp_psychic triggers only for weapons with the 'Psychic' keyword."""
    d_psy = mk_defender(toughness=3, save=7, fnp_psychic=5)
    # Non-psychic weapon: fnp_psychic should not fire.
    non_psy = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0), d_psy)
    base    = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0),
                  mk_defender(toughness=3, save=7))
    assert abs(non_psy.avg_damage - base.avg_damage) < TOL
    # Psychic weapon: fnp_psychic 5+ ignores ~2/6 of damage.
    psy = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0, keywords=["Psychic"]), d_psy)
    assert abs(psy.avg_damage / base.avg_damage - 2/3) < 0.05


def test_fnp_best_of_baseline_and_mortal():
    """When baseline fnp and fnp_mortal both set, mortals use the lower (better) value."""
    # fnp=6 (saves 1/6) but fnp_mortal=4 (saves 3/6). Mortals should see 4+.
    dev_w = mk_weapon(attacks="60", skill=3, strength=4, ap=0, keywords=["Devastating Wounds"])
    d_both = mk_defender(toughness=3, save=7, unit_size=100, fnp=6, fnp_mortal=4)
    d_only = mk_defender(toughness=3, save=7, unit_size=100, fnp=6)
    r_both = run(dev_w, d_both)
    r_only = run(dev_w, d_only)
    # Mortal stream is ~6.67 damage; dropping its FNP from 6+ to 4+ saves an extra
    # 6.67 * (3/6 - 1/6) = 6.67 * 2/6 ≈ 2.22
    expected_drop = (40 * 1/6) * (2/6)
    assert abs((r_only.avg_damage - r_both.avg_damage) - expected_drop) < 0.8


def test_spill_loss_on_multiwound_overkill():
    """D6 damage into W1 models. Every unsaved wound still kills exactly one model."""
    r = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0, damage="D6"),
            mk_defender(toughness=3, save=7, unit_size=10))
    # 12 * 4/6 * 4/6 = 5.33 unsaved; each kills 1 model regardless of D6 roll.
    assert abs(r.avg_kills - 5.33) < TOL
    assert abs(r.avg_damage - 5.33) < TOL


def test_p_wipe_sane_when_outmatched():
    """Massive overkill: p_wipe ~1.0."""
    r = run(mk_weapon(attacks="20", skill=2, strength=10, ap=-4, damage="D6+3", count=5),
            mk_defender(toughness=3, save=5, unit_size=3))
    assert r.p_wipe > 0.99
    assert r.p_kills[3] > 0.99


def test_unit_size_1_single_model():
    r = run(mk_weapon(attacks="4", skill=3, strength=8, ap=-2, damage="3"),
            mk_defender(toughness=5, save=3, wounds=6, unit_size=1))
    # Check the output structure is coherent
    assert len(r.p_kills) == 2                            # 0..unit_size
    assert abs(sum(r.p_kills) - 1.0) < 1e-6
    assert r.p_wipe == r.p_kills[1]


# --- plan builder ----------------------------------------------------------

class TestBuildPlan:
    def test_basic_thresholds(self):
        plan = _build_plan(
            mk_weapon(skill=3, strength=5, ap=-1),
            mk_defender(toughness=4, save=3),
        )
        assert plan.hit_threshold == 3
        assert plan.wound_threshold == 3                    # S5 vs T4
        assert plan.save_threshold == 4                     # 3+ with AP-1

    def test_invuln_beats_worse_armour(self):
        plan = _build_plan(
            mk_weapon(skill=3, strength=4, ap=-3),
            mk_defender(toughness=4, save=3, invuln_ranged=5),
        )
        # armour becomes 6+, invuln is 5+ (better)
        assert plan.save_threshold == 5

    def test_ignores_cover_strips_save_bonus(self):
        plan_plain = _build_plan(
            mk_weapon(ap=-1),
            mk_defender(save=5, save_bonus_ranged=1),
        )
        plan_ic = _build_plan(
            mk_weapon(ap=-1, keywords=["Ignores Cover"]),
            mk_defender(save=5, save_bonus_ranged=1),
        )
        assert plan_plain.save_threshold == 5               # 5+ with cover vs AP-1
        assert plan_ic.save_threshold == 6                  # cover cancelled

    def test_melee_ignores_heavy_lance_applies(self):
        melee_plan = _build_plan(
            mk_weapon(weapon_type="melee", skill=3, strength=4, keywords=["Lance", "Heavy"]),
            mk_defender(toughness=4),
        )
        # Lance gives +1 to wound (4+ → 3+). Heavy ignored on melee.
        assert melee_plan.wound_threshold == 3

    def test_anti_x_plural_match(self):
        plan = _build_plan(
            mk_weapon(keywords=["Anti-Infantry 4+"]),
            mk_defender(keywords=["Infantry"]),
        )
        assert plan.crit_wound_threshold == 4


# --- regression fixes (PR #1 review feedback) ------------------------------

def test_save_floors_at_two_plus_in_cover():
    """Sv2+ + cover must not become 1+ (10e floors save at 2+). Regression for PR #1."""
    d = mk_defender(toughness=4, save=2, unit_size=10, save_bonus_ranged=1)
    # S4 AP-0 vs T4 (wound 4+, 3/6), hit 3+ (4/6), Sv2+cover → save floored at 2+ (fails 1/6)
    r = run(mk_weapon(attacks="12", skill=3, strength=4, ap=0, damage="1"), d)
    # 12 * 4/6 * 3/6 * 1/6 = 0.667 damage. Buggy (1+ save) would give ~0.
    assert abs(r.avg_damage - 0.667) < TOL
    assert r.avg_damage > 0.3     # sanity floor — save is not 1+


def test_twin_linked_skipped_when_reroll_wounds_set():
    """If the caller provides reroll_wounds='all', twin-linked must not double up.
    Result should equal plain reroll_wounds='all' (no twin bonus on top)."""
    d = mk_defender(toughness=4, save=7, unit_size=20)
    reroll_only = run(mk_weapon(attacks="12", skill=3, strength=3, ap=0, reroll_wounds="all"), d)
    reroll_twin = run(mk_weapon(attacks="12", skill=3, strength=3, ap=0, reroll_wounds="all",
                                keywords=["Twin-linked"]), d)
    assert abs(reroll_only.avg_damage - reroll_twin.avg_damage) < TOL


def test_sustained_hits_d3_samples_dice():
    """Sustained Hits D3 averages +2 hits per crit, not +3 (was deterministic before)."""
    # 60 attacks. Hits per attack = P(non-crit hit)*1 + P(crit)*(1 + E[D3])
    #   non-crit-hit prob = 3/6 (rolls 3,4,5), crit prob = 1/6 (roll 6), miss = 2/6.
    #   = (3/6)*1 + (1/6)*(1+2) = 1.0 hit/attack → 60 hits.
    # Wounds S4 vs T3 (3+, 4/6): 40. Sv7+: all go through → avg_damage ≈ 40.
    # Buggy version (deterministic +3 instead of D3 sample): 1.167 hit/attack → 70 hits → 46.67 dmg.
    w = mk_weapon(attacks="60", skill=3, strength=4, ap=0, damage="1", keywords=["Sustained Hits D3"])
    d = mk_defender(toughness=3, save=7, unit_size=100)
    r = run(w, d)
    assert abs(r.avg_damage - 40.0) < 1.5           # D3 adds trial-to-trial variance
    assert r.avg_damage < 44.0                       # clearly below the buggy +3 expectation


def test_rapid_fire_and_blast_stack():
    """Both keywords present → base_attacks + RF_n + unit_size//5, all times count."""
    # A=2, count=3, RF2 → +2*3=6; Blast vs 15-unit → +3*3=9. Total = 6 + 6 + 9 = 21 attacks.
    w = mk_weapon(attacks="2", skill=3, strength=4, ap=0, damage="1", count=3,
                  keywords=["Rapid Fire 2", "Blast"])
    d = mk_defender(toughness=3, save=7, unit_size=15)
    r = run(w, d)
    # 21 * 4/6 * 4/6 = 9.33
    assert abs(r.avg_damage - 9.33) < TOL


def test_lethal_plus_twin_linked():
    """Twin-linked still helps non-crit hits that go to the wound roll; lethal consumes only crits."""
    d = mk_defender(toughness=8, save=7, unit_size=30)   # wound 6+
    plain = run(mk_weapon(attacks="30", skill=3, strength=3, ap=0, keywords=["Lethal Hits"]), d)
    twin  = run(mk_weapon(attacks="30", skill=3, strength=3, ap=0,
                          keywords=["Lethal Hits", "Twin-linked"]), d)
    # Lethal converts 1/6 hits to auto-wounds. Twin-linked adds wound rerolls on the remaining
    # 3/6 (non-crit) hits. Expect a measurable uplift.
    assert twin.avg_damage > plain.avg_damage * 1.10


def test_unit_size_zero_raises():
    """Guard against pathological input — librarian asserts unit_size >= 1; we match."""
    with pytest.raises(AssertionError):
        simulate(SimAttacker("A", 1, [mk_weapon()]),
                 mk_defender(unit_size=0), n_iter=10, seed=0)
