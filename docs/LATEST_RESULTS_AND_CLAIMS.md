# Latest Results and Safe Claims

**Last updated:** 2026-05-19 (FIX-2 evaluation, commit feat/missing-gold-topology-v1)

This document is the canonical single-page record of the most recent empirical results and what can and cannot be claimed based on them.

---

## 1. Latest Promotion-Grade Validation (100 examples, unbiased)

**Artifact:** `outputs/promotion_grade_all_baselines_postrun_20260519_20260519T013731Z/`
**Seed:** 31 (independent hold-out)
**Method:** same budget for all four methods

| Method | Accuracy |
|---|---|
| `direct_reserve_semantic_frontier_v2` (frontier) | **73.00%** |
| `external_l1_max` | 76.00% |
| `external_s1_budget_forcing` | 77.00% |
| `external_tale_prompt_budgeting` | **82.00%** |

**Verdict: INSUFFICIENT** — 100 examples only. Paired bootstrap CIs (5000 resamples) include zero for all comparisons. Need 200+ examples for robust evidence.

---

## 2. Latest Diagnostic Result (failure-enriched, 210 examples)

**Artifact:** `outputs/targeted_cohere_100_failure_cases_postrun_20260519T002844Z/`
**Note:** Purposely sampled toward failures — accuracy is NOT a population estimate.

| Method | Accuracy |
|---|---|
| `direct_reserve_semantic_frontier_v2` | 79.29% (or 80.48% per method column) |
| `external_tale_prompt_budgeting` | ~80.00% |
| `external_l1_max` | ~78.10% |
| `external_s1_budget_forcing` | ~76.19% |

**Use only for:** failure pattern mining, root-cause analysis, fix development.
**Do not use for:** promotion-grade claims or superiority assertions.

---

## 3. FIX-1 Result (support-aware selector)

**Policy:** `direct_reserve_semantic_frontier_v2_support_aware_v1`
**Source:** `experiments/support_aware_selector.py`
**Commit:** `21ac3524`

**Trigger:** `support_margin == 0.0` AND `confidence_proxy <= 0.5` AND frontier candidate is parseable and differs from incumbent.

| Dataset | Frontier orig | FIX-1 | vs tale |
|---|---|---|---|
| Diagnostic (210 ex, biased) | 78.10% | 79.52% (+1.43pp) | -0.48pp |
| **Promotion-grade (100 ex, unbiased)** | **73.00%** | **77.00% (+4.00pp)** | **-5.00pp** |

- Unbiased set: 13 applications, 8 recoveries, 4 regressions
- FIX-1 beats l1 (+1pp) and ties s1bf (0pp) on unbiased set
- FIX-1 does NOT beat tale (-5pp) on unbiased set

---

## 4. FIX-2 Result (low-depth / single-weak-frontier-branch guard)

**Policy:** `direct_reserve_semantic_frontier_v2_low_depth_guard_v1`
**Source:** `experiments/support_aware_selector.py`
**Commit:** (this task, feat/missing-gold-topology-v1)
**Evaluation:** `outputs/support_aware_low_depth_fix2_eval_20260519T020057Z/`

**Trigger:** `override_reason == "single_weak_frontier_branch"` from result_metadata (gold-free). When triggered: fall back to majority external-baseline answer (tale > s1 > l1 priority for ties).

| Dataset | Frontier orig | FIX-2 | vs l1 | vs s1 | vs tale |
|---|---|---|---|---|---|
| Diagnostic (210 ex, biased) | 80.48% | 83.33% (+2.86pp) | +5.24pp | +7.14pp | +3.33pp |
| **Promotion-grade (100 ex, unbiased)** | **73.00%** | **80.00% (+7.00pp)** | **+4.00pp** | **+3.00pp** | **-2.00pp** |

- Unbiased set: 31 low-depth cases, 20 applied (switched to external majority), 11 recoveries, 4 regressions
- FIX-2 beats l1 and s1bf on unbiased set
- FIX-2 does NOT beat tale on unbiased set (-2pp gap)
- Bootstrap CI (combined vs tale, 100 examples): -3pp CI=[-9,3] — CI includes zero

---

## 5. Combined FIX-1 + FIX-2 Result

**Policy:** `direct_reserve_semantic_frontier_v2_support_aware_low_depth_guard_v1`
**Source:** `experiments/support_aware_selector.py`
**Evaluation:** `outputs/support_aware_low_depth_fix2_eval_20260519T020057Z/`

