# paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3

Run ID: `20260422T175142Z`

## Surface
- `outputs/canonical_full_method_ranking_20260421T212948Z/`
- single matched decision surface for in-house strict variants and fair near-direct externals

## Methods
- requested: strict_gate1_cap_k6, strict_gate1, strict_f2, strict_f3, strict_gate2, external_s1_budget_forcing, external_tale_prompt_budgeting, external_l1_exact, external_l1_max
- runnable: strict_gate1_cap_k6, strict_f2, strict_f3, external_s1_budget_forcing, external_tale_prompt_budgeting, external_l1_exact, external_l1_max
- blocked: strict_gate1, strict_gate2

## Main result snapshot
- strongest fair near-direct external: `external_l1_max`
- recommendation: **paper should center strict_f3**
- reason: strict_f3 remains stronger on the decision surface and is at least as strong as the top fair near-direct external comparator.

## Outputs
- `comparison_table.csv`
- `aggregate_summary.json`
- `per_dataset_summary.csv`
- `per_seed_summary.csv`
- `failure_decomposition.csv`
- `collapse_diagnostics.csv`
- `blocked_or_caveated_methods.csv`
- `decision_recommendation.json`
- figure-ready: `budget_performance_frontier.csv`, `oracle_gap_regret.csv`, `anti_collapse_plot_data.csv`, `failure_decomposition_plot_data.csv`, `decision_table.csv`
