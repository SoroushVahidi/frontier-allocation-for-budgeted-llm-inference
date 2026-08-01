# Stop-vs-act bounded robustness sweep result note

Bounded robustness sweep over lightweight simulation-only stop-vs-act pipeline.

## Matched sweep setup
- Seeds: `31,32,33,34`
- Budgets: `10,14`
- Uncertainty policies: `none,downweight,filter`
- Dataset episodes per (seed,budget): `700`
- Eval episodes per run: `280`
- Total runs: `24`

## Artifacts
- Per-run metrics: `outputs/stop_vs_act_controller_robustness/20260415T000000Z/robustness_per_run_metrics.csv`
- Aggregate by uncertainty policy: `outputs/stop_vs_act_controller_robustness/20260415T000000Z/robustness_summary_by_uncertainty_policy.csv`
- Aggregate by budget+policy: `outputs/stop_vs_act_controller_robustness/20260415T000000Z/robustness_summary_by_budget_and_uncertainty_policy.csv`
- Global summary JSON: `outputs/stop_vs_act_controller_robustness/20260415T000000Z/robustness_summary.json`

## Required question answers

### 1) Does learned stop-vs-act beat the heuristic baseline consistently?
- Overall win/loss/tie vs heuristic across all runs: `{'wins': 13, 'losses': 11, 'ties': 0, 'total': 24}`.
- Interpretation: this is not treated as consistent unless wins clearly dominate losses across seeds and budgets.

### 2) Does uncertainty-aware training help?
- Compare `downweight` / `filter` against `none` by their mean learned-vs-heuristic accuracy margin and win/loss counts.
- `downweight` minus `none` mean learned-vs-heuristic margin: `+0.0031` (policy mean=+0.0103, none mean=+0.0071).
- `filter` minus `none` mean learned-vs-heuristic margin: `-0.0174` (policy mean=-0.0103, none mean=+0.0071).

### 3) Is one uncertainty policy clearly better?
- Top-counts on learned accuracy across matched (seed,budget) cells: `{'cells': 8, 'policy_top_counts': {'none': 4, 'downweight': 4, 'filter': 1}, 'cells_with_top_tie': 1}`.
- Highest mean learned-vs-heuristic margin in this bounded sweep: `downweight`.
- Conservative rule: if top counts are split or margins are close, treat as mixed rather than clear winner.

### 4) Do gains persist across multiple budgets?
- Budget `10` -> downweight: mean_margin=+0.0143, W/L=2/2, filter: mean_margin=-0.0205, W/L=2/2, none: mean_margin=+0.0018, W/L=2/2.
- Budget `14` -> downweight: mean_margin=+0.0063, W/L=2/2, filter: mean_margin=+0.0000, W/L=2/2, none: mean_margin=+0.0125, W/L=3/1.

### 5) Are results promising, mixed, or weak?
- Label as **promising** only if learned beats baselines with clear margin and low seed sensitivity.
- Label as **mixed** if wins exist but losses/variance remain material.
- Label as **weak** if losses dominate or effects are near-zero/noisy.
- **Observed label in this bounded sweep: mixed.** Wins exist, but losses are still frequent versus the heuristic baseline and variance is non-trivial.

## Failure slices / instability patterns
- seed=31, budget=10, policy=filter, margin_vs_heuristic=-0.0179, margin_vs_uncertainty=+0.0143.
- seed=32, budget=10, policy=downweight, margin_vs_heuristic=-0.0107, margin_vs_uncertainty=+0.0607.
- seed=32, budget=10, policy=filter, margin_vs_heuristic=-0.0857, margin_vs_uncertainty=-0.0107.
- seed=32, budget=10, policy=none, margin_vs_heuristic=-0.0286, margin_vs_uncertainty=+0.0393.
- seed=34, budget=10, policy=downweight, margin_vs_heuristic=-0.0036, margin_vs_uncertainty=+0.0429.
- seed=34, budget=10, policy=none, margin_vs_heuristic=-0.0393, margin_vs_uncertainty=+0.0036.
- seed=32, budget=14, policy=downweight, margin_vs_heuristic=-0.0036, margin_vs_uncertainty=+0.0429.
- seed=32, budget=14, policy=filter, margin_vs_heuristic=-0.0214, margin_vs_uncertainty=+0.0250.
- seed=33, budget=14, policy=filter, margin_vs_heuristic=+0.0643, margin_vs_uncertainty=-0.0071.
- seed=33, budget=14, policy=none, margin_vs_heuristic=+0.0429, margin_vs_uncertainty=-0.0179.
- seed=34, budget=14, policy=downweight, margin_vs_heuristic=-0.0536, margin_vs_uncertainty=-0.0786.
- seed=34, budget=14, policy=filter, margin_vs_heuristic=-0.0500, margin_vs_uncertainty=-0.0643.
- ... plus 1 additional negative-margin runs (see CSV).

## Conservative recommendation
- Use aggregate + win/loss evidence as the deciding signal, not a single best run.
- If mixed, keep this direction but avoid broad expansion until label/proxy robustness improves.
- If weak, revise label/training setup before deeper integration.
- **Current recommendation:** keep but treat as mixed (do not promote to stronger canonical direction yet); prioritize supervision-target refinement and uncertainty-policy calibration before deeper frontier-allocation integration.
