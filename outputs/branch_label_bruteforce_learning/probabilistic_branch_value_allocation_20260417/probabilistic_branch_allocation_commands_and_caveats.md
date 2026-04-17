# Probabilistic branch-allocation bounded pass: commands, assumptions, caveats

## Commands executed

```bash
python -m py_compile scripts/run_probabilistic_branch_value_allocation_experiment.py scripts/run_branch_value_uncertainty_strict_validation_pass.py

python scripts/run_probabilistic_branch_value_allocation_experiment.py \
  --targets-root outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root \
  --run-id probabilistic_branch_value_allocation_20260417 \
  --feature-set v3 \
  --seeds 11,29,47 \
  --regimes all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer \
  --coverage-floor 0.55 \
  --temperature 0.75 \
  --temperature-grid 0.50,0.75,1.00
```

## Assumptions

- Canonical branch-value path reused as-is for targets, branch value, and risk heads.
- Canonical defer threshold tuning remains anchored to baseline mode only (validation split).
- Deterministic and probabilistic forced-choice modes are evaluated on identical test rows and identical seeds.
- Probabilistic decisions are reproducible via deterministic pseudo-random stream from `(seed, row_index)`.

## Caveats

- This bounded pass uses the currently available canonical target root under the learning outputs tree.
- The run is intentionally go/no-go scoped; no broad controller redesign or target-regime rewrite.
- Probabilistic modes here are forced-choice (coverage 1.0), so defer behavior changes by construction.
