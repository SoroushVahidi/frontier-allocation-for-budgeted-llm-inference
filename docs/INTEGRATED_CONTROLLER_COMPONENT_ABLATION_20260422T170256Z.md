# Integrated controller component ablation (20260422T170256Z)

## Protocol
- Canonical surface: strict-phased default-decision broader matched surface.
- datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024', 'olympiadbench']
- seeds: [11, 23]
- budgets: [6, 8]
- subset size per (dataset, seed): 20

## Variants
- `full_integrated`: runtime=`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control`, output_repair=True
- `no_answer_support`: runtime=`strict_gate1_cap_k6_ablation_no_answer_support_v1`, output_repair=True
- `no_anti_collapse`: runtime=`strict_gate1_cap_k6_ablation_no_anti_collapse_v1`, output_repair=True
- `no_repeat_expansion_control`: runtime=`strict_gate1_cap_k6_ablation_no_repeat_expansion_control_v1`, output_repair=True
- `no_output_repair`: runtime=`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1_fixed_k6_control`, output_repair=False
- `allocation_only_core`: runtime=`strict_gate1_cap_k6_ablation_allocation_only_core_v1`, output_repair=False
- `best_reduced_variant`: selected post-hoc from reduced variants by accuracy, then absent/present failure tie-breaks.

## Aggregate summary

| variant | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | avg_actions | avg_max_family_expansion_share | avg_longest_same_family_run |
|---|---:|---:|---:|---:|---:|---:|---:|
| allocation_only_core | 0.6125 | 94 | 30 | 0 | 5.784 | 0.000 | 0.000 |
| full_integrated | 0.6281 | 86 | 33 | 0 | 5.875 | 0.000 | 0.000 |
| no_answer_support | 0.5844 | 96 | 32 | 13 | 5.897 | 0.000 | 0.000 |
| no_anti_collapse | 0.5906 | 100 | 31 | 0 | 6.037 | 0.000 | 0.000 |
| no_output_repair | 0.6281 | 86 | 33 | 0 | 5.875 | 0.000 | 0.000 |
| no_repeat_expansion_control | 0.6312 | 92 | 26 | 0 | 5.822 | 0.000 | 0.000 |
| best_reduced_variant | 0.6312 | 92 | 26 | 0 | 5.822 | 0.000 | 0.000 |

## Main findings
- Full integrated accuracy: `0.6281`.
- Best reduced variant selected: `no_repeat_expansion_control`.
- Interpret conservatively: this ablation isolates implemented toggles in current code paths; it does not claim causality beyond these operational definitions.

## Artifacts
- `outputs/integrated_controller_component_ablation_20260422T170256Z/manifest.json`
- `outputs/integrated_controller_component_ablation_20260422T170256Z/aggregate_summary.csv`
- `outputs/integrated_controller_component_ablation_20260422T170256Z/aggregate_summary.json`
- `outputs/integrated_controller_component_ablation_20260422T170256Z/per_dataset_metrics.csv`
- `outputs/integrated_controller_component_ablation_20260422T170256Z/per_seed_summary.csv`
- `outputs/integrated_controller_component_ablation_20260422T170256Z/failure_decomposition.csv`
- `outputs/integrated_controller_component_ablation_20260422T170256Z/anti_collapse_diagnostics.csv`
- `outputs/integrated_controller_component_ablation_20260422T170256Z/per_case_results.csv`
