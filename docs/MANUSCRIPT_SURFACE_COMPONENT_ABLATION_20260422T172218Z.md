# Manuscript-surface component ablation (20260422T172218Z)

## Surface and method lock
- Canonical manuscript-facing method lock: `strict_f3`.
- Canonical fairness/matched surface: `outputs/canonical_full_method_ranking_20260421T212948Z/`.
- Datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Seeds: [11, 23]
- Budgets: [4, 6, 8]
- Subset size per (dataset, seed): 20

## Component-to-code mapping
- answer-support aggregation: `experiments/controllers.py` (`_group_support_summary`, `_final_prediction_from_groups`; weights `answer_support_weight`, `value_weight`).
- anti-collapse: `experiments/controllers.py` (`_anti_collapse_priority_adjustments`, `enable_anti_collapse_answer_group_refinement`).
- repeat-expansion moderation: `experiments/controllers.py` (`repeat_expand_*`, low-marginal-gain cooldown signals).
- bounded output repair: `experiments/output_layer_repair.py` (`choose_repair_answer(..., enable_rescue=...)`).

## Aggregate summary

| variant | accuracy | absent_from_tree | present_not_selected | output_layer_mismatch | avg_actions |
|---|---:|---:|---:|---:|---:|
| full_method | 0.6250 | 97 | 38 | 1 | 5.319 |
| no_answer_support_aggregation | 0.6222 | 106 | 27 | 11 | 5.264 |
| no_anti_collapse | 0.6694 | 92 | 27 | 0 | 5.281 |
| no_output_repair | 0.6222 | 97 | 39 | 0 | 5.319 |
| no_repeat_expansion_control | 0.5833 | 123 | 27 | 0 | 5.275 |
| upstream_only_core | 0.6694 | 94 | 25 | 0 | 5.403 |
| strongest_reduced_variant | 0.6694 | 92 | 27 | 0 | 5.281 |

## Explicit answers
- Component contributing most to final accuracy (drop vs full): `no_repeat_expansion_control`.
- Component most reducing `absent_from_tree` failures: `no_repeat_expansion_control`.
- Output repair appears secondary on this canonical surface: `True`.
- Manuscript claims support status: component-level support is partial and variant-dependent; avoid overclaiming universal gains from every component.

## Artifacts
- `outputs/manuscript_surface_component_ablation_20260422T172218Z/aggregate_summary.csv`
- `outputs/manuscript_surface_component_ablation_20260422T172218Z/per_dataset_summary.csv`
- `outputs/manuscript_surface_component_ablation_20260422T172218Z/per_seed_summary.csv`
- `outputs/manuscript_surface_component_ablation_20260422T172218Z/failure_decomposition.csv`
- `outputs/manuscript_surface_component_ablation_20260422T172218Z/compute_allocation_diagnostics.csv`
- `outputs/manuscript_surface_component_ablation_20260422T172218Z/per_case_results.csv`
