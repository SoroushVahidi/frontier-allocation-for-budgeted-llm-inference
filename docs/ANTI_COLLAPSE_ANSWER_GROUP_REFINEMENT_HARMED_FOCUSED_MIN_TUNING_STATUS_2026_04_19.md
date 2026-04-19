# Anti-collapse answer-group refinement harmed-focused minimal tuning status (2026-04-19)

## Scope and rule compliance
This pass intentionally stayed inside the same promoted anti-collapse answer-group refinement line and reused the same bounded matrix/protocol:
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`
- seeds: `[11, 23]`
- budgets: `[6, 8]`
- subset size: `20` per dataset/seed
- compared methods:
  1. `broad_diversity_aggregation_strong_v1` (broad-family baseline)
  2. `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_v1` (current promoted anti-collapse variant)
  3. `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_harmed_tuned_v1` (one minimal harmed-focused follow-up)

No new family was introduced. No broad sweep was run.

## A) Harmed-case analysis first (before tuning changes)
From the current anti-collapse run in this bounded matrix (`anti_collapse_refinement` vs baseline), harmed cases were categorized with the required subtype taxonomy and written to:
- `outputs/anti_collapse_answer_group_refinement_bounded_eval_20260419/pairwise_vs_baseline_harmed_cases.json`

Current anti-collapse harmed count in this rerun: **54** (prior status note reported **51** on the earlier run).

Subtype breakdown (current anti-collapse harmed set):
- repeat/cap threshold too weak: **29**
- anti-collapse blocked a good incumbent continuation: **10**
- residual late commit after improved tree growth: **11**
- alternative matured but still low value: **3**
- alternative preserved but wrong: **1**
- repeat penalty too strong: **0**
- aggregation still underweighted right answer-group: **0**

Dominant residual pattern remained split between:
1) repeat/cap still too weak in harmed slices, and
2) residual late-commit / incumbent-blocking harms.

## B) Minimal tuning applied (interpretable and small)
Only small anti-collapse-line parameter nudges were added in a single new variant:
- `repeated_same_branch_penalty`: `0.09 -> 0.085` (slightly less punitive)
- `repeated_same_branch_cap`: `3 -> 2` (earlier anti-monopolization check)
- `monopolization_margin_requirement`: `0.11 -> 0.09` (less likely to block a clearly strong incumbent)
- `answer_group_distinctness_bonus`: `0.12 -> 0.13` (small extra encouragement for under-covered groups)

Everything else in the mechanism line was kept fixed.

## C) Bounded matrix results (same diagnostics surface)
Using the shared bounded run output `comparison_summary.json`:

### Accuracy
- baseline broad: **0.6500**
- current anti-collapse: **0.6625**
- minimal harmed-tuned: **0.6958**

### First/second split survival
- baseline broad: **0.6208 / 0.6167**
- current anti-collapse: **0.6458 / 0.6292**
- minimal harmed-tuned: **0.6792 / 0.6667**

### Improved / harmed / unchanged vs baseline
- current anti-collapse: **57 / 54 / 129**
- minimal harmed-tuned: **60 / 49 / 131**

### Failure counts (not_generated / underweighted / collapsed_early / committed_away)
- baseline broad: **74 / 9 / 0 / 10**
- current anti-collapse: **64 / 10 / 0 / 17**
- minimal harmed-tuned: **61 / 7 / 0 / 12**

### Structural diagnostics
- repeated-same-branch expansion rate:
  - baseline: **0.5781**
  - current anti-collapse: **0.4465**
  - minimal harmed-tuned: **0.4575**
- repeated-same-branch expansion count:
  - baseline: **967**
  - current anti-collapse: **621**
  - minimal harmed-tuned: **647**
- shallow preserved alternative count:
  - baseline/current/tuned: **0 / 0 / 0**
- matured alternative count:
  - baseline/current/tuned: **0 / 17 / 9**
- answer-group diversity realized:
  - baseline/current/tuned: **1.2500 / 1.3167 / 1.3250**
- mean branch creation / expand / verify:
  - baseline: **2.6750 / 6.5625 / 0.0083**
  - current anti-collapse: **3.0083 / 5.6625 / 0.7000**
  - minimal harmed-tuned: **2.8875 / 5.6708 / 0.6000**

## D) Harmed-case subtype shift after minimal tuning
For the minimally tuned variant (`anti_collapse_harmed_tuned`) harmed breakdown vs baseline:
- repeat/cap threshold too weak: **26** (from 29)
- anti-collapse blocked good incumbent continuation: **13** (from 10)
- residual late commit after improved tree growth: **7** (from 11)
- alternative matured but still low value: **3** (flat)
- alternative preserved but wrong: **0** (from 1)
- repeat penalty too strong: **0**
- aggregation still underweighted right answer-group: **0**

Interpretation: harms fell overall (54 -> 49) and late-commit harms dropped, while incumbent-blocked harms rose slightly.

## Conservative conclusion
- This minimal harmed-focused follow-up produced a **material harmed reduction vs current anti-collapse in this rerun** (**54 -> 49**) while also improving accuracy and split-survival metrics.
- The anti-collapse structural benefit remains intact (repeated same-branch expansion still much lower than baseline).
- The line is still not solved/final because harmed cases remain non-trivial (49).

## Exact next recommendation
Keep the anti-collapse answer-group refinement as the promoted next line, now with the harmed-focused minimal-tuned variant as the default promoted setting for the next bounded follow-up.

Next bounded step should stay narrow:
1. target the remaining dominant harmed buckets (`repeat_or_cap_threshold_too_weak`, `anti_collapse_blocked_good_incumbent_continuation`),
2. do one additional micro-adjustment pass only,
3. keep the same matrix and fixed diagnostics/reporting surface.
