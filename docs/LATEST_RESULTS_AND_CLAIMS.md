# Latest Results and Safe Claims

**Last updated:** 2026-05-19 (overnight 300-example validation + FIX-6 LoVEC-1 offline feasibility)

This document is the canonical single-page record of the most recent empirical results and what can and cannot be claimed based on them.

---

## 1. Latest Promotion-Grade Validation (300 examples, unbiased)

**Validation artifact root:** `outputs/overnight_fix5_promotion_grade_validation_20260519T040621Z/`
**Postrun artifact root:** `outputs/overnight_fix5_postrun_eval_20260519_20260519T134633Z/`
**Seed / budget:** `41 / 6`
**Rows:** `1200` (`300 examples × 4 methods`)
**Integrity:** no runtime/API/rate-limit/cap errors; duplicates `0`; promotion review coverage `100%`; leakage scan pass.

| Method / Policy | Accuracy |
|---|---|
| `direct_reserve_semantic_frontier_v2` (frontier) | **81.00%** (243/300) |
| `external_l1_max` | 80.33% (241/300) |
| `external_s1_budget_forcing` | 80.33% (241/300) |
| `external_tale_prompt_budgeting` (TALE) | 80.33% (241/300) |
| `FIX-2` | 82.67% (248/300) |
| `FIX-2+FIX-4` | **83.33%** (250/300) |
| `FIX-5` | 80.33% (241/300) |

Key paired deltas vs TALE (bootstrap 95% CI):
- Frontier: `+0.67pp` `[-3.67, +5.00]`
- FIX-2: `+2.33pp` `[-0.67, +5.33]`
- FIX-2+FIX-4: `+3.00pp` `[0.00, +6.00]`
- FIX-5: `+0.00pp` `[0.00, +0.00]`

**Interpretation:**
- FIX-5 did not hold on the larger unbiased run (switches `0`, tied TALE).
- Current best base policy is **FIX-2+FIX-4**.
- `+3pp` over TALE is promising by point estimate, but CI lower bound is exactly `0.00`, so this is not yet a publication-strong superiority claim.

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

## 6. FIX-3 Result (within-method verifier calibration guard)

**Policy:** `direct_reserve_semantic_frontier_v2_within_method_calibrated_v1`
**Source:** `experiments/support_aware_selector.py`
**Evaluation:** `outputs/fix3_within_method_calibration_eval_20260519T023843Z/`

**Trigger:** `override_reason == "frontier_not_run_or_budget_exhausted"` OR non-SWFB row with empty `answer_group_best_branch_scores`. When triggered: fall back to external majority. Does NOT fire on SWFB rows (handled by FIX-2).

**Key finding:** AGBS raw scores (0.8–0.975) are not discriminative within non-SWFB rows — they are anti-correlated due to SWFB dominance. FIX-3 uses score *absence* as the signal.

| Dataset | Frontier orig | FIX-3 | Applications | vs tale |
|---|---|---|---|---|
| Diagnostic (210 ex, biased) | 80.48% | 80.95% (+0.48pp) | 1 case | +0.95pp |
| **Promotion-grade (100 ex, unbiased)** | **73.00%** | **73.00% (+0.00pp)** | **0 cases** | **-9.00pp** |

**FIX-3 has near-zero coverage on promotion-grade data.** No `frontier_not_run_or_budget_exhausted` cases appear in the 100-example unbiased set; all non-SWFB rows have AGBS scores present. FIX-3 is structurally correct but does not help on the current promotion-grade artifact.

---

## 7. Combined FIX-1 + FIX-2 + FIX-3 Result

**Policy:** `direct_reserve_semantic_frontier_v2_support_lowdepth_calibrated_v1`
**Source:** `experiments/support_aware_selector.py`
**Evaluation:** `outputs/fix3_within_method_calibration_eval_20260519T023843Z/`

Precedence: FIX-1 → FIX-2 → FIX-3. Only one fires per row.

| Dataset | Frontier orig | Combined | vs l1 | vs s1 | vs tale |
|---|---|---|---|---|---|
| Diagnostic (210 ex, biased) | 80.48% | 79.52% (-0.95pp) | +1.43pp | +3.33pp | -0.48pp |
| **Promotion-grade (100 ex, unbiased)** | **73.00%** | **79.00% (+6.00pp)** | **+3.00pp** | **+2.00pp** | **-3.00pp** |

