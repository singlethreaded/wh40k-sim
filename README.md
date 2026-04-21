# wh40k-sim

Monte Carlo damage simulator for Warhammer 40,000 10th edition. Built as a
validation backstop for analytic damage calculators — the output shape matches
the `UnitDamageResult` used by the [librarian](https://github.com/singlethreaded/librarian)
project's Markov-chain calc, so the two can be run side-by-side on the same
inputs.

## Install

```bash
pip install -e .          # editable install from a clone
pip install -e ".[dev]"   # + pytest for the test suite
```

As a git submodule (typical consumer setup):

```bash
git submodule add https://github.com/singlethreaded/wh40k-sim.git vendor/wh40k-sim
pip install -e vendor/wh40k-sim
```

Requires Python ≥ 3.10. No runtime dependencies.

## Usage

```python
from wh40k_sim import SimAttacker, SimDefender, SimWeapon, simulate

bolt_rifle = SimWeapon(
    name="Bolt Rifle",
    attacks="2", skill=3, strength=4, ap=-1, damage="1",
    count=5,
)
intercessors = SimAttacker(name="Intercessors", model_count=5, weapons=[bolt_rifle])
guardsmen    = SimDefender(name="Guardsmen", toughness=3, save=5, wounds=1,
                           unit_size=10, keywords=["Infantry"])

result = simulate(intercessors, guardsmen, n_iter=20000, seed=42)
print(result.avg_damage, result.p_kills)
```

See `examples/` for more scenarios.

## Keyword support

`SimWeapon.keywords` accepts the same strings librarian emits. Implemented:
Sustained Hits N (including `D3`/`D6`), Lethal Hits, Devastating Wounds,
Twin-linked, Anti-X N+, Torrent, Heavy, Lance, Rapid Fire N, Blast, Melta N,
Ignores Cover.

**Range assumptions** (match librarian): Rapid Fire and Melta assume half
range, Heavy assumes stationary, Lance assumes charging. See `open_issues.md`
for the deferred list.

## Conventions

- AP stored as a **negative int** (AP-1 → `ap=-1`), matching librarian.
- Save threshold floors at 2+ after cover (10e core rules).
- Damage floors at 1 after `damage_reduction`.
- FNP is rolled per point of damage independently.

## Testing

```bash
pytest
```

40 cases covering the dice-expression parser, happy-path analytic comparisons,
each keyword in isolation, edge cases (auto-fail saves, invuln-vs-cover,
spill-loss on multi-wound models), and the `_WeaponPlan` builder.

## Output shape

`SimResult` fields mirror librarian's `UnitDamageResult`:

| Field                    | Meaning                                             |
|--------------------------|-----------------------------------------------------|
| `avg_damage`             | Effective damage (HP-pool capped, respects spill-loss) |
| `avg_damage_uncapped`    | Raw damage applied pre-cap (post-FNP)               |
| `avg_kills`              | Expected models killed (fractional)                 |
| `p_wipe`                 | P(entire unit killed)                               |
| `p_kills[k]`             | P(exactly k models killed), k=0..unit_size          |
| `avg_damage_per_model`   | `avg_damage / unit_size`                            |
| `n_iter`                 | Trials run (wh40k-sim extension, not on UnitDamageResult) |
