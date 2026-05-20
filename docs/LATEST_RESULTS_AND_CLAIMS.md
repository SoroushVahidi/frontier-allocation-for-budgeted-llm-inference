# Latest Results and Safe Claims

**Last updated:** 2026-05-20 (final FIX-2+FIX-4 all-external postrun completed; aggregate-720 claim decision updated; FIX-8 parser prototype evaluated offline)

This document is the canonical single-page record of the most recent empirical results and what can and cannot be claimed based on them.

---

## 0. Current Operational Checkpoint

- Current best effective policy: **FIX-2+FIX-4**.
- **FIX-5 is not promoted** as the current best policy after unbiased validation.
- **FIX-6 / LoVEC extra-action is not promoted** after the independent Stage-2 relaunch.
- **FIX-7 is an offline prototype only** (no runtime promotion claim).
- Final all-baseline 300-example validation for seed `71` is complete:
  - validation root: `outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/`
  - postrun root: `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/`
- Safe current claim: FIX-2+FIX-4 is ahead by point estimate on final-300 and aggregate-720, with positive stratified CI lower bounds vs L1/S1/TALE/best-external.
- New reviewer-risk baseline: a four-answer pooled ensemble (frontier + L1 + S1 + TALE, strict majority with frontier tie-break) reaches 253/300 = 84.33% on Final-300 and 575/720 = 79.86% on Aggregate-720. FIX-2+FIX-4 remains ahead by point estimate (260/300 = 86.67%; 581/720 = 80.69%), but the paired/bootstrap CI vs this pooled ensemble includes zero (Final-300 delta +2.33pp CI [-0.67, +5.67]; Aggregate-720 delta +0.83pp CI [-1.11, +2.78]). Do not claim statistically separated superiority over pooled ensembles.
- Unsafe current claim: do not extrapolate beyond this benchmark setting without additional independent runs.

---

## 1. Final All-External Validation (300 examples, unbiased)

**Validation artifact root:** `outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/`
**Postrun artifact root:** `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/`
**Seed / budget:** `71 / 6`
**Rows:** `1200` (`300 examples × 4 methods`)
**Integrity:** rows `1200/1200`, unique examples `300/300`, duplicates `0`, all rows scored, promotion review coverage `100%`, leakage scan hit rows `0`, no runtime/rate-limit/cap errors in log scan.

| Method / Policy | Accuracy |
|---|---|
| `direct_reserve_semantic_frontier_v2` (frontier) | 76.67% (230/300) |
| `external_l1_max` | 83.00% (249/300) |
| `external_s1_budget_forcing` | 82.00% (246/300) |
| `external_tale_prompt_budgeting` (TALE) | 78.33% (235/300) |
| `FIX-2` | 85.67% (257/300) |
| `FIX-2+FIX-4` | **86.67%** (260/300) |
| `FIX-5` | 78.67% (236/300) |

FIX-2+FIX-4 paired deltas (bootstrap 95% CI, 5000 resamples):
- vs `external_l1_max`: `+3.67pp` `[+0.33, +7.00]`, wins/losses/ties `19/8/273`
- vs `external_s1_budget_forcing`: `+4.67pp` `[+1.00, +8.33]`, wins/losses/ties `23/9/268`
- vs `external_tale_prompt_budgeting`: `+8.33pp` `[+5.00, +12.00]`, wins/losses/ties `27/2/271`
- vs pooled four-answer ensemble: `+2.33pp` `[-0.67, +5.67]`, wins/losses/ties `16/9/275`
- vs external-only L1/S1/TALE majority: `+1.33pp` `[-1.00, +3.67]`, wins/losses/ties `8/4/288`

Interpretation:
- FIX-2+FIX-4 is best by point estimate on the final unbiased 300-example run.
- On this run, CI lower bounds are positive vs all external baselines.
- The pooled-ensemble baselines are closer than individual external baselines; report them as robustness checks, not as statistically separated wins.

### Gate-action decomposition

Inside the combined FIX-2+FIX-4 policy:
- Final-300: FIX-2 fires on 63 examples, FIX-4 fires on 3 examples after FIX-2 does not fire, and no gate fires on 234 examples. FIX-4 changes 3 originally wrong frontier answers into 3 correct final answers, with 0 losses.
- Aggregate-720: FIX-2 fires on 122 examples, FIX-4 fires on 5 examples after FIX-2 does not fire, and no gate fires on 593 examples. FIX-4 changes 5 originally wrong frontier answers into 5 correct final answers, with 0 losses.