- Unbiased (fix breakdown): fix1=13, fix2=9, fix3=0, original=78
- Bootstrap CI (5000 resamples): vs l1 +3pp CI=[-5,11], vs s1 +2pp CI=[-5,9], vs tale -3pp CI=[-9,3]
- **Does NOT beat all external baselines** (TALE at 82% remains 3pp ahead)
- **CIs include zero** — 100 examples insufficient for conclusive evidence
- FIX-3 adds no new recoveries on this artifact; combined FIX-1+2+3 = combined FIX-1+2

---

## 8. FIX-4 Result (external unanimous consensus gate)

**Policy:** `direct_reserve_semantic_frontier_v2_external_consensus_gate_v1`
**Combined with FIX-2:** `direct_reserve_semantic_frontier_v2_lowdepth_external_consensus_v1`
**Source:** `experiments/support_aware_selector.py`
**Evaluation:** `outputs/fix4_external_consensus_eval_20260519T031424Z/`

**Trigger:** `override_reason == 'direct_frontier_agree' AND all 3 external baselines give the same answer X AND X != frontier_answer`. Conservative: requires all 3/3 externals and DFA override only. Inference-available, gold-free.

**Key finding:** FIX-4 triggered on exactly the 2 predicted P1 cases (from precise failure pattern mining). Both were recoveries. Zero regressions observed.

| Dataset | Frontier | FIX-2 | FIX-4 alone | **FIX-2+FIX-4** | TALE |
|---|---|---|---|---|---|
| Diagnostic (210 ex, biased) | 78.10% | 83.33% | 78.10% | 83.33% | 80.00% |
| **Promo-grade (100 ex, unbiased)** | **73.00%** | **80.00%** | **75.00%** | **82.00%** | **82.00%** |

- Promo: FIX-4 applied=2, recoveries=2, regressions=0
- **FIX-2+FIX-4 = 82% — ties TALE by point estimate**
- Bootstrap CI vs TALE: +0.00pp CI=[-5, +5] — includes zero (100 examples insufficient)
- Bootstrap CI vs l1: +6.00pp CI=[0, +12] — marginally includes zero (boundary)
- Bootstrap CI vs s1: +5.00pp CI=[-1, +12] — includes zero

| Combined Policy | Promo Accuracy |
|---|---|
| FIX-1+2+3+4 | 81.00% |
| **FIX-2+4** | **82.00%** ← best policy |
| FIX-1+2 | 79.00% |
| FIX-2 alone | 80.00% |

Note: FIX-1+2+3+4 = 81% (slightly below FIX-2+4 = 82%) because FIX-1 takes priority over FIX-2 for some SWFB+tie cases where FIX-2 would have been correct.

---

## 9. FIX-5 Result (TALE-default conservative agreement-region router)

**Policy:** `external_tale_default_frontier_switch_v1`
**Source:** `experiments/support_aware_selector.py`
**Evaluation:** `outputs/fix5_tale_default_router_eval_20260519T035829Z/`

**Policy design:**
- default to `external_tale_prompt_budgeting`
- compute frontier candidate with FIX-2+FIX-4 (`combined24`)
- switch only when:
  - `override_reason == "direct_frontier_agree"`
  - `support_margin > 0`
  - `l1 == s1 != tale`
  - `combined24_answer == l1 == s1`
  - frontier is not low-depth-risk
- never switch when:
  - all three externals unanimously disagree with frontier candidate
  - frontier is low-depth-risk
  - required metadata/answers are missing

| Dataset | FIX-2+4 | TALE | FIX-5 |
|---|---|---|---|
| Diagnostic (210 ex, biased) | 83.33% | 80.00% | 80.00% |
| **Promotion-grade (100 ex, unbiased)** | **82.00%** | **82.00%** | **83.00%** |

- Promotion switches: `1`
- Promotion recoveries/regressions vs TALE: `1 / 0`
- Promo paired bootstrap CI (FIX-5 minus TALE): `+1.0pp`, CI `[0.0, +3.0]pp` (includes boundary zero)
- FIX-5 beats all external baselines by point estimate on the 100-example set, but this is not statistically decisive.

