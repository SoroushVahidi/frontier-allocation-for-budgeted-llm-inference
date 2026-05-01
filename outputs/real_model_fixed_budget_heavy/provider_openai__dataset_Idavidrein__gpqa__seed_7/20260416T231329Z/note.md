# Real-model fixed-budget pilot note

- Run id: `20260416T231329Z`
- Providers: openai
- Datasets: Idavidrein/gpqa
- Subset size per provider/dataset: 60
- Fixed budget (max actions/problem): 8
- Min expansions before prune: 0
- Learned scorer path preference: `outputs/branch_scorer_v3/models/adaptive_learned_branch_score_v4.json`

## Provider/dataset summary
- openai | Idavidrein/gpqa | adaptive_relative_rank: acc=0.050, avg_actions=1.77, budget_exhaustion=0.03, avg_calibrated_z=-0.362417
- openai | Idavidrein/gpqa | adaptive_score_plus_progress: acc=0.050, avg_actions=1.75, budget_exhaustion=0.02, avg_calibrated_z=-0.331872
- openai | Idavidrein/gpqa | adaptive_learned_branch_score_v4: acc=0.067, avg_actions=1.67, budget_exhaustion=0.02, avg_calibrated_z=-0.373636
- openai | Idavidrein/gpqa | best_of_n: acc=0.200, avg_actions=7.68, budget_exhaustion=0.83, avg_calibrated_z=n/a

## Pilot signal
- This real-API pilot is intentionally small; use trends as directional only, not benchmark claims.
- Mean method accuracy across successful rows: 0.092

## Calibration stats (provider-specific mean/std)
- openai: mean=0.4307, std=0.2514, n_score_samples=465

## Ranking comparison (raw accuracy vs calibrated z-score)
- openai | Idavidrein/gpqa: raw_top=best_of_n, calibrated_top=adaptive_score_plus_progress, ranking_changed=True

## Diagnostics included
- branch diversity / collapse from unique branch ids touched per example
- branch-score variance across action-trace score updates
- budget usage over time from remaining_budget in action trace
- semantic redundancy proxy as mean token-overlap (Jaccard) between recorded steps/predictions
- provider/method failure reasons via lightweight error categorization
