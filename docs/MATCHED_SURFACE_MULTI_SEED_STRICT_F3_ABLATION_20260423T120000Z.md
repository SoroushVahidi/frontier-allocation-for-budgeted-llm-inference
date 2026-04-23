# MATCHED_SURFACE_MULTI_SEED_STRICT_F3_ABLATION_20260423T120000Z

## Purpose
Run a materially stronger multi-seed component ablation rerun for strict_f3 on the canonical manuscript-facing matched surface.

## Exact matched surface used
- Canonical matched surface: `outputs/canonical_full_method_ranking_20260421T212948Z`
- This run is a strict rerun of the manuscript-facing ablation surface: `True`.
- Datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Budgets: [4, 6, 8]
- Seeds: [11, 23, 37, 41, 53, 67]
- Subset size per (dataset, seed): 20

## Exact ablation variants used
- `full_method` (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1`, output_repair=True)
- `no_answer_support_aggregation` (`strict_f3_ablation_no_answer_support_aggregation_v1`, output_repair=True)
- `no_anti_collapse` (`strict_f3_ablation_no_anti_collapse_v1`, output_repair=True)
- `no_repeat_expansion_control` (`strict_f3_ablation_no_repeat_expansion_control_v1`, output_repair=True)
- `no_output_repair` (`broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth3_coverage_forced_v1`, output_repair=False)
- `upstream_only_core` (`strict_f3_ablation_upstream_only_core_v1`, output_repair=False)

## Main findings (plain language)
- Full strict_f3 mean accuracy = 0.6231 across 6 seeds.
- Removing `no_answer_support_aggregation`: Δaccuracy=-0.0074, Δabsent_from_tree=+0.0148, Δpresent_not_selected=-0.0120.
- Removing `no_anti_collapse`: Δaccuracy=+0.0083, Δabsent_from_tree=-0.0009, Δpresent_not_selected=-0.0102.
- Removing `no_repeat_expansion_control`: Δaccuracy=+0.0056, Δabsent_from_tree=+0.0213, Δpresent_not_selected=-0.0269.
- Removing `no_output_repair`: Δaccuracy=+0.0000, Δabsent_from_tree=+0.0000, Δpresent_not_selected=+0.0000.
- Removing `upstream_only_core`: Δaccuracy=-0.0028, Δabsent_from_tree=+0.0074, Δpresent_not_selected=-0.0046.

Most clearly supported component (largest accuracy drop when removed): `no_answer_support_aggregation`.

## Mechanism-story recommendation
- If only one component shows robust negative deltas when removed, narrow the manuscript mechanism claim to that component and treat others as mixed/secondary.
- If multiple removals improve or remain near-zero, avoid broad all-component benefit claims on this matched surface.
- Recommended paper-writing action for this run: narrow to a smaller claim unless all major removals are consistently harmful.
