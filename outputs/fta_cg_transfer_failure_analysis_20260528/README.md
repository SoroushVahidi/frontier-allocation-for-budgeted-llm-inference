# FTA-CG Transfer Failure Analysis

**Date:** 2026-05-28  
**Classification of evaluated rule:** OVERFIT_RULE (see evaluation report)  
**Input evaluation directory:** `/tmp/fta_corroboration_guard_eval_20260528_151259/`  
**Purpose:** Offline post-mortem to understand why FTA-CG showed +1.43pp on MATH-500 seed=11 (discovery) but +0.00pp on MATH-500 seed=71 (disjoint validation).

---

## Summary of Findings

### 1. What FTA-CG does

Before applying FIX-2 (Low-Depth Guard), the Corroboration Guard (CG) checks whether any external method (L1, S1, TALE) agrees with the frontier answer. If yes, FIX-2 is suppressed and frontier is kept.

### 2. Why it fails to transfer on MATH-500

**Finding 1 — All changed decisions are 1-of-3 corroboration cases.**

Every one of the 112 changed decisions (across all datasets) has exactly 1-of-3 externals corroborating the frontier. This is a mathematical necessity: if 2+ externals corroborate frontier, the external majority equals frontier, so FIX-2 is already a no-op (it only switches when `ext_majority != frontier`). The guard therefore only fires — and only matters — in the 1-of-3 pattern.

**Finding 2 — Wins and losses on MATH-500 seed=71 are perfectly balanced (5 wins, 5 losses).**

| Set | CG wins | CG losses | Net | Both-wrong |
|---|---:|---:|---:|---:|
| math500_seed11_discovery | 11 | 4 | +7 | 30 |
| math500_seed71_disjoint | 5 | 5 | **0** | 16 |
| gsm8k_final300_seed71 | 5 | 0 | +5 | 2 |
| gsm8k_aggregate720 | 10 | 2 | +8 | 7 |
| cloudrift_gsm8k_seed71 | 1 | 2 | −1 | 0 |

On the disjoint MATH-500, every win is cancelled by a loss. No structural signal from the data distinguishes them.

**Finding 3 — Useful suppression rate ≈ frontier baseline accuracy.**

| Set | Frontier acc | Useful supp rate | Suppressions |
|---|---:|---:|---:|
| math500_seed11_discovery | 0.264 | 0.333 | 99 |
| math500_seed71_disjoint | 0.290 | 0.383 | 60 |
| gsm8k_final300_seed71 | 0.790 | 0.841 | 44 |
| gsm8k_seed41 | 0.810 | 0.766 | 47 |
| gsm8k_seed61 | 0.575 | 0.556 | 18 |
| cloudrift_gsm8k_seed71 | 0.873 | 0.864 | 66 |
| gsm8k_aggregate720 | 0.762 | 0.761 | 109 |

The useful suppression rate (fraction of FIX-2 suppressions where frontier was correct) tracks the frontier baseline accuracy almost exactly. The guard is not discriminating which suppressions are beneficial — it simply inherits the frontier base rate. On MATH-500 (frontier ~29% accuracy), only ~1/3 of corroborated frontiers are actually right. On GSM8K (frontier ~79%), ~4/5 are right.

**Finding 4 — No structural feature separates wins from losses on MATH-500.**

Examined features: corroborating method (L1/S1/TALE), non-corroborating external agreement pattern, frontier_support, candidate_pool_answer_group_count, override_reason. None cleanly separate wins from losses:

- All cases: override_reason = `single_weak_frontier_branch`
- All cases: n_corroborating = 1
- Both wins and losses have non_corr_2of2 ∈ {0,1} with nearly equal split

### 3. Why CG helps GSM8K

On GSM8K, the frontier has 79–87% baseline accuracy. When any external corroborates the frontier, the frontier is almost always right. FIX-2 was switching away from a good answer. CG correctly prevents that. The rule is incidentally effective because of high frontier accuracy, not because the 1-of-3 corroboration signal is discriminative.

### 4. Did FTA-CG recover the motivating failures?

On MATH-500 seed=11 (discovery set), 20 examples had "frontier correct, FTA wrong" (the inspected failure pattern). FTA-CG recovered 11/20 = **55%** of these. However:
- 4 new losses were introduced on seed=11
- On disjoint seed=71, 5 wins and 5 losses perfectly cancel

The guard partially fixes the inspected cases but produces equal-magnitude harm on unseen cases.

### 5. Structure of losses (cases where CG hurts)

Loss pattern on MATH-500 seed=71 (5 cases):

