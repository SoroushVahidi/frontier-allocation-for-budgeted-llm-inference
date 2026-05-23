# Offline Policy Search For Improved Deferral (2026-05-23)

This analysis is **offline-only** and uses existing artifacts only. No API calls were made. Learned/searched policies are diagnostic unless explicitly evaluated in held-out/transfer settings.

## Inputs and Scope

- GSM8K aggregate records: 3 disjoint fixed-pool sources (300 + 120 + 300 = 720 examples).
- MATH-500 complete-case records: 488 examples from transfer diagnostic complete-case intersection.
- Runtime-legal features only for policy decisions; gold/exact used only for offline labels and scoring.

## Unified Dataset Summary

- Total unified examples: **1208** (GSM8K=720, MATH-500=488).
- Current FTA (FIX-2+FIX-4) accuracy: GSM8K **0.8069**, MATH-500 **0.2766**, combined **0.5927**.
- L1 accuracy: GSM8K **0.7764**, MATH-500 **0.3033**, combined **0.5853**.
- Pooled-4 accuracy: GSM8K **0.8208**, MATH-500 **0.2971**, combined **0.6093**.

## Best Hand-Coded Policy (By Combined Accuracy)

- Policy: **`agreement_only_2of3_against_frontier`**
- Combined accuracy: **0.6109** (delta vs current FTA: +0.0182; +1.82 pp).
- GSM8K accuracy: **0.8208** (delta vs current FTA: +1.39 pp).
- MATH-500 accuracy: **0.3012** (delta vs current FTA: +2.46 pp).
- Delta vs MATH-500 L1: -0.20 pp.
- Deferral rate (combined): 0.2003. Recoveries/regressions vs frontier (combined): 102/34 (net +68).

## Best No-Dataset-Indicator Policy

- Policy: **`agreement_only_2of3_against_frontier`**
- Combined accuracy: **0.6109** (delta vs current FTA: +1.82 pp).
- GSM8K delta vs current FTA: +1.39 pp; MATH-500 delta vs current FTA: +2.46 pp.

## Goal Search (A-E)

Top candidates meeting at least one goal are listed in `best_policy_candidates.csv`. First 10:

| policy | A | B | C | D | E | delta combined pp | delta GSM pp | delta MATH pp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `external3_majority_l1_s1_tale` | 1 | 1 | 1 | 1 | 1 | +1.57 | +0.42 | +3.28 |
| `agreement_only_2of3_against_frontier` | 1 | 0 | 1 | 1 | 1 | +1.82 | +1.39 | +2.46 |
| `pooled4_majority_frontier_tiebreak` | 1 | 0 | 1 | 1 | 1 | +1.66 | +1.39 | +2.05 |
| `ldg_to_pooled4_then_eco` | 1 | 0 | 1 | 1 | 1 | +1.08 | +0.69 | +1.64 |
| `ldg_to_external3_l1_s1_tale_then_eco` | 1 | 0 | 1 | 1 | 1 | +0.91 | +0.42 | +1.64 |
| `pooled_support_rule_ldg_diff` | 1 | 0 | 1 | 0 | 1 | +0.66 | +0.00 | +1.64 |
| `conservative_hybrid_ldg_math_to_l1_else_current_fallback_DIAGNOSTIC` | 1 | 0 | 1 | 0 | 0 | +0.50 | +0.00 | +1.23 |
| `ldg_to_l1_then_eco` | 0 | 0 | 0 | 0 | 1 | -0.17 | -1.11 | +1.23 |
| `l1_support_rule_ldg_diff` | 0 | 0 | 0 | 0 | 1 | -0.58 | -1.81 | +1.23 |
| `always_l1` | 0 | 0 | 0 | 0 | 1 | -0.75 | -3.06 | +2.66 |

## Learned / Calibrated Selectors (Diagnostic)

- Full model summary: `learned_policy_summary.csv`
- Transfer summary: `transfer_policy_summary.csv`

Top transfer/held-out results by accuracy:

| experiment | best policy | accuracy | delta vs current FTA (pp) | delta vs L1 (pp) |
|---|---|---:|---:|---:|
| `leave_source_out_gsm8k_seed71_300` | `isotonic_logreg_defer_to_l1_thr_0.15` | 0.8767 | +1.00 | +4.67 |
| `leave_source_out_gsm8k_seed41_300` | `logreg_defer_to_l1` | 0.8533 | +2.00 | +5.00 |
| `train_math_test_gsm` | `logreg_defer_to_l1` | 0.8083 | +0.14 | +3.19 |
| `in_sample_diagnostic_all` | `isotonic_logreg_defer_to_l1_thr_0.25` | 0.6200 | +2.73 | +3.48 |
| `leave_source_out_gsm8k_seed61_120` | `logreg_defer_to_l1` | 0.6000 | +0.83 | +2.50 |
| `train_math_split_test_math_holdout` | `isotonic_logreg_defer_to_l1_thr_0.15` | 0.3741 | +2.72 | +3.40 |
| `train_gsm_plus_small_math_cal_test_math_holdout` | `isotonic_logreg_defer_to_l1_thr_0.15_with_dataset` | 0.3216 | +5.26 | +2.05 |
| `train_gsm_test_math` | `logreg_defer_to_l1` | 0.3156 | +3.89 | +1.23 |

## Dataset Indicator Necessity

- The top combined hand-coded policy does **not** require dataset/source indicator.
- Compare with/without indicator variants in `handcoded_policy_summary.csv` and `learned_policy_summary.csv`.

## Paired CI Summary

- Bootstrap paired CIs (5,000 resamples) are in `paired_ci_summary.csv` for:
  - best policy `agreement_only_2of3_against_frontier` vs current FTA, L1, pooled4 (GSM8K, MATH-500, combined);
  - best no-dataset-indicator policy `agreement_only_2of3_against_frontier` vs current FTA (GSM8K, MATH-500, combined).

## Direct Answers To Requested Questions

1. Best zero-extra-call policy found: `agreement_only_2of3_against_frontier` (combined accuracy 0.6109).
2. Improve MATH-500 without damaging GSM8K: Yes under Goal A threshold.
3. Beat L1 on MATH-500: No.
4. Beat pooled-4 or reduce oracle regret: Yes.
5. Improvement source: inspect recovery/regression and deferral rates; primary driver is captured by policy-specific switch behavior in `handcoded_policy_summary.csv`.
6. Dataset/source-specific calibration required: Not required by top policy.
7. Paid validation run justification: only if freezing one policy from `best_policy_candidates.csv` that meets Goal A/B/C and verifying on an untouched unbiased set.

## Output Files

- `outputs/offline_policy_search_improved_deferral_20260523/manifest.json`
- `outputs/offline_policy_search_improved_deferral_20260523/unified_fixed_pool_records.csv`
- `outputs/offline_policy_search_improved_deferral_20260523/handcoded_policy_summary.csv`
- `outputs/offline_policy_search_improved_deferral_20260523/learned_policy_summary.csv`
- `outputs/offline_policy_search_improved_deferral_20260523/transfer_policy_summary.csv`
- `outputs/offline_policy_search_improved_deferral_20260523/best_policy_candidates.csv`
- `outputs/offline_policy_search_improved_deferral_20260523/paired_ci_summary.csv`
- `outputs/offline_policy_search_improved_deferral_20260523/feature_importance_or_rule_summary.csv`
