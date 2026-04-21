# CANONICAL FULL METHOD RANKING (20260421T212948Z)

## Purpose
Create one canonical full-method leaderboard that includes the latest promoted default `strict_gate1_cap_k6` and major comparison methods on one matched evaluation surface.

## Evaluation contract
- Datasets: openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024
- Seeds: 11, 23
- Budgets: 4, 6, 8
- Subset size per dataset-seed: 20
- Contract basis: current broad comparison bundle contract (2026-04-20), extended to include strict-phased finalists and latest promoted strict method.

## Included methods
- `adaptive_min_expand_0`
- `adaptive_min_expand_1`
- `adaptive_min_expand_2`
- `broad_diversity_aggregation_strong_v1`
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1`
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1`
- `external_l1_exact`
- `external_l1_max`
- `external_s1_budget_forcing`
- `external_tale_prompt_budgeting`
- `program_of_thought`
- `reasoning_beam2`
- `reasoning_greedy`
- `self_consistency_3`
- `strict_f2`
- `strict_f3`
- `strict_gate1_cap_k6`
- `verifier_guided_search`

## Excluded methods
- `strict_gate1`: method_not_in_current_build_frontier_strategies (runtime key missing: broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first)
- `strict_gate2`: method_not_in_current_build_frontier_strategies (runtime key missing: broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v2_budget_aware_rescue)

## Aggregate overall ranking
Top 10:

- #1 `strict_f3` acc=0.6583 actions=5.222
- #2 `strict_gate1_cap_k6` acc=0.6528 actions=5.297
- #3 `broad_diversity_aggregation_strong_v1` acc=0.6361 actions=5.689
- #4 `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1` acc=0.6333 actions=5.433
- #5 `strict_f2` acc=0.6222 actions=5.456
- #6 `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1` acc=0.6139 actions=5.594
- #7 `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1` acc=0.6028 actions=5.367
- #8 `reasoning_beam2` acc=0.5861 actions=3.933
- #9 `self_consistency_3` acc=0.5667 actions=5.889
- #10 `adaptive_min_expand_2` acc=0.5583 actions=3.475

## Dataset-wise leaders
- openai/gsm8k: #1 `strict_gate1_cap_k6` acc=0.6750
- HuggingFaceH4/MATH-500: #1 `strict_gate1_cap_k6` acc=0.6833
- HuggingFaceH4/aime_2024: #1 `strict_f3` acc=0.7417

## Latest promoted method: exact rank and nearest competitors
- `strict_gate1_cap_k6` rank: **#2**
- Overall #1 method: **`strict_f3`**
- Strongest direct adversary by closest overall accuracy: **`strict_f3`** (rank #1).

## Head-to-head results for `strict_gate1_cap_k6`

- vs `program_of_thought`: improved=235, worsened=0, unchanged=125, net=235
- vs `adaptive_min_expand_0`: improved=173, worsened=26, unchanged=161, net=147
- vs `verifier_guided_search`: improved=131, worsened=46, unchanged=183, net=85
- vs `external_l1_exact`: improved=131, worsened=49, unchanged=180, net=82
- vs `external_s1_budget_forcing`: improved=133, worsened=54, unchanged=173, net=79
- vs `adaptive_min_expand_1`: improved=124, worsened=51, unchanged=185, net=73
- vs `reasoning_greedy`: improved=134, worsened=64, unchanged=162, net=70
- vs `external_tale_prompt_budgeting`: improved=117, worsened=54, unchanged=189, net=63
- vs `external_l1_max`: improved=111, worsened=55, unchanged=194, net=56
- vs `adaptive_min_expand_2`: improved=102, worsened=68, unchanged=190, net=34

## Cost/performance interpretation
Ranking is accuracy-first with cost/failure tie-breakers. This report distinguishes the promoted default from the overall leader instead of assuming they are identical.

## Defensibility gaps
- Some strict aliases from current canonical docs are excluded if their exact runtime keys are absent in current `build_frontier_strategies`.
- This remains a bounded matched surface and not universal performance.

## Safe manuscript summary
On this canonical matched contract, the overall leader is `strict_f3`, while the current promoted default `strict_gate1_cap_k6` ranks #2. Therefore the promoted default is not the overall leader on this surface.

## Exact artifact paths
- `outputs/canonical_full_method_ranking_20260421T212948Z/overall_ranking.csv`
- `outputs/canonical_full_method_ranking_20260421T212948Z/dataset_wise_ranking.csv`
- `outputs/canonical_full_method_ranking_20260421T212948Z/strict_gate1_cap_k6_head_to_head.csv`
- `outputs/canonical_full_method_ranking_20260421T212948Z/excluded_methods.csv`
- `outputs/canonical_full_method_ranking_20260421T212948Z/manifest.json`
