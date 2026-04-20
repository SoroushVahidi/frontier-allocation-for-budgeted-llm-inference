# Anti-collapse repeat-expansion fine: harmed-case-focused minimal tuning pass (2026-04-20)

## Scope and constraints followed
This pass stayed in the same promoted method line:
- **anti-collapse answer-group-aware allocation with soft repeat-expansion control**.

No redesign was introduced, and the repeat-expansion fine remained enabled.
Only repeat-expansion knobs were minimally tuned.

## A) Harmed-case analysis before tuning
Anchor current-repeat-fine run (`configs/anti_collapse_answer_group_refinement_bounded_eval_20260419.json`) showed:
- accuracy: **0.6583**
- improved / harmed / unchanged vs broad baseline: **57 / 56 / 127**
- harmed subtype breakdown:
  - `anti_collapse_blocked_good_incumbent_continuation`: **14**
  - `repeat_or_cap_threshold_too_weak`: **23**
  - `residual_late_commit_problem_after_improved_tree_growth`: **19**

These were extracted from:
- `outputs/anti_collapse_answer_group_refinement_bounded_eval_20260419/comparison_summary.json`
- `outputs/anti_collapse_answer_group_refinement_bounded_eval_20260419/pairwise_vs_baseline_harmed_cases.json`

## B) Minimal tuning performed (single pass)
A single minimal tuned variant was added:
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`

Only two repeat-expansion knobs changed from the current repeat-fine settings:
- `repeat_expand_penalty_weight`: **0.07 -> 0.065**
- `repeat_expand_override_margin`: **0.10 -> 0.08**

Unchanged in this pass:
- `repeat_expand_family_penalty_weight` (**0.12**)
- `repeat_expand_free_steps` (**3**)

Interpretation intent: make incumbent override slightly easier when incumbent quality still clearly dominates, while keeping family suppression strength unchanged.

## C) Bounded comparison run used for this pass
A matched bounded run including broad baseline, current repeat-fine, and the minimal tuned variant was executed at:
- `outputs/anti_collapse_answer_group_refinement_repeat_fine_min_tuning_pass_20260420_matched/`

Config:
- `configs/anti_collapse_answer_group_refinement_repeat_fine_min_tuning_pass_20260420_matched.json`

## D) Diagnostics (fixed reporting surface)
From `comparison_summary.json` in the matched pass output:

### Accuracy
- broad baseline: **0.6750**
- current repeat-fine: **0.6458**
- minimal tuned repeat-fine: **0.6833**

### Improved / harmed / unchanged vs broad baseline
- current repeat-fine: **46 / 53 / 141**
- minimal tuned repeat-fine: **54 / 52 / 134**

### Repeat expansion metrics
- repeated same-branch expansion count:
  - baseline: **869**
  - current repeat-fine: **615**
  - tuned repeat-fine: **616**
- repeated same-branch expansion rate:
  - baseline: **0.5249**
  - current repeat-fine: **0.4418**
  - tuned repeat-fine: **0.4501**
- repeated same-family expansion count:
  - baseline: **1119**
  - current repeat-fine: **829**
  - tuned repeat-fine: **820**
- repeated same-family expansion rate:
  - baseline: **0.6815**
  - current repeat-fine: **0.5848**
  - tuned repeat-fine: **0.5887**

### Maturity/diversity
- matured alternative count:
  - baseline: **0**
  - current repeat-fine: **13**
  - tuned repeat-fine: **15**
- answer-group diversity realized:
  - baseline: **1.3000**
  - current repeat-fine: **1.2917**
  - tuned repeat-fine: **1.3167**

### Repeat-penalty instrumentation
- repeat_penalty_trigger_count:
  - current repeat-fine: **230**
  - tuned repeat-fine: **231**
- repeat_penalty_override_count:
  - current repeat-fine: **130**
  - tuned repeat-fine: **129**
- repeat_penalty_alternative_selected_count:
  - current repeat-fine: **76**
  - tuned repeat-fine: **84**

### Harmed-case subtype breakdown
- current repeat-fine:
  - `repeat_or_cap_threshold_too_weak`: **27**
  - `anti_collapse_blocked_good_incumbent_continuation`: **16**
  - `residual_late_commit_problem_after_improved_tree_growth`: **10**
- tuned repeat-fine:
  - `repeat_or_cap_threshold_too_weak`: **23**
  - `anti_collapse_blocked_good_incumbent_continuation`: **15**
  - `residual_late_commit_problem_after_improved_tree_growth`: **11**

## Compact harmed-case note (requested)
- **What was tuned:** `repeat_expand_penalty_weight` and `repeat_expand_override_margin` only.
- **Incumbent-blocking harms:** in the matched pass, fell slightly (**16 -> 15**).
- **Repeat-fine still in promoted line:** **yes**; the mechanism remains part of the promoted anti-collapse line in this pass.

## Conservative conclusion
This one minimal pass moved in the intended direction on the primary residual metric, but only modestly:
- incumbent-blocking harms improved slightly,
- total harmed improved slightly,
- maturity/diversity were preserved or improved,
- repeat-expansion fine remained active and structurally effective.

Given the small effect size on incumbent-blocking harms, this should be treated as a **useful but not closing** micro-tune.

## Exact next recommendation
Do one additional micro-pass only if continuing this line:
1. keep `repeat_expand_free_steps` fixed,
2. keep `repeat_expand_family_penalty_weight` fixed,
3. nudge only one knob next (`repeat_expand_override_margin`) in a very small step and rerun the same fixed diagnostics.

If the next micro-pass does not reduce incumbent-blocking harms more materially, freeze this line and avoid further local knob-chasing.