| Example | frontier | l1 | s1 | tale | fta (correct) | ftacg (wrong) | gold |
|---|---|---|---|---|---|---|---|
| MATH-500_27 | 1 | 1 (corr.) | 305 | 16 | 16 | 1 | 16 |
| MATH-500_63 | 7 | 8 | 7 (corr.) | 8 | 8 | 7 | 8 |
| MATH-500_99 | 2 | 0 | 2 (corr.) | −1 | −1 | 2 | −1 |
| MATH-500_103 | 3 | 3 (corr.) | 4 | 4 | 4 | 3 | 4 |
| MATH-500_158 | 3 | 4 | 4 | 3 (corr.) | 4 | 3 | 4 |

Pattern: 1 external corroborates the (wrong) frontier, while 1–2 others indicate the correct answer. CG incorrectly suppresses FIX-2. The corroborating external is simply wrong alongside the frontier.

Win pattern on MATH-500 seed=71 (5 cases):

| Example | frontier | l1 | s1 | tale | fta (wrong) | ftacg (correct) | gold |
|---|---|---|---|---|---|---|---|
| MATH-500_34 | 29 | 29 (corr.) | 58 | 1212 | 1212 | 29 | 29 |
| MATH-500_80 | 350 | 300 | 350 (corr.) | 400 | 400 | 350 | 350 |
| MATH-500_101 | 2 | 2 (corr.) | 11 | 11 | 11 | 2 | 2 |
| MATH-500_168 | −13 | −13 (corr.) | 2 | 2 | 2 | −13 | −13 |
| MATH-500_183 | −4 | −4 (corr.) | 1 | 1 | 1 | −4 | −4 |

Pattern: Structurally identical — 1 external corroborates the (correct) frontier, FIX-2 was going to switch to a wrong answer. CG correctly blocks FIX-2.

**The win and loss structures are indistinguishable without gold labels.**

### 6. Candidate narrowed rules — none effective on MATH-500

Tested two alternative conditions for when CG fires:

| Rule | MATH-500 seed=71 net | GSM8K Final-300 net | GSM8K agg-720 net |
|---|---:|---:|---:|
| any_1of3 (current) | 0 | +5 | +8 |
| require non-corr disagree (non_corr_2of2=0) | 0 | −3 | 0 |
| require non-corr agree (non_corr_2of2=1) | 0 | +3 | 0 |

No tested narrowing improves MATH-500 seed=71. The "require non-corr agree" rule preserves more GSM8K benefit than the "disagree" variant but still gives zero on MATH-500.

The root problem is structural: with frontier accuracy ~29%, even a correct corroboration signal fires equally on right and wrong cases because both externals and frontier are frequently wrong independently.

---

## Conclusions

**Main reason FTA-CG failed to transfer:** The 1-of-3 corroboration condition carries near-zero discriminative power on MATH-500 because the frontier baseline accuracy is too low (~29%). The useful suppression rate simply tracks the frontier base rate. On MATH-500, corroborated frontier answers are no more likely to be correct than uncorroborated ones, because both frontier and its corroborating external make shared errors on hard math problems.

**Did it fix the motivating failures?** Partially (55% recovery on discovery set, 20 inspected cases). But for every 2 recovered cases, the guard creates 2 equivalent losses on unseen cases on MATH-500 seed=71.

**Best candidate narrowed rule:** None identified that helps MATH-500 disjoint validation. The "require non_corr_agree" rule (fire CG only when the other 2 externals also disagree among themselves) avoids the 3 worst GSM8K reversals while preserving net +3, but has zero effect on MATH-500 and is not validated.

**Recommendation:** Do not implement FTA-CG in source code. The failure mode is fundamental, not a threshold issue. To address MATH-500 selector errors, the more promising path is improving pool coverage (oracle ceiling 46.3%) rather than adjusting override guards.

---

## Files

| File | Contents |
|---|---|
| `README.md` | This report |
| `changed_cases.csv` | All 112 changed decisions with corroboration features and metadata |
| `win_loss_feature_summary.csv` | Feature comparison between wins and losses by dataset |
| `candidate_narrow_rules_summary.csv` | Net improvement under each candidate narrowing rule |

## Source

Evaluation script: `/tmp/fta_cg_eval.py`  
Evaluation outputs: `/tmp/fta_corroboration_guard_eval_20260528_151259/`  
Key inputs: MATH-500 seed=11 (discovery, 488), MATH-500 seed=71 (disjoint, 300), GSM8K Final-300/Aggregate-720 (Cohere), Cloudrift GSM8K seed=71 (300).
