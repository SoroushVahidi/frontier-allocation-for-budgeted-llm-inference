# Branch scorer v6 robustness note

- Mean v6 margin vs adaptive_relative_rank: 0.0003
- Std v6 margin vs adaptive_relative_rank: 0.0194
- v6 win rate vs adaptive_relative_rank: 0.511 (23/45)
- Mean v6 margin vs adaptive_learned_branch_score_v5: 0.0020
- Robustly better vs adaptive_relative_rank? no

## Best / worst settings for v6 margin vs adaptive_relative_rank
- Best: seed=7, budget=12, init_branches=3, margin=0.0450
- Worst: seed=3, budget=8, init_branches=3, margin=-0.0333
