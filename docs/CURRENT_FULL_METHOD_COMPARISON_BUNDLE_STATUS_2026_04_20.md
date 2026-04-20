# Current full method comparison bundle status (2026-04-20)

## 1) Exact current full method name
- Base integrated controller: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1`.
- Current full method evaluated in this bundle: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1` (base controller + deterministic output-layer repair evaluation).

## 2) Comparison methods included
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1` (our_broad_family_variant; origin=new_run).
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1` (our_broad_family_variant; origin=new_run).
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1` (our_latest_full_integrated; origin=new_run).
- `broad_diversity_aggregation_strong_v1` (our_broad_family_variant; origin=new_run).
- `external_tale_prompt_budgeting` (external_baseline; origin=reused).
- `reasoning_beam2` (internal_baseline; origin=reused).
- `reasoning_greedy` (internal_baseline; origin=reused).
- `self_consistency_3` (internal_baseline; origin=reused).
- `adaptive_min_expand_2` (earlier_repo_line; origin=reused).
- `external_s1_budget_forcing` (external_baseline; origin=reused).
- `external_l1_max` (external_baseline; origin=reused).
- `external_l1_exact` (external_baseline; origin=reused).
- `adaptive_min_expand_1` (earlier_repo_line; origin=reused).
- `verifier_guided_search` (internal_baseline; origin=reused).
- `adaptive_min_expand_0` (earlier_repo_line; origin=reused).
- `program_of_thought` (internal_baseline; origin=reused).

## 3) Datasets included
- openai/gsm8k, HuggingFaceH4/MATH-500, HuggingFaceH4/aime_2024.
- Matched seeds: [11, 23]; matched budgets: [4, 6, 8]; subset size per dataset-seed: 20.

## 4) Reused vs newly run
- Reused prior artifact: `outputs/full_method_comparison_bundle/20260419T214335Z/`.
- Newly run methods: broad_diversity_aggregation_strong_v1, broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1, broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1 plus repaired-view method alias `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1`.

## 5) #1 overall under current bundle
- Rank #1: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1` with mean accuracy 0.6167.

## 6) Our current full method overall rank
- `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1__deterministic_output_layer_repair_v1` rank: #3 with mean accuracy 0.6000.

## 7) Where our method wins
- vs `broad_diversity_aggregation_strong_v1`: net margin (other-ours) = -9 (ours_wins=102, other_wins=93).

## 8) Where our method loses
- vs `adaptive_min_expand_0`: net margin (other-ours) = 144 (other_wins=144, ours_wins=0).
- vs `adaptive_min_expand_1`: net margin (other-ours) = 144 (other_wins=144, ours_wins=0).
- vs `adaptive_min_expand_2`: net margin (other-ours) = 144 (other_wins=144, ours_wins=0).
- vs `external_l1_exact`: net margin (other-ours) = 144 (other_wins=144, ours_wins=0).
- vs `external_l1_max`: net margin (other-ours) = 144 (other_wins=144, ours_wins=0).

## 9) Remaining reviewer-defensibility gaps
- External adjacent baselines remain excluded from numeric ranking without direct import package runs.
- This bundle is bounded (3 datasets, 2 seeds, budgets 4/6/8, subset size 20).
- Only top competitors were rerun for prediction-string defeat registry; older reused rows lack prediction fields.

## Defeat registry note
- Top competitor used for compact defeat registry: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_v1`.
- See `outputs/current_full_method_comparison_bundle_20260420/defeat_registry_latest_full_vs_top_competitor.csv`.
