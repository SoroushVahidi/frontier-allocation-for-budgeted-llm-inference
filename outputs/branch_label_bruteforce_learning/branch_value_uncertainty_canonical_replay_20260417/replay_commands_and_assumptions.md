# Canonical replay command log / assumptions / caveats (2026-04-17)

## Script replayed unchanged
- `scripts/run_branch_value_uncertainty_strict_validation_pass.py`

## Commands run

```bash
python -m py_compile scripts/run_branch_value_uncertainty_strict_validation_pass.py

python scripts/run_branch_value_uncertainty_strict_validation_pass.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_compare_bundle_exact_augmented_regimes_20260417 \
  --run-id branch_value_uncertainty_strict_validation_canonical_replay_near_tie_bundle_20260417 \
  --regimes all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer \
  --seeds 11,29,47 \
  --feature-set v3

python scripts/run_branch_value_uncertainty_strict_validation_pass.py \
  --targets-root outputs/branch_label_bruteforce_targets/incomparability_exact_augmented_regimes_20260417 \
  --run-id branch_value_uncertainty_strict_validation_canonical_replay_incomparability_20260417 \
  --regimes all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer \
  --seeds 11,29,47 \
  --feature-set v3

python scripts/run_branch_value_uncertainty_strict_validation_pass.py \
  --targets-root outputs/branch_label_bruteforce_targets/validation_penalized_regimes_nt_l0.20_t0.02_eu0.10_cap1.50_20260417 \
  --run-id branch_value_uncertainty_strict_validation_canonical_replay_penalized_20260417 \
  --regimes all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer \
  --seeds 11,29,47 \
  --feature-set v3
```

## Assumptions
- The canonical replay should use the strict validation script unchanged and keep seeds/settings matched to prior bounded strict pass.
- The minimum comparable regime set remains `all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer`.
- Canonical root candidates were selected from repository-documented branch-allocation target roots that reflect hard-case exact-augmented and penalized-marginal work.

## Caveats / blocking issue
- In this checkout, all three canonical root candidates were missing the required `regime_*` directories.
- The script therefore produced machine-readable outputs with `missing_regimes` and zero-row aggregates, which are diagnostic only.
- No honest metric upgrade/downgrade claim is possible from this replay attempt without mounting canonical artifacts.