---

## 10. Safe Claims

The following claims are supported by current evidence:

- **On the latest 300-example unbiased run, FIX-2+FIX-4 is the best observed policy** at `83.33%` vs TALE/L1/S1 `80.33%` (point delta `+3.00pp`).
- **FIX-5 did not transfer to the 300-example run** (switches `0`, accuracy `80.33%`, tied TALE/L1/S1).
- **FIX-2+FIX-4 remains gold-free and inference-available** (no gold/exact/correctness used in runtime trigger logic).
- **FIX-6 / LoVEC-1 scaffold is implemented offline** and currently defaults safely to FIX-2+FIX-4 while logging state/action availability.
- **Observed-action oracle analysis indicates nontrivial remaining headroom** but also irreducible errors without new generation (`24/50` FIX-2+FIX-4 errors on the 300-example run).

## 11. Unsafe Claims

Do NOT make these claims:

- ❌ Do not claim robust superiority over TALE from FIX-2+FIX-4 yet — the paired CI lower bound is exactly `0.00pp` on the 300-example run.
- ❌ Do not claim FIX-5 is the preferred policy — it did not switch and did not beat TALE on the latest main run.
- ❌ Do not claim any result based on the failure-enriched diagnostic set as a population-level estimate.
- ❌ Do not claim LoVEC-1 gains from offline oracle as deployable runtime gains; oracle rows are diagnostic and label-backed.
- ❌ Do not use gold/exact/correctness/example_id/artifact path as runtime features for LoVEC.

---

## 12. FIX-6 Feasibility (Offline Only)

**Artifact:** `outputs/fix6_lovec1_value_of_compute_20260519_20260519T140300Z/`

Main 300-example findings:
- LoVEC-1 (current scaffold): `83.33%` (equal to FIX-2+FIX-4; no accuracy-changing switches yet)
- Logged frontier-alternative availability: `42.0%`
- Logged external-alternative availability: `30.0%`
- Observable-action oracle upper bound: `92.0%` (`+8.67pp` vs FIX-2+FIX-4, diagnostic upper bound only)
- FIX-2+FIX-4 errors: `50`
- Reducible with logged alternatives: `26`
- Irreducible without new generation: `24`

Interpretation:
- There is enough logged counterfactual structure to justify a value-of-compute direction.
- There is **not** enough outcome data to claim deployable gains from accuracy-changing LoVEC routing without new extra-action collection.

---

## 13. Next Recommended Step

**Recommended: A — Run a minimal extra-action Cohere pilot for LoVEC-1 (30–50 cases, capped, tmux, promotion-review logging).**

Rationale:
- FIX-2+FIX-4 is currently strongest on main unbiased evidence.
- LoVEC-1 scaffold is implemented but intentionally non-switching for safety.
- Offline observable oracle shows potential, but a substantial irreducible subset still requires new generation outcomes.
- Next progress bottleneck is collecting disjoint extra-action outcomes, not another selector-only tweak.

Status update (2026-05-19):
- Extra-action replay pilot is currently running in tmux (`fix6_lovec_extra_action_pilot_20260519`) under `outputs/fix6_lovec1_extra_action_pilot_20260519T141709Z/`.
- Offline postrun converter is prepared: `scripts/analyze_fix6_extra_action_pilot.py`.
- No new empirical claims are made until pilot completion and postrun analysis.

---

## 14. Source Files

| File | Purpose |
|---|---|
| `experiments/support_aware_selector.py` | FIX-1 through FIX-5 and combined policy implementations |
| `experiments/value_of_compute_controller.py` | FIX-6 / LoVEC-1 state extraction, action availability, controller scaffold, offline observable oracle helper |
| `tests/test_support_aware_selector.py` | FIX-1..FIX-5 tests |
| `tests/test_value_of_compute_controller.py` | FIX-6 scaffold tests |
| `scripts/run_fix6_lovec1_offline_eval.py` | Offline FIX-6 evaluation driver (no API calls) |
| `outputs/overnight_fix5_postrun_eval_20260519_20260519T134633Z/` | Canonical postrun for latest 300-example unbiased validation |
| `outputs/fix6_lovec1_value_of_compute_20260519_20260519T140300Z/` | FIX-6 offline feasibility outputs and pilot plan |
