# High-budget fixed-K sweep evaluation (20260421T164449Z)

## Scope
Focused sweep over fixed same-family hard caps under the strict-phased Gate-1 controller, targeting only higher budgets.
Controller behavior is held constant; only the hard same-family cap K changes.

## Control/default
- control alias: `strict_gate1_cap_k6`
- control method: `broad_diversity_aggregation_strong_v1_anti_collapse_answer_group_refinement_repeat_expansion_fine_incumbent_guard_tuned_v1_hard_early_root_depth2_then_gate_v1_optimistic_collapse_first_hard_max_family_expansions_cap_k6_v1__deterministic_output_layer_repair_v1`

## Evaluation surface
- datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'olympiadbench']
- subset size per dataset/seed: 8
- seeds: [13, 37, 101]
- budgets (high-only): [12, 14, 16, 18, 20]
- fixed K values: [4, 6, 8, 10, 12]
- total evaluated rows: 360

## Overall comparison
| K | accuracy | absent_from_tree | present_not_selected | repeated_same_family_present | avg_longest_same_family_run | avg_max_family_share | avg_actions | avg_expansions | avg_verifications | improved_vs_k6 | worsened_vs_k6 | unchanged_vs_k6 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 0.7167 | 58 | 44 | 298 | 4.228 | 0.551 | 12.117 | 9.097 | 3.019 | 0 | 0 | 360 |
| 8 | 0.6944 | 54 | 56 | 300 | 5.481 | 0.637 | 11.039 | 10.019 | 1.019 | 72 | 80 | 208 |
| 10 | 0.6556 | 66 | 58 | 304 | 6.325 | 0.693 | 11.036 | 10.311 | 0.725 | 72 | 94 | 194 |
| 12 | 0.6500 | 74 | 52 | 289 | 6.611 | 0.727 | 10.194 | 9.761 | 0.433 | 71 | 95 | 194 |
| 4 | 0.6250 | 79 | 56 | 298 | 2.856 | 0.522 | 12.608 | 6.642 | 5.967 | 71 | 104 | 185 |

## Best K by budget
| budget | best_k |
|---:|---:|
| 12 | 6 |
| 14 | 8 |
| 16 | 10 |
| 18 | 6 |
| 20 | 8 |

## Interpretation
- On this evaluated high-budget surface, overall best fixed cap is **K=6**.
- Winner sequence by budget: [6, 8, 10, 6, 8]
- Plateau check: assess whether gains past K=6 are small/inconsistent across budgets using per-budget table.
- Collapse check: use repeated_same_family_present, avg_longest_same_family_run, and avg_max_family_share to verify whether larger K reintroduces concentration.
- Recommendation is scoped to this evaluated high-budget surface and current strict-phased repository phase.

## Artifacts
- output directory: `outputs/high_budget_k_sweep_eval_20260421T164449Z`
- machine-readable aggregate summary: `aggregate_summary.json`
- per-budget summary: `per_budget_summary.json` and `per_budget_summary_table.csv`
- per-dataset summary: `per_dataset_summary.json`
- head-to-head summaries vs K=6: `head_to_head_vs_k6.json`
- high-budget recommendation artifact: `recommended_k_for_high_budget_regime.json`