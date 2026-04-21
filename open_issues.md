# Open Issues

## Deferred weapon keywords
- **Indirect Fire** — mostly no damage-calc effect; skip until needed.

## Keywords that make range assumptions (match librarian)
- **Rapid Fire N**, **Melta N** assume half range (bonus always applied).
- **Heavy** assumes the attacker was stationary.
- **Lance** assumes the attacker charged.

## Deferred modeling
- **fnp_mortal / fnp_psychic** — exposed on `SimDefender` but not currently
  consulted (v1 treats all damage as "normal"; no mortal/psychic source flag yet).
- **Multi-phase turn model** (shooting then charge then fight) — current design
  resolves all weapons in one pass, sharing HP pool.
- **Per-model variance in unit_size when W > 1** — currently all models have
  identical W; fine for homogeneous units, doesn't model e.g. sergeant with
  extra wounds.

## Later
- Confidence intervals on the returned averages
- Parallel iteration (multiprocessing) for large n_iter

## From PR #1 review (2026-04-20)
- **Wire up `fnp_mortal` / `fnp_psychic`** — fields exist on `SimDefender` but
  `simulate()` only reads `fnp`. Librarian's `_fnp_through` picks the best of
  baseline / mortal / psychic per damage source, which needs a "mortal source"
  or "psychic source" flag on `SimWeapon` (or on individual damage paths, e.g.
  Devastating mortals). Either plumb it through or drop the unused fields.
  *Source: PR #1.*
- **Packaging** — no `pyproject.toml` / `setup.py` / README. Librarian will need
  these when it adds this repo as a submodule and imports `wh40k_sim`. A minimal
  `pyproject.toml` with `tool.setuptools.packages = ["wh40k_sim"]` plus a short
  README is enough. *Source: PR #1.*
- **`_find_kw` case-insensitivity divergence** — sim is case-insensitive on
  keyword matching; librarian's `_find_kw` (core.py:72) is case-sensitive.
  Low-risk but a semantic divergence. Pick one and align both. *Source: PR #1.*
- **`SimResult.n_iter` is a superset field** — `UnitDamageResult` doesn't carry
  it. Update `profiles.py` / `__init__.py` docstrings to say "superset of
  UnitDamageResult" rather than "matches". *Source: PR #1.*
