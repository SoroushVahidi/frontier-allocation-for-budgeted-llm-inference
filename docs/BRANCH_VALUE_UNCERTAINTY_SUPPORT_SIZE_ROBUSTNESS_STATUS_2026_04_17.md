# Branch-value uncertainty support-size robustness status (2026-04-17)

## Goal
Diagnose whether the high-defer behavior seen on the rebuilt canonical replay is primarily:
1) a small-support artifact, or
2) a structural weakness of the current derived compare/defer rule.

This pass keeps the same method family and strict validation harness, with no redesign.

## Fixed evaluation harness (unchanged)
- Script: `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
- Regimes: `all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer`
- Seeds: `11,29,47`
- Feature set: `v3`

## Rebuild sizes and roots used

### Anchor (reused canonical rebuild)
- Support size (state summaries per regime): **36**
- Root: `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root`
- Strict run: `branch_value_uncertainty_strict_validation_support36_anchor_20260417`

### Matched larger-support rebuild
- Support size: **72**
- Root: `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/canonical_targets_root_support72`
- Strict run: `branch_value_uncertainty_strict_validation_support72_20260417`

### Larger-support rebuild
- Support size: **108**
- Root: `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/canonical_targets_root_support108`
- Strict run: `branch_value_uncertainty_strict_validation_support108_20260417`

## Key robustness results (full_method)

| Support | Accepted acc | Coverage | Defer rate | Near-tie accepted acc | Adjacent-rank accepted acc | Pairwise baseline acc | Penalized proxy acc | Delta vs pairwise |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 36 | 0.9333 | 0.2698 | 0.7302 | 0.0000 | 0.8889 | 0.7937 | 0.7667 | +0.1397 |
| 72 | 0.9524 | 0.5333 | 0.4667 | 0.0000 | 0.9167 | 0.8119 | 0.9506 | +0.1405 |
| 108 | 0.9333 | 0.5201 | 0.4799 | 0.1111 | 0.9048 | 0.8801 | 0.9815 | +0.0532 |

Observations:
- Increasing support from 36 to 72 substantially reduces defer rate (0.73 -> 0.47) and improves coverage.
- At 108 support, defer remains high (~0.48), not close to low-defer behavior.
- Near-tie accepted accuracy remains weak and unstable (0.00 -> 0.00 -> 0.11).
- Full-method accepted accuracy advantage over pairwise survives at all sizes, but margin shrinks at 108 (+0.053).

## Budget-conditioned behavior (full_method)
Pooled across regime/seed rows from strict outputs:

- Support 36:
  - Budget 3: coverage 0.333, accepted acc 1.000
  - Budget 4: coverage 0.429, accepted acc 1.000
  - Budget 5: coverage 0.231, accepted acc 0.667
- Support 72:
  - Budget 2: coverage 0.714, accepted acc 1.000
  - Budget 3: coverage 0.333, accepted acc 1.000
  - Budget 4: coverage 0.571, accepted acc 1.000
  - Budget 5: coverage 0.435, accepted acc 0.900
- Support 108:
  - Budget 2: coverage 0.700, accepted acc 1.000
  - Budget 3: coverage 0.500, accepted acc 1.000
  - Budget 4: coverage 0.467, accepted acc 0.857
  - Budget 5: coverage 0.375, accepted acc 0.889

Conservative read: accepted accuracy is strong where the method acts, but coverage remains modest especially at higher budgets.

## Regime-conditioned behavior (full_method)
With this strict harness/config, aggregate full-method metrics are effectively identical across the three requested regimes for each support size. This is recorded in machine-readable outputs and should be interpreted as a current harness/result characteristic rather than a claim that regimes are intrinsically equivalent.

## Direct answers to robustness question
1. **Does high defer persist with larger support?**
   - **Partly yes.** It drops strongly from 36 to 72 support, but remains high (~0.47-0.48) at 72/108.
2. **Does near-tie accepted accuracy improve?**
   - **Weakly and unstably.** It stays at 0.0 through support 72 and reaches only 0.111 at 108.
3. **Does accepted-accuracy edge over pairwise survive?**
   - **Yes, but less strongly at larger support.** Delta remains positive, shrinking from ~+0.14 to +0.053.
4. **Is current line mainly conservative selector, small-support artifact, or unstable?**
   - **Promising but still over-deferring** (best fit): not purely small-support artifact, not totally unstable, but near-tie quality is still fragile.

## Status classification
**promising but still over-deferring**

## Next exact recommended Codex task
Run a **strict no-redesign calibration diagnosis pass** on the same support-72 and support-108 roots to localize defer inflation sources:
- keep model family fixed,
- keep features fixed (`v3`),
- extract per-threshold acceptance profiles and near-tie acceptance/error tradeoff using existing strict outputs,
- produce a threshold-stability and tie-slice error decomposition report only (no new method logic).

## Repository artifacts written for this pass
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/support_size_rebuild_configs_and_sources.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/strict_validation_summaries_by_root.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/aggregate_support_size_comparison_summary.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_support_robustness_20260417/commands_assumptions_and_caveats.md`
