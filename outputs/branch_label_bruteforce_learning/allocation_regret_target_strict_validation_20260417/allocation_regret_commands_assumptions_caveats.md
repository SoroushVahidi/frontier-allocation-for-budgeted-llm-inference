# Allocation regret target experiment: commands, assumptions, caveats

## Commands run

```bash
python -m py_compile scripts/build_bruteforce_target_regimes.py scripts/build_exact_augmented_target_regimes.py scripts/run_branch_value_uncertainty_strict_validation_pass.py experiments/bruteforce_branch_allocator.py
python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx --output-dir outputs/branch_label_bruteforce_targets --run-id allocation_regret_target_20260417 --pair-strategies all_pairs,allocation_regret_target,allocation_regret_target_no_outside --near-tie-margin 0.03 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.15 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx
python scripts/run_branch_value_uncertainty_strict_validation_pass.py --targets-root outputs/branch_label_bruteforce_targets/allocation_regret_target_20260417 --run-id allocation_regret_target_strict_validation_20260417 --output-dir outputs/branch_label_bruteforce_learning --regimes all_pairs,allocation_regret_target,allocation_regret_target_no_outside --seeds 11,29,47 --feature-set v3
```

## Assumptions

- Canonical base labels are taken from `outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx`.
- Matched strict-validation settings are reused from the existing harness defaults unless explicitly overridden.
- Primary comparison metric uses strict-validation `full_method` accepted-pair accuracy with coverage/defer and hard-slice diagnostics.

## Caveats

- This bounded pass reuses available local artifacts only; no new brute-force corpus regeneration was performed.
- The strict-validation harness computes aggregate values across all `(regime, seed)` rows, so experiment-specific per-regime deltas are reported in added summary JSONs in this run directory.
- Near-tie accepted accuracy is sparse under the strict defer-heavy operating point selected by validation (coverage-constrained threshold selection), so near-tie comparisons should be interpreted conservatively.