---

## 1B. Prior Promotion-Grade Validation (300 examples, unbiased)

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

## 1A. FIX-7 Offline Prototype (No Promotion)

**Artifact root:** `outputs/fix7_cluster_selector_offline_eval_20260520_20260520T014151Z/`
**Scope:** Offline-only replay of conservative cluster-level selector + robust parser arbitration.
**Runtime status:** FIX-2+FIX-4 remains current deployed/best effective policy.

What was added:
- `experiments/cluster_answer_selector.py` (conservative parser/canonicalizer + clustering primitives)
- `scripts/run_fix7_cluster_selector_offline_eval.py` (offline rule sweep + reporting)
- `tests/test_cluster_answer_selector.py`

Claim boundary:
- This is prototype evidence only.
- No live/API promotion decision is made from this run.
- Recommendation file is conservative (`fix7_next_decision.json` => `B`: keep prototype; wait for independent final validation before any promotion).

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
- The first 40-case extra-action pilot produced positive action-value signal but overlapped prior evidence and is not promotion-grade by itself.

---

## 13. Independent FIX-6 Stage-2 Relaunch (80 selected cases, disjoint from prior union)

**Input root:** `outputs/fix6_lovec_independent_extra_action_pilot_20260519T163021Z/`
**Postrun root:** `outputs/fix6_lovec_independent_stage2_postrun_20260519_20260519T191510Z/`
**Stage-2 seed / budget:** `67 / 6`
**Rows:** `160` (`80 examples × 2 methods`)
**Methods:** `direct_reserve_semantic_frontier_v2`, `external_tale_prompt_budgeting`

Integrity summary:
- Status: `160/160 scored`
- Duplicate rows: `0`
- Runtime/rate-limit/cap failures: none observed in live logs
- Prompt/feature leakage scan (`gold`/`exact` terms): `0` hits
- Promotion-review fields in Stage-2 rows: missing (`enough_for_promotion_review = no`)

Selected-case mix:
- `tier2 / all_methods_wrong`: `31`
- `tier2 / residual_low_depth_not_caught`: `4`
- `tier3 / not_failure` controls: `45`

Action-value results vs Stage-1 FIX-2+FIX-4 baseline:

| Action proxy | Correctness | Recoveries vs FIX-2+FIX-4 | Regressions vs FIX-2+FIX-4 | Net vs FIX-2+FIX-4 | Net vs TALE | Control regression rate |
|---|---:|---:|---:|---:|---:|---:|
| Extra frontier proxy | 55.00% (44/80) | 3 | 4 | **-1** | +5 | 8.89% (4/45) |
| Extra TALE retry proxy | 51.25% (41/80) | 1 | 5 | **-4** | +2 | 11.11% (5/45) |

Residual-category breakdown (net vs FIX-2+FIX-4):
- Extra frontier: `all_methods_wrong +1`, `residual_low_depth_not_caught +2`, `not_failure -4`
- Extra TALE retry: `all_methods_wrong +1`, `residual_low_depth_not_caught 0`, `not_failure -5`

Comparison to first 40-case overlapping pilot:
- First pilot was positive by mean delta for both actions.
- Independent relaunch **did not replicate** net-vs-FIX-2+FIX-4 gains:
  - extra frontier: from nonnegative pilot signal to net `-1`
  - extra TALE retry: from nonnegative pilot signal to net `-4`
- Control-slice regressions remained material.

Decision from independent relaunch:
- **E: abandon extra-action promotion now; proceed with FIX-2+FIX-4 validation/writing.**
- No accuracy-changing LoVEC-1 rule is ready for deployment from this independent run.

Safe claim update:
- The independent Stage-2 relaunch does **not** currently support promoting an accuracy-changing LoVEC extra-action policy over FIX-2+FIX-4.

Unsafe claim update:
- Do not claim that extra frontier or extra TALE retry is deployable from current independent evidence.

---

## 14. Next Recommended Step

