# Final held-out controller evaluation note

- Selected best learned method from training job outputs: `adaptive_learned_branch_score_v4`
- Held-out seeds: [29, 31, 37, 41, 43]
- Budgets: [8, 10, 12, 14]
- Initial branches: [3, 5, 7]
- Episodes per setting: 3000

## Main aggregate results
- Mean best-learned accuracy: 0.5734
- Mean adaptive_relative_rank accuracy: 0.5717
- Mean margin vs adaptive_relative_rank: 0.0017
- Win rate vs adaptive_relative_rank: 0.600

## Comparator baselines included
- adaptive_relative_rank (strong heuristic ranker)
- adaptive_score_plus_progress (adaptive heuristic)
- adaptive_raw_score (fixed-policy style score ordering)
- adaptive_eptree_baseline (strong uncertainty/instability heuristic baseline)

## Files
- `final_summary.json`: aggregate headline metrics
- `final_per_setting.csv`: full per-regime table
- `budget_sweep_table.csv`: budget-sweep figure/table data
- `selected_best_learned_model.json`: selection provenance from job 914308 outputs
