# Upstream target-semantics bounded experiment commands / assumptions / caveats

## Commands run

```bash
python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root/regime_all_pairs_approx \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id target_semantics_upstream_20260417 \
  --pair-strategies opportunity_intensity_weighted,opportunity_intensity_weighted_no_outside_norm \
  --near-tie-margin 0.03 \
  --tie-use-near-tie-flag \
  --opportunity-intensity-tau 0.01 \
  --opportunity-intensity-w-min 0.50 \
  --opportunity-intensity-w-max 20.0 \
  --opportunity-intensity-final-min 0.70 \
  --opportunity-intensity-final-max 1.60

python scripts/run_branch_value_uncertainty_strict_validation_pass.py \
  --targets-root outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417 \
  --run-id target_semantics_upstream_strict_validation_20260417 \
  --regimes all_pairs_approx,opportunity_intensity_weighted,opportunity_intensity_weighted_no_outside_norm \
  --seeds 11,29,47 \
  --feature-set v3

python scripts/summarize_upstream_target_semantics_experiment.py \
  --strict-results outputs/branch_label_bruteforce_learning/target_semantics_upstream_strict_validation_20260417/strict_validation_results.json \
  --targets-root outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417 \
  --baseline-regime all_pairs_approx \
  --output-dir outputs/branch_label_bruteforce_learning/target_semantics_upstream_strict_validation_20260417 \
  --run-id target_semantics_upstream_strict_validation_20260417
```

## Assumptions

- Reused canonical strict-validation harness and settings (feature set `v3`, seeds `11,29,47`) to keep comparison matched.
- Reused available canonical baseline regime directory `regime_all_pairs_approx` as the baseline path.
- No decision-rule modifications were introduced; only supervision weighting semantics were changed for the new regimes.

## Caveats

- In this bounded artifact set, `outside_option_value_estimate` is effectively zero/unset for pair rows, so the with/without-outside normalization regimes are numerically identical in this pass.
- Strict-validation `full_method` metrics are dominated by value/risk defer pipeline and did not move across regimes; pairwise-binary baseline metrics were also unchanged in aggregate.
- Dataset slice here is small (openai/gsm8k-only in this recovered canonical root), so this pass is diagnostic rather than broad final evidence.
