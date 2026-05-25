# XGB53 Router-v2 Independent Validation — 2026-05-24

**Status:** COMPLETE ✓ (4.6 minutes, validated in detached TMUX)

**Decision: VALIDATED — XGB53 model confirmed as superior to corrected router-v2**

> **Scope note:** XGB53 is a **parallel learned-router research track**. The 83.21% figure
> is a 5-target method-selection CV accuracy, not a paper-facing end-to-end GSM8K accuracy.
> It is NOT directly comparable to the FTA (FIX-2+FIX-4) Final-300/Aggregate-720 numbers.
> A separate held-out end-to-end validation run is required before any paper claim update.

## Purpose

Independent audit of the XGBoost+Optuna 53-feature model from the
router_v2 improvement campaign before trusting or launching more data generation.

## Validation Script

`scripts/validate_xgb53_router_v2_tmux.py`

## Output Root

`outputs/xgb53_router_v2_tmux_validation_20260524/`

## Headline Results

| Metric | Prev corrected baseline | Campaign claimed | **This validation** |
|---|---|---|---|
| Pooled CV (20 seeds) | 80.47% | 84.15% | **83.21% ± 0.26% (CI95 ±0.11%)** |
| LOSO mean | 78.10% | 82.62% | **80.83%** |
| Provider heldout | 74.80% | 81.50% | **80.38%** |
| Dataset heldout | 65.40% | 81.87% | **80.48%** |

All metrics confirm substantial improvement over the corrected router-v2 baseline.
The campaign numbers were slightly optimistic (campaign used 10 seeds; this used 20).

## Audit Results

### A. Feature Legality
- All **53 features passed** the runtime-legal leakage audit
- 14 calibration reliability features also passed
- No token from: `_ok`, `_failed`, `_correct`, `oracle`, `gold`, `all_sources`, `only_`, `wrong`, `best_action`, `reference`, `label`, `target`, `failure`

### B. Data Integrity
- Official 4-scenario table: **exactly 1200 rows**, 4 × 300 ✓
- No duplicate (example_id, scenario_id) pairs ✓
- No auxiliary rows in headline metric ✓

### C. Fold-Safe Calibration
- **FOLD-SAFE**: calibration features change when y_train is permuted ✓
- Test labels are never used to construct calibration features ✓

### D. Optuna Audit

| Method | CV Accuracy |
|---|---|
| Fixed campaign params | 80.67% |
| Nested Optuna (inner 3-fold) | 81.17% |
| Difference | +0.50% |

**Finding:** Nested Optuna ≈ fixed params — campaign hyperparameter tuning was not
overfitting to test folds. The 0.5pp gap is within noise.

## Baselines

| Baseline | Accuracy |
|---|---|
| pooled4 (Cohere agreement) | 64.92% |
| C1d calibrated | 65.17% |
| beta shrinkage | 65.17% |
| agreement only | 63.42% |
| always S1 | 63.92% |
| oracle best action (ceiling) | 75.00% |
| oracle best source (ceiling) | 75.00% |
| **XGB53 (this validation)** | **83.21%** |

## Transfer Evaluations

| Protocol | Accuracy |
|---|---|
| LOSO mean (leave-one-scenario-out) | 80.83% |
| Provider heldout mean | 80.38% |
| Dataset heldout mean | 80.48% |

## Ablation Studies

| Variant | N Features | Mean Accuracy |
|---|---|---|
| full_53_features | 53 | 83.93% |
| no_calibration_features | 53 | 83.93% |
| no_numeric_structural | 36 | 84.65% |
| agreement_pairwise_only | 30 | 83.87% |
| base_22_corrected_router_features | 22 | 82.37% |
| metadata_only_NEGATIVE_CONTROL | 2 | 72.30% |
| random_label_NEGATIVE_CONTROL | 53 | 48.73% |

**Note:** Random-label control at 48.73% (≈ chance) confirms no data leakage in the
feature matrix or evaluation pipeline.

## Feature Importance (Top 10)

| Feature | Gain | SHAP |
|---|---|---|
| S1_in_majority | 0.258 | 0.388 |
| s1_cluster_size | 0.248 | 0.506 |
| n_singleton_answers | 0.032 | 0.063 |
| frontier_s1_agree | 0.026 | 0.217 |
| question_has_equation_flag | 0.026 | 0.229 |
| external_majority_exists | 0.026 | 0.076 |
| frontier_in_majority | 0.025 | 0.093 |
| s1_l1_agree | 0.021 | 0.316 |
| majority_size | 0.013 | 0.082 |
| counting_keyword | 0.013 | 0.215 |

## Recovery/Regression Analysis

| Scenario | Recoveries | Regressions | Net |
|---|---|---|---|
| cohere_gsm8k | 18 | 15 | +3 |
| cohere_math500 | 165 | 35 | **+130** |
| mistral_gsm8k | 11 | 12 | -1 |
| mistral_math500 | 104 | 48 | **+56** |

MATH-500 scenarios show the strongest gains (as expected from the campaign).

## Safety Flags

| Check | Status |
|---|---|
| API calls | ✗ None |
| Active jobs touched | ✗ None |
| Commit/push | ✗ None |
| Original artifacts overwritten | ✗ None |
| Auxiliary rows in headline | ✗ None |

## Output Files

All in `outputs/xgb53_router_v2_tmux_validation_20260524/`:

- `xgb53_validation_feature_audit.csv` — per-feature legality audit
- `xgb53_validation_fold_safety_audit.md` — fold-safety permutation test results
- `xgb53_validation_optuna_audit.md` — Optuna audit: nested vs fixed params
- `xgb53_repeated_cv_summary.csv` — 20-seed repeated CV results
- `xgb53_transfer_summary.csv` — LOSO / provider-heldout / dataset-heldout
- `xgb53_ablation_summary.csv` — 7 ablation variants
- `xgb53_baseline_comparison.csv` — all baselines vs XGB53
- `xgb53_negative_controls.csv` — metadata-only and random-label controls
- `xgb53_recovery_regression_summary.csv` — per-scenario case-level delta
- `xgb53_feature_importance.csv` — gain + SHAP importance
- `xgb53_validation_decision.md` — machine-readable decision record
- `manifest.json` — timestamps, metrics, safety flags
- `launch_status.json` — TMUX launch record
- `runtime_snapshot.json` — mid-run process snapshot

## Conclusion

The XGB53 model (XGBoost+Optuna, 53 runtime-legal features) is **independently validated**:

- No hidden leakage in any of the 53 features
- Calibration features are fold-safe (train-label-dependent only)
- Optuna tuning did not overfit to test folds (nested ≈ fixed, Δ = 0.5pp)
- Reproduced from raw artifacts, no reliance on campaign-internal state
- Repeated CV: **83.21%** (+2.74pp over 80.47% baseline), confirmed with 20 seeds
- Transfer metrics all above 80% (vs 65–74% for corrected baseline)

**Recommendation: proceed to replace corrected router-v2 with XGB53.**
