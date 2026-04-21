# Hard max family expansions evaluation (20260421T040333Z)

## Definition
Family expansion cap = no branch family may exceed K expansion actions in a run; once capped, that family is ineligible for further expand actions while verify/commit behavior remains enabled.

## Method and comparator selection
- Selected target strict-phased method: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1`
- Selection note: Picked strict_gate1 explicitly from latest strict-phased docs because it outperformed strict_gate2 on the broader strict-phased default decision report.
- Selected best comparator: `reasoning_beam2`
- K values tested: [2, 3, 4]
- Insertion point in code: `GlobalDiversityAggregationController.run` expansion decision path before executing expand.
- Strict phased law preserved: **True**

## Aggregate comparison
| method | accuracy | absent_from_tree | present_not_selected | repeated_same_family_present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged | cap_bound_case_count | dominant_family_hit_cap_case_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.6100 | 30 | 9 | 96 | 70 | 10.880 | 9.990 | 0.890 | 0 | 0 | 0 | 0 | 0 |
| strict_target | 0.6000 | 19 | 21 | 86 | 81 | 9.720 | 9.140 | 0.580 | 24 | 25 | 51 | 0 | 0 |
| strict_gate2_reference | 0.6500 | 28 | 7 | 87 | 72 | 10.770 | 10.090 | 0.680 | 20 | 16 | 64 | 0 | 0 |
| strict_target_cap_k2 | 0.5500 | 35 | 10 | 30 | 65 | 12.520 | 3.760 | 8.760 | 22 | 28 | 50 | 88 | 88 |
| strict_target_cap_k3 | 0.6200 | 29 | 9 | 84 | 71 | 11.500 | 5.300 | 6.200 | 25 | 24 | 51 | 79 | 86 |
| strict_target_cap_k4 | 0.6800 | 17 | 15 | 86 | 83 | 11.910 | 6.890 | 5.020 | 24 | 17 | 59 | 80 | 81 |
| strict_gate2_cap_k3 | 0.6200 | 31 | 7 | 78 | 69 | 12.100 | 5.420 | 6.680 | 24 | 23 | 53 | 83 | 88 |

## Representative helped cases
- olympiadbench / Hothan_OlympiadBench_51: present_not_selected -> correct
- openai/gsm8k / openai_gsm8k_94: absent_from_tree -> correct
- openai/gsm8k / openai_gsm8k_28: absent_from_tree -> correct
- olympiadbench / Hothan_OlympiadBench_82: absent_from_tree -> correct
- olympiadbench / Hothan_OlympiadBench_17: absent_from_tree -> correct

## Representative harmed cases
- HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_43: correct -> absent_from_tree
- openai/gsm8k / openai_gsm8k_35: correct -> present_not_selected
- olympiadbench / Hothan_OlympiadBench_34: correct -> absent_from_tree
- HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_92: correct -> present_not_selected
- HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_74: correct -> absent_from_tree

## Dataset-wise breakdown
- HuggingFaceH4/MATH-500: strict_target acc=0.6176, cap_k3 acc=0.6176, cap_k3 absent=11, cap_k3 present_not_selected=2
- olympiadbench: strict_target acc=0.5758, cap_k3 acc=0.6061, cap_k3 absent=11, cap_k3 present_not_selected=2
- openai/gsm8k: strict_target acc=0.6061, cap_k3 acc=0.6364, cap_k3 absent=7, cap_k3 present_not_selected=5

## Conclusion
Hard cap verdict: **promising**.
Judgment prioritizes final performance and failure decomposition rather than collapse diagnostics alone.

## Concise summary
- files changed: experiments/controllers.py, experiments/frontier_matrix_core.py, tests/test_hard_max_family_expansions_cap.py, scripts/run_hard_max_family_expansions_eval.py, docs/HARD_MAX_FAMILY_EXPANSIONS_EVAL_20260421T040333Z.md
- commands run: see shell command list in run logs.
- selected target method: broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1
- selected best comparator: reasoning_beam2
- K values tested: [2, 3, 4]
- output directory: outputs/hard_max_family_expansions_eval_20260421T040333Z
- baseline vs capped(K=3) absent_from_tree: 30 vs 29
- baseline vs capped(K=3) present_not_selected: 9 vs 9
- baseline vs capped(K=3) repeated_same_family_present: 96 vs 84
- baseline vs capped(K=3) gold_in_tree: 70 vs 71
- baseline vs capped(K=3) improved/worsened/unchanged: 25/24/51
- one-sentence verdict: hard family-expansion cap looks promising in this run.