# Canonical regime rebuild + strict replay commands (2026-04-17)

## Objective
Rebuild one usable canonical targets root containing:

- `regime_all_pairs_approx`
- `regime_promoted_exact_hard_region`
- `regime_penalized_marginal_defer`

then replay strict validation unchanged.

## Rebuild chain commands

```bash
# 1) Rebuild upstream base labels
python scripts/run_bruteforce_branch_label_generator.py \
  --output-dir outputs/branch_label_bruteforce \
  --run-id canonical_rebuild_base_labels_20260417 \
  --max-frontier-states 36 \
  --episodes-per-example 2 \
  --frontier-budget 8 \
  --min-remaining-budget 2 \
  --max-remaining-budget 5 \
  --init-branches 4 \
  --max-branches-per-state 5 \
  --seed 17 \
  --rollout-samples-per-candidate 24 \
  --max-allocation-samples 96

# 2) Mine hard pairs from rebuilt base labels
python scripts/mine_bruteforce_hard_regions.py \
  --labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417 \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_hard_region_mining_20260417 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.08 \
  --low-confidence-threshold 0.58 \
  --max-candidates 120

# 3) Re-label mined hard pairs with exact runner
python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417 \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/canonical_rebuild_hard_region_mining_20260417/mined_hard_candidates.jsonl \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_exact_hard_region_expansion_20260417 \
  --max-target-pairs 91

# 4) Build exact-augmented regime root (contains all_pairs_approx and promoted_exact_hard_region)
python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417 \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/canonical_rebuild_exact_hard_region_expansion_20260417 \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_exact_augmented_regimes_20260417 \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --tie-policy davidson_close_call

# 5) Build penalized regime root (contains penalized_marginal_defer)
python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417 \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_penalized_regimes_20260417 \
  --pair-strategies penalized_marginal_defer \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --tie-policy davidson_close_call \
  --penalized-lambda 0.10 \
  --penalized-delta-c-mode constant_one \
  --penalized-tau-base 0.02 \
  --penalized-tau-relative-scale 0.10 \
  --penalized-tau-uncertainty-scale 0.50 \
  --penalized-tau-budget-scale 0.05 \
  --penalized-tau-mode selective_ambiguity_gate_v1 \
  --penalized-tau-easy-uncertainty-multiplier 0.20 \
  --penalized-tau-easy-budget-multiplier 0.00 \
  --penalized-tau-gap-cap-multiplier 1.50

# 6) Strict replay unchanged on assembled canonical root
python scripts/run_branch_value_uncertainty_strict_validation_pass.py \
  --targets-root outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root \
  --run-id branch_value_uncertainty_strict_validation_canonical_rebuild_20260417 \
  --regimes all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer \
  --seeds 11,29,47 \
  --feature-set v3
```

## Assembled canonical root provenance

The assembled root uses:

- `regime_all_pairs_approx` from `canonical_rebuild_exact_augmented_regimes_20260417`
- `regime_promoted_exact_hard_region` from `canonical_rebuild_exact_augmented_regimes_20260417`
- `regime_penalized_marginal_defer` from `canonical_rebuild_penalized_regimes_20260417`

Manifest and checksums:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_manifest.json`

## Caveats

- This rebuild is provenance-preserving and script-faithful, but it reconstructs artifacts in this checkout rather than restoring prior archived output directories.
- No method redesign or threshold retuning was performed before replay.
