# Branch-value uncertainty support-size robustness pass commands (2026-04-17)

## Scope
Canonical branch-allocation / frontier-allocation path only.
No method redesign, no feature redesign, no threshold-retuning outside unchanged strict validation harness behavior.

## Strict harness and fixed settings
- Script: `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
- Regimes: `all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer`
- Seeds: `11,29,47`
- Feature set: `v3`

## Anchor root reused
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root`

## Additional matched-size rebuilds executed

### Support-72 rebuild chain
```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --output-dir outputs/branch_label_bruteforce \
  --run-id canonical_rebuild_base_labels_20260417_support72 \
  --max-frontier-states 72 \
  --episodes-per-example 2 \
  --frontier-budget 8 \
  --min-remaining-budget 2 \
  --max-remaining-budget 5 \
  --init-branches 4 \
  --max-branches-per-state 5 \
  --seed 17 \
  --rollout-samples-per-candidate 24 \
  --max-allocation-samples 96

python scripts/mine_bruteforce_hard_regions.py \
  --labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417_support72 \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_hard_region_mining_20260417_support72 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.08 \
  --low-confidence-threshold 0.58 \
  --max-candidates 240

python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417_support72 \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/canonical_rebuild_hard_region_mining_20260417_support72/mined_hard_candidates.jsonl \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_exact_hard_region_expansion_20260417_support72 \
  --max-target-pairs 182
```

### Support-108 rebuild chain
```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --output-dir outputs/branch_label_bruteforce \
  --run-id canonical_rebuild_base_labels_20260417_support108 \
  --max-frontier-states 108 \
  --episodes-per-example 2 \
  --frontier-budget 8 \
  --min-remaining-budget 2 \
  --max-remaining-budget 5 \
  --init-branches 4 \
  --max-branches-per-state 5 \
  --seed 17 \
  --rollout-samples-per-candidate 24 \
  --max-allocation-samples 96

python scripts/mine_bruteforce_hard_regions.py \
  --labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417_support108 \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_hard_region_mining_20260417_support108 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.08 \
  --low-confidence-threshold 0.58 \
  --max-candidates 360

python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417_support108 \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/canonical_rebuild_hard_region_mining_20260417_support108/mined_hard_candidates.jsonl \
  --output-dir outputs/branch_label_bruteforce_targets \
  --run-id canonical_rebuild_exact_hard_region_expansion_20260417_support108 \
  --max-target-pairs 273
```

### Common regime-build and strict-validation commands (same method family)
```bash
python scripts/build_exact_augmented_target_regimes.py ...
python scripts/build_bruteforce_target_regimes.py ...
python scripts/run_branch_value_uncertainty_strict_validation_pass.py ...
```

Concrete strict-validation run ids:
- `branch_value_uncertainty_strict_validation_support36_anchor_20260417`
- `branch_value_uncertainty_strict_validation_support72_20260417`
- `branch_value_uncertainty_strict_validation_support108_20260417`

## Assembled target roots
- Anchor root (support 36 states):
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root`
- Support 72 root:
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/canonical_targets_root_support72`
- Support 108 root:
  - `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/canonical_targets_root_support108`

## Assumptions and caveats
- Strict harness internals remained unchanged.
- Support-size change was introduced only via upstream rebuild support (`--max-frontier-states`) plus proportionally larger hard-candidate/exact-pair caps.
- No new features were added and no compare/defer rule redesign was applied.
- Near-tie accepted accuracy remains low and should be treated as unstable at current sample support.