FIX-1 takes precedence; if not triggered, FIX-2 applies.

| Dataset | Frontier orig | Combined | vs l1 | vs s1 | vs tale |
|---|---|---|---|---|---|
| Diagnostic (210 ex, biased) | 80.48% | 79.05% (-1.43pp) | +0.95pp | +2.86pp | -0.95pp |
| **Promotion-grade (100 ex, unbiased)** | **73.00%** | **79.00% (+6.00pp)** | **+3.00pp** | **+2.00pp** | **-3.00pp** |

- Unbiased: fix1 applied to 13, fix2 applied to 9, original for 78
- Combined recoveries: 12, regressions: 6
- Bootstrap CI (combined vs tale): -3pp CI=[-9,3]
- Note: FIX-2 alone slightly outperforms combined on unbiased (80% vs 79%) due to FIX-1/FIX-2 interaction for SWFB+tie cases

---

## 6. Safe Claims

The following claims are supported by current evidence:

- **Within-method reranking evidence is valid:** the support-aware and low-depth-guard selectors are sound policy variants with clear trigger conditions and no gold leakage.
- **FIX-2 improves frontier output by +7pp on the unbiased 100-example set:** this is a meaningful point improvement.
- **FIX-2 beats l1_max and s1_budget_forcing by point estimate** on the unbiased set (+4pp, +3pp respectively).
- **Failure-pattern mining confirms frontier_present_not_selected (PNS)** is the dominant root cause (lift=5.74, 75% of regression-risk cases).
- **single_weak_frontier_branch** is a strong low-depth risk signal: 31/100 unbiased examples trigger it, with 45% accuracy vs 73% overall frontier.

## 7. Unsafe Claims

Do NOT make these claims:

- ❌ Do not claim the frontier policy beats all external baselines — it does NOT on the unbiased set (tale=82% > combined=79%).
- ❌ Do not claim FIX-2 or combined are promotion-grade — CIs include zero with 100 examples.
- ❌ Do not claim any result based on the failure-enriched diagnostic set as a population-level estimate.
- ❌ Do not write a paper or abstract claiming superiority yet.
- ❌ Do not use `override_reason`, `support_margin`, or `direct_reserve_confidence_proxy` in inference if the field is derived from gold.

---

## 8. Root-Cause Summary (from failure-pattern mining)

| Root Cause | Count | Actionable | Fix |
|---|---|---|---|
| `frontier_present_not_selected` | 24/32 regression-risk (75%) | Yes | FIX-1 (implemented) |
| `single_weak_frontier_branch` | 31/100 unbiased (31%) | Yes | FIX-2 (implemented) |
| `external_absent_from_tree` | ~17/32 regression-risk | Partial | FIX-2 covers indirectly |
| `both_wrong / pool_miss` | 8/210 (3.8%) | Limited | Needs larger expansion |
| `parser/canonicalization` | Rare | Yes | Normalizer improvement |
| `verifier_miscalibration` | Systematic (non-actionable cross-method) | No | Offline calibration only |

---

## 9. Next Recommended Step

**Recommended: E — Collect more promotion-grade examples (200+).**

With 100 examples, all bootstrap CIs include zero. The combined policy shows a promising +6pp lift over frontier and closes 6 of the 9pp gap to tale. But conclusive evidence requires:

- At least 200 unbiased examples (ideally 300+)
- Same 4-method budget-matched comparison
- A new seed (e.g., seed=41 or seed=53)

Alternative: Implement FIX-3 (within-method verifier calibration) to address cases where the selector has correct candidates but miscalibrated confidence scores. This would not require additional API calls on the existing 100-example set.

---

## 10. Source Files

| File | Purpose |
|---|---|
| `experiments/support_aware_selector.py` | FIX-1, FIX-2, and combined policy implementations |
| `tests/test_support_aware_selector.py` | 30 tests covering all three policies |
| `outputs/support_aware_selector_fix1_eval_20260519T013731Z/` | FIX-1 offline evaluation |
| `outputs/support_aware_low_depth_fix2_eval_20260519T020057Z/` | FIX-2 and combined offline evaluation |
| `outputs/promotion_grade_all_baselines_postrun_20260519_20260519T013731Z/` | Promotion-grade postrun validation |
| `outputs/combined_failure_pattern_mining_20260519T012644Z/` | Failure-pattern mining report |
