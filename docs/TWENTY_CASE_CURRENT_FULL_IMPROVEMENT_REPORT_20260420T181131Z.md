# Twenty-case targeted improvement report (20260420T181131Z)

## Method change
- Old current full runtime method: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`
- Improved method: `broad_diversity_aggregation_strong_v1_anti_collapse_width_depth_challenger_guard_v1`
- Added explicit width-vs-depth guard that interrupts repeated same-family monopolization and forces challenger maturation.
- Added uncertainty-triggered verify allocation on near-tie states (bounded steps).

## Before/after summary on the same 20 cases
- Old correct: 12/20
- Improved correct: 11/20
- Repaired cases (wrong -> correct): 5
- Absent-from-tree: 5 -> 7
- Present-but-not-selected: 3 -> 2
- Repeated same-family expansions (total): 147 -> 149

## Artifacts
- Output bundle: `outputs/twenty_exact_current_full_improvement_eval_20260420T181131Z`
- Per-case table: `outputs/twenty_exact_current_full_improvement_eval_20260420T181131Z/per_case_before_after.csv`

## Conclusion
- This is a bounded controller change focused on search-allocation under fixed budget; conclusions are limited to this fresh 20-case slice.
