# Broader strict phased default decision evaluation (20260421T023506Z)

## Scope
- Broader matched surface over canonical mix (including olympiadbench) rather than the frozen 100-case slice.
- Strict phased law enforced for all strict variants (F1→F2→F3), with controller-driven in-phase ordering.

## Methods compared
- `baseline`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1`
- `strict_f2`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1`
- `strict_f3`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1__deterministic_output_layer_repair_v1`
- `strict_gate1`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1`
- `strict_gate2`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v2_budget_aware_rescue__deterministic_output_layer_repair_v1`
- `broad_bundle_leader`: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1__deterministic_output_layer_repair_v1`

## Optional methods not runnable in this pass
- `strict_gate1_low_marginal_gain_cooldown` skipped: 'broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_low_marginal_gain_cooldown_v1'

## Aggregate comparison

| method | accuracy | absent_from_tree | present_not_selected | repeated-same-family-present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.6500 | 90 | 22 | 302 | 230 | 6.197 | 5.575 | 0.622 | 0 | 0 | 0 |
| strict_f2 | 0.6531 | 85 | 26 | 271 | 235 | 5.959 | 5.487 | 0.472 | 76 | 75 | 169 |
| strict_f3 | 0.6094 | 98 | 27 | 282 | 222 | 6.116 | 5.631 | 0.484 | 70 | 83 | 167 |
| strict_gate1 | 0.6469 | 75 | 38 | 264 | 245 | 5.850 | 5.416 | 0.434 | 78 | 79 | 163 |
| strict_gate2 | 0.5781 | 102 | 33 | 267 | 218 | 5.872 | 5.438 | 0.434 | 67 | 90 | 163 |
| broad_bundle_leader | 0.6219 | 93 | 28 | 301 | 227 | 6.147 | 5.528 | 0.619 | 67 | 76 | 177 |

## Required decision questions
1. Does `strict_f3` beat `strict_f2` on broader matched surface? **False**
2. Does `strict_gate1` beat `strict_f3`? **True**
3. Does `strict_gate2` beat `strict_f3`? **False**
4. Best compromise judged by accuracy, absent-from-tree, repeated-family collapse, and budget cost: see aggregate table + recommendation below.
5. Proposed default promoted model: **strict_f2** (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_coverage_forced_v1__deterministic_output_layer_repair_v1`).

## Dataset-wise results
See `per_dataset_summary.csv` for per-dataset per-method metrics and baseline deltas.

## Final default recommendation
- recommended default model name: **strict_f2**
- one-paragraph justification: On this broader matched surface, `strict_f2` is the strongest conservative compromise by the configured decision rule (maximize accuracy, then reduce absent-from-tree and repeated-same-family collapse, then prefer lower budget cost), while preserving strict phased-law behavior checks in this run.
- whether the recommendation is broad-default or hard-regime-default only: **broad-default**
- one sentence explaining why the other leading candidate(s) were not chosen: The nearest alternatives either trailed on overall broader matched accuracy or required more compute / showed worse failure-mix tradeoffs under the same strict-law constraints.