**Recommended: E — Do not promote extra-action LoVEC now; proceed with FIX-2+FIX-4 validation/writing.**

Rationale:
- The independent Stage-2 relaunch did not produce positive net gain vs FIX-2+FIX-4 for either action proxy.
- Control-slice (`tier3/not_failure`) regressions are non-trivial and erase tier2 gains.
- The strongest inference-available trigger candidate (`low_depth=true` with split external signature) still has negative net effect in the independent run.
- Current evidence supports documenting LoVEC as exploratory scaffolding, not an accuracy-changing runtime policy.

Current status (2026-05-19):
- 40-case overlapping extra-action pilot: completed and positive but non-promotion-grade due to overlap.
- Independent 80-case Stage-2 relaunch: completed with 160/160 rows and negative net-vs-FIX-2+FIX-4 action value.
- No deployable LoVEC-1 action rule is justified from current independent evidence.

---

## 15. Source Files

| File | Purpose |
|---|---|
| `experiments/support_aware_selector.py` | FIX-1 through FIX-5 and combined policy implementations |
| `experiments/value_of_compute_controller.py` | FIX-6 / LoVEC-1 state extraction, action availability, controller scaffold, offline observable oracle helper |
| `tests/test_support_aware_selector.py` | FIX-1..FIX-5 tests |
| `tests/test_value_of_compute_controller.py` | FIX-6 scaffold tests |
| `scripts/run_fix6_lovec1_offline_eval.py` | Offline FIX-6 evaluation driver (no API calls) |
| `outputs/overnight_fix5_postrun_eval_20260519_20260519T134633Z/` | Canonical postrun for latest 300-example unbiased validation |
| `outputs/fix6_lovec1_value_of_compute_20260519_20260519T140300Z/` | FIX-6 offline feasibility outputs and pilot plan |

---

## 16. FIX-2+FIX-4 Aggregate Unbiased Evidence (Primary: 300 + 120 disjoint)

**Artifact root:** `outputs/fix24_aggregate_validation_evidence_20260519_20260519T222123Z/`

Primary inclusion (disjoint, unbiased):
- `main_300_unbiased_seed41_budget6` (`300` examples, seed `41`, budget `6`)
- `independent_stage1_base_120_seed61_budget6` (`120` examples, seed `61`, budget `6`)

Sensitivity-only (excluded from primary due design/tuning role):
- `promotion_grade_100_seed31_budget6` (`100` examples, seed `31`, budget `6`)

Primary integrity:
- Primary overlap checks: `example_id overlap = 0`, `question-hash overlap = 0`
- Required methods present for all primary groups
- All primary rows scored
- Promotion-review coverage present on primary rows
- Leakage scan note: one lexical false-positive pattern (`exact`) appears in question text for one stage-1 case family; no gold/exact-match feature leakage evidence in routing fields

Primary aggregate accuracy (`N = 420`):
- `FIX-2+FIX-4`: `321/420 = 76.43%`
- `external_l1_max`: `310/420 = 73.81%`
- `external_s1_budget_forcing`: `309/420 = 73.57%`
- `external_tale_prompt_budgeting`: `306/420 = 72.86%`

Primary paired deltas (FIX-2+FIX-4 minus external):
- vs `external_l1_max`: `+2.62pp`, stratified 95% CI `[-0.48, +5.71]`
- vs `external_s1_budget_forcing`: `+2.86pp`, stratified 95% CI `[+0.24, +5.71]`
- vs `external_tale_prompt_budgeting`: `+3.57pp`, stratified 95% CI `[+1.19, +5.95]`
- vs source-local best external comparator: `+2.62pp`, stratified 95% CI `[+0.24, +5.00]`

Sensitivity (primary + 100-example set, `N = 520`):
- Point estimate remains positive vs all externals, but best-external delta softens (`+2.12pp`) and remains modest.

Decision update:
- **Recommended action: D (document promising but still-conservative result).**
- FIX-2+FIX-4 is current best effective policy by point estimate on disjoint unbiased aggregate.
- CI evidence is stronger than the single 300-example view, but **all-external superiority is not yet fully locked** because the stratified CI vs `external_l1_max` still crosses zero.

