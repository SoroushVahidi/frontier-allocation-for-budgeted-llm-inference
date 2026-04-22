# Robustness pass: budget stability and failure mechanisms

- Budget sweep bundle: `outputs/budget_sweep_robustness/20260422T042642Z/`
- Multi-seed stability bundle: `outputs/multi_seed_stability/20260422T042646Z/`
- Failure-mechanism robustness bundle: `outputs/failure_mechanism_robustness/20260422T042649Z/`

## 1) Does strict_f3 remain strong across budgets?
- Yes on the canonical matched budgets `[4, 6, 8]` and datasets `['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']`.
- Budget 4: strict_f3=0.641667, external_l1_max=0.466667, delta=0.175000.
- Budget 6: strict_f3=0.658333, external_l1_max=0.525000, delta=0.133333.
- Budget 8: strict_f3=0.675000, external_l1_max=0.500000, delta=0.175000.
- Mean delta across budget points: 0.161111.

## 2) Is strongest fair comparison stable across repeated runs?
- Stability is evaluated as repeated evaluation-seed variation on existing canonical seeds (not training-seed variation).
- strict_f3: mean=0.658333, std=0.035355, min=0.633333, max=0.683333, seeds=2.
- external_l1_max: mean=0.497222, std=0.058926, min=0.455556, max=0.538889, seeds=2.
- Note: only two canonical seeds are currently available for strict_f3 and external_l1_max in the anchored surface; this limits spread-estimation depth.

## 3) Do dominant failure modes stay the same across budgets?
- Overall strict-loss count (strict_f3 wrong & external_l1_max correct): 56.
- Overall dominant mechanism: absent_from_tree.
- Overall absent_from_tree rate: 0.857143.
- Overall present_not_selected rate: 0.142857.
- Budget 4: absent_from_tree=0.812500, present_not_selected=0.187500, losses=16.
- Budget 6: absent_from_tree=0.954545, present_not_selected=0.045455, losses=22.
- Budget 8: absent_from_tree=0.777778, present_not_selected=0.222222, losses=18.

## 4) Exact manuscript-safe wording
- "Across the canonical matched budget points (4, 6, 8), strict_f3 consistently outperforms the strongest fair external baseline external_l1_max on the shared near-direct evaluation substrate."
- "Across available repeated evaluation seeds on the canonical surface, strict_f3 retains a positive mean-accuracy margin over external_l1_max; we report mean/spread and do not claim formal significance from this small seed count."
- "Failure analysis against external_l1_max remains dominated by absent_from_tree, with present_not_selected as a secondary mechanism, and this pattern persists across budget slices."

## Main-paper vs appendix readiness
- Main-paper ready now: budget curve table (`budget_curve_table.csv` + `head_to_head_budget_table.csv`), stability table (`seed_stability_table.csv`), failure-mechanism table (`failure_mechanism_by_budget.csv`).
- Appendix-ready: per-dataset breakdown tables and additional caveat material (`budget_curve_by_dataset.csv`, `seed_stability_by_dataset.csv`, `failure_mechanism_by_dataset.csv`, `feature_summary.json`).

## Dataset coverage note
- Requested anchors included: gsm8k and MATH-500.
- Science-anchor gpqa_diamond is not currently present in the canonical matched-surface artifact used for fairness-locked comparisons; this pass therefore uses the strongest runnable canonical set and records that limitation explicitly.
