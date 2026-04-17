# Branch-value + uncertainty strict validation status (2026-04-18)

## Scope

This note records a stricter validation pass for:

- `scripts/run_branch_value_uncertainty_derived_defer_experiment.py`

using a dedicated validation harness:

- `scripts/run_branch_value_uncertainty_strict_validation_pass.py`

Goal: test whether branch-level value supervision + uncertainty-aware derived compare/defer decisions remain promising under stronger bounded regimes and hard slices, with ablations and baseline comparisons.

## Important repository-grounded caveat discovered

A true canonical replay on prior heavy target-regime directories was not possible in this checkout because those `regime_*` target roots are not present locally.

To avoid losing momentum while preserving auditability, this pass used a stronger bounded proxy target root with multiple regimes and hard-slice structure:

- `outputs/branch_label_bruteforce_targets/strict_validation_proxy_20260418/`

This limitation must be treated as a validation caveat, not ignored.

## Bug / misleading interpretation fixed in this pass

A bug was found and fixed in the validation baseline logic:

- The initial penalized-marginal proxy baseline accidentally used directional information from `ternary_defer_label`, which can leak target direction and inflate baseline accuracy.
- Fix: use `ternary_defer_label` only as defer/not-defer signal, and always use model-predicted value difference for directional prediction.

This fix is in:

- `scripts/run_branch_value_uncertainty_strict_validation_pass.py`

## Validation setup

### Regimes

- `all_pairs_approx`
- `promoted_exact_hard_region`
- `penalized_marginal_defer`

### Seeds and feature setting

- seeds: `11,29,47`
- feature set: `v3`

### Baselines compared

1. binary pairwise logistic baseline (same tables)
2. value-only forced comparator
3. penalized-marginal proxy baseline (fixed leakage issue)
4. strongest tie-aware/defer-aware reference from existing repo outputs (recorded as contextual reference, not row-matched)

## Required ablations (executed)

1. value only
2. value + raw uncertainty
3. value + learned residual-risk head
4. value + outside-option competitiveness
5. full method

## Main aggregate results (strict validation run)

From:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_summary.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_results.json`

Aggregate over 3 regimes × 3 seeds:

- **full method**: accepted accuracy `0.9646`, coverage `0.7580`, defer rate `0.2420`
- **binary pairwise baseline**: accepted accuracy `0.8908`, coverage `1.0000`
- **value-only forced**: accepted accuracy `0.8967`, coverage `1.0000`
- full vs pairwise accepted-accuracy delta: `+0.0738`
- full vs value-only accepted-accuracy delta: `+0.0679`

Hard slices (aggregate):

- full near-tie accepted accuracy: `0.6093`
- full adjacent-rank accepted accuracy: `0.9735`

Ablation highlights:

- value+raw uncertainty is the strongest non-full ablation (`0.9573` accepted acc, `0.7596` coverage)
- learned-risk-only underperforms raw-uncertainty-only on accepted accuracy (`0.9226` vs `0.9573`)
- outside-option-only variant helps less than uncertainty variants

## Failure-mode diagnosis

### 1) Are gains only from reduced coverage?
Partly selective, but not purely degenerate:
- full coverage (`0.7580`) is almost identical to value+raw uncertainty (`0.7596`), yet full accepted accuracy is higher (`0.9646` vs `0.9573`).

### 2) Does uncertainty head help?
Mixed:
- raw uncertainty contributes strongly,
- learned-risk-only variant underperforms raw-uncertainty-only,
- full method still beats raw-only, suggesting combination value but not clean learned-risk dominance.

### 3) Is outside-option doing most of the work?
No:
- outside-option-only variant (`0.9110`) is far below full (`0.9646`).

### 4) Hard-slice behavior
- adjacent-rank performance is strong.
- near-tie accepted accuracy is mixed and does not dominate raw-uncertainty-only.

### 5) Diffuse defer / confidence misuse
- deferred pairs have much smaller true value gaps than accepted pairs, and higher oracle-defer-proxy scores, indicating defer is not purely random/diffuse.

### 6) Stability
- accepted accuracy is stable-to-moderately-stable across seeds; coverage varies more by regime/seed.

## Honest status classification

**Classification: mixed bounded line.**

Why not stronger:
- strict pass shows consistent accepted-accuracy gains over brittle pairwise/value-only baselines,
- but near-tie hard-slice improvement is not dominant,
- and learned-risk contribution is mixed.

## Commands run

```bash
python -m py_compile scripts/run_branch_value_uncertainty_strict_validation_pass.py scripts/run_branch_value_uncertainty_derived_defer_experiment.py
python scripts/run_branch_value_uncertainty_strict_validation_pass.py \
  --targets-root outputs/branch_label_bruteforce_targets/strict_validation_proxy_20260418 \
  --run-id branch_value_uncertainty_strict_validation_20260418 \
  --regimes all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer \
  --seeds 11,29,47 \
  --feature-set v3
```

## Artifacts written

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_config.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_results.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_summary.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_20260418/strict_validation_manifest.json`

## Next exact recommended step

Run the same strict validation script on real canonical `regime_*` target roots when mounted in the environment (same seeds/settings), then decide continuation based on whether near-tie gains persist under true canonical artifacts.