Safe claim update:
- FIX-2+FIX-4 is ahead of TALE and S1 with positive paired lower bounds on the current disjoint unbiased aggregate.
- FIX-2+FIX-4 is ahead of L1 by point estimate, but L1 paired CI still crosses zero.

Unsafe claim update:
- Do not claim definitive superiority over all external baselines yet.

---

## 17. Final Aggregate Update (Primary: 300 + 120 + 300 = 720)

**Artifact root:** `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/`

Primary inclusion (disjoint, unbiased):
- `main_300_seed41_budget6`
- `independent_stage1_base_120_seed61_budget6`
- `final_300_seed71_budget6`

Cross-source overlap checks:
- `example_id` overlap: `0` across all source pairs.
- `question-hash` overlap: `0` across all source pairs.

Aggregate accuracy (`N = 720`):
- `FIX-2+FIX-4`: `581/720 = 80.69%`
- `external_l1_max`: `559/720 = 77.64%`
- `external_s1_budget_forcing`: `555/720 = 77.08%`
- `external_tale_prompt_budgeting`: `541/720 = 75.14%`

Paired deltas (FIX-2+FIX-4 minus external; source-stratified bootstrap, 5000 resamples):
- vs `external_l1_max`: `+3.06pp`, 95% CI `[+0.83, +5.42]`, `p(delta>0)=0.995`
- vs `external_s1_budget_forcing`: `+3.61pp`, 95% CI `[+1.39, +5.69]`, `p(delta>0)=0.999`
- vs `external_tale_prompt_budgeting`: `+5.56pp`, 95% CI `[+3.61, +7.50]`, `p(delta>0)=1.000`
- vs source-local best external: `+3.06pp`, 95% CI `[+1.11, +5.00]`, `p(delta>0)=0.999`

Sensitivity-only include (add prior 100-example seed-31 set, `N = 820`):
- vs L1: `+3.06pp -> +3.41pp` (shift `+0.36pp`)
- vs S1: `+3.61pp -> +3.78pp` (shift `+0.17pp`)
- vs TALE: `+5.56pp -> +4.88pp` (shift `-0.68pp`)
- vs best external: `+3.06pp -> +2.68pp` (shift `-0.37pp`)
- Conclusion unchanged: FIX-2+FIX-4 remains ahead by point estimate.

Claim readiness decision:
- **Decision: A** (strong enough to begin result packaging/write-up preparation).
- All aggregate source-stratified CI lower bounds are strictly above zero vs L1/S1/TALE/best-external.
- Margin vs best external is positive and above the 1pp publication-meaningful threshold.

Safe claim update:
- FIX-2+FIX-4 currently beats all three external baselines by point estimate on both final-300 and aggregate-720, with positive aggregate stratified lower bounds.

Unsafe claim update:
- Do not generalize this result to other datasets/providers/budgets without independent validation.

---

## 18. FIX-8 Robust Parser/Canonicalizer Prototype (Offline, No Promotion)

**Artifact root:** `outputs/fix8_parser_canonicalizer_eval_20260520_20260520T033331Z/`
**Scope:** offline parser/canonicalization re-evaluation only (no new generations, no API calls).
**Variants evaluated:** `R0`, `P1`, `P2`, `P3`, `P4`.

Key outcome:
- On final-300, all FIX-8 variants matched baseline FIX-2+FIX-4 exactly:
  - R0/P1/P2/P3/P4: `260/300 = 86.67%`
  - recoveries/regressions vs R0: `0/0` for all variants.
- On aggregate-720, all FIX-8 variants also matched baseline exactly:
  - R0/P1/P2/P3/P4: `581/720 = 80.69%`
  - recoveries/regressions vs R0: `0/0` for all variants.
- Parser-failure stress slice:
  - referenced parser/canonicalization cases: `12`
  - recovered by FIX-8 variants in this replay: `0`
  - remaining wrong: `12`

Decision:
- `fix8_next_decision.json` => **C** (explicit cue anchoring is the safest constrained form), but **no promotion** because there is no measured gain over baseline on final-300 or aggregate-720.

Safe claim update:
- FIX-8 prototype is implemented and offline-validated.
- Current evidence does not support changing the promoted policy due to parser/canonicalization changes.

Unsafe claim update:
- Do not claim parser-driven accuracy improvement from FIX-8 on current unbiased validation artifacts.
