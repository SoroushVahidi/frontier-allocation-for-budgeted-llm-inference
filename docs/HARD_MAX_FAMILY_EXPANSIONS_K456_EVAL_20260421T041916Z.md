# Hard max family expansions K=4/5/6 evaluation (20260421T041916Z)

## Definition
Family expansion cap = no branch family may exceed K expansion actions in a run; once capped, that family is ineligible for further expand actions while verify/commit behavior remains enabled.

## Method and comparator selection
- Selected target strict-phased method: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1`
- Selection note: Reused prior hard-cap target (strict Gate 1) for direct K-sweep comparability; current canonical docs still treat strict Gate 1 as a leading strict-phased candidate.
- Selected best comparator: `reasoning_beam2`
- K values tested: [3, 4, 5, 6]
- Insertion point in code: `GlobalDiversityAggregationController.run` expansion decision path before executing expand.
- Strict phased law preserved: **True**

## Aggregate comparison
| method | accuracy | absent_from_tree | present_not_selected | repeated_same_family_present | gold_in_tree | avg_actions | avg_expansions | avg_verifications | improved | worsened | unchanged | cap_bound_case_count | dominant_family_hit_cap_case_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.0000 | 78 | 22 | 97 | 22 | 11.480 | 10.840 | 0.640 | 0 | 70 | 30 | 0 | 0 |
| strict_target | 0.7000 | 21 | 9 | 77 | 79 | 9.360 | 8.750 | 0.610 | 0 | 0 | 0 | 0 | 0 |
| strict_gate2_reference | 0.7000 | 19 | 11 | 84 | 81 | 9.970 | 9.300 | 0.670 | 21 | 21 | 58 | 0 | 0 |
| strict_target_cap_k3 | 0.6200 | 27 | 11 | 73 | 73 | 10.260 | 4.860 | 5.400 | 17 | 25 | 58 | 68 | 75 |
| strict_target_cap_k4 | 0.6500 | 24 | 11 | 87 | 76 | 11.420 | 6.880 | 4.540 | 18 | 23 | 59 | 77 | 82 |
| strict_target_cap_k5 | 0.6700 | 18 | 15 | 81 | 82 | 9.800 | 7.250 | 2.550 | 22 | 25 | 53 | 58 | 63 |
| strict_target_cap_k6 | 0.6900 | 20 | 11 | 84 | 80 | 10.710 | 9.050 | 1.660 | 21 | 22 | 57 | 66 | 72 |

## Head-to-head K comparisons
| comparison | left_better | right_better | unchanged |
|---|---:|---:|---:|
| strict_target_cap_k4 vs strict_target_cap_k5 | 22 | 24 | 54 |
| strict_target_cap_k5 vs strict_target_cap_k6 | 21 | 23 | 56 |
| strict_target_cap_k4 vs strict_target_cap_k6 | 22 | 26 | 52 |

## Representative helped cases
- olympiadbench / Hothan_OlympiadBench_85: absent_from_tree -> correct
- HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_32: absent_from_tree -> correct
- openai/gsm8k / openai_gsm8k_42: present_not_selected -> correct
- HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_19: absent_from_tree -> correct
- HuggingFaceH4/MATH-500 / HuggingFaceH4_MATH-500_56: absent_from_tree -> correct

## Representative harmed cases

## Dataset-wise breakdown
- HuggingFaceH4/MATH-500: strict_target acc=0.7037, cap_k4/k5/k6 acc=0.6667/0.7037/0.6667, cap_k4 absent=6, cap_k4 present_not_selected=3
- HuggingFaceH4/aime_2024: strict_target acc=0.6316, cap_k4/k5/k6 acc=0.4737/0.6842/0.7895, cap_k4 absent=7, cap_k4 present_not_selected=3
- olympiadbench: strict_target acc=0.7407, cap_k4/k5/k6 acc=0.5926/0.6667/0.7037, cap_k4 absent=7, cap_k4 present_not_selected=4
- openai/gsm8k: strict_target acc=0.7037, cap_k4/k5/k6 acc=0.8148/0.6296/0.6296, cap_k4 absent=4, cap_k4 present_not_selected=1

## Conclusion
Hard cap verdict: **K=6 is better**.
Judgment prioritizes final performance and failure decomposition rather than collapse diagnostics alone.

## Concise summary
- files changed: experiments/controllers.py, experiments/frontier_matrix_core.py, tests/test_hard_max_family_expansions_cap.py, scripts/run_hard_max_family_expansions_eval.py, docs/HARD_MAX_FAMILY_EXPANSIONS_K456_EVAL_20260421T041916Z.md
- commands run: see shell command list in run logs.
- selected target method: broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first__deterministic_output_layer_repair_v1
- selected best comparator: reasoning_beam2
- K values tested: [3, 4, 5, 6]
- output directory: outputs/hard_max_family_expansions_k456_eval_20260421T041916Z
- uncapped vs K4/K5/K6 accuracy: 0.7000 / 0.6500 / 0.6700 / 0.6900
- uncapped vs K4/K5/K6 absent_from_tree: 21 / 24 / 18 / 20
- uncapped vs K4/K5/K6 present_not_selected: 9 / 11 / 15 / 11
- uncapped vs K4/K5/K6 repeated_same_family_present: 77 / 87 / 81 / 84
- uncapped vs K4/K5/K6 gold_in_tree: 79 / 76 / 82 / 80
- uncapped vs K4/K5/K6 improved/worsened/unchanged: 18/23/59 ; 22/25/53 ; 21/22/57
- one-sentence verdict: K=6 is better.