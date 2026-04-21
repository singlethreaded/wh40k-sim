# Open Issues

## Keywords that make range assumptions (match librarian)
- **Rapid Fire N**, **Melta N** assume half range (bonus always applied).
- **Lance** assumes the attacker charged.

## Deferred modeling
- **Multi-phase turn model** (shooting then charge then fight) — current design
  resolves all weapons in one pass, sharing HP pool.
- **Per-model variance in unit_size when W > 1** — currently all models have
  identical W; fine for homogeneous units, doesn't model e.g. sergeant with
  extra wounds.

## Later
- Confidence intervals on the returned averages
- Parallel iteration (multiprocessing) for large n_iter

