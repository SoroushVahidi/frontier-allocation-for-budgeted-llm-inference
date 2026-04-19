# Full method comparison bundle status note

- run_id: `20260419T214335Z`
- generated_utc: `2026-04-19T21:43:41.194573+00:00`

## Methods actually compared numerically
- `adaptive_min_expand_0`
- `adaptive_min_expand_1`
- `adaptive_min_expand_2`
- `external_l1_exact`
- `external_l1_max`
- `external_s1_budget_forcing`
- `external_tale_prompt_budgeting`
- `program_of_thought`
- `reasoning_beam2`
- `reasoning_greedy`
- `self_consistency_3`
- `verifier_guided_search`

## Methods not fully compared and why
- Adjacent import-validated only baselines are tracked in status table and not numerically ranked without import artifacts:
  best_route, when_solve_when_verify, cascade_routing, mob_majority_of_bests, rest_mcts, openr.
- Blocked baseline: `compute_optimal_tts`.

## Primary ranking rule
- Rank by mean_accuracy over all matched dataset/seed/budget rows.
- Tie-break: Lower mean_avg_actions, then higher mean_coverage, then lexical method name.

## Compact aggregate ranking

| rank | method | family | mean_accuracy | mean_avg_actions | status |
|---|---|---|---|---|---|
| 1 | external_tale_prompt_budgeting | external_baseline | 0.5305555555555556 | 1.9166666666666667 | runnable_direct |
| 2 | reasoning_beam2 | internal_baseline | 0.5027777777777778 | 4.055555555555555 | runnable_direct |
| 3 | reasoning_greedy | internal_baseline | 0.49166666666666664 | 2.1305555555555555 | runnable_direct |
| 4 | self_consistency_3 | internal_baseline | 0.48055555555555557 | 5.927777777777778 | runnable_direct |
| 5 | adaptive_min_expand_2 | earlier_repo_line | 0.4694444444444444 | 3.630555555555555 | runnable_direct |
| 6 | external_s1_budget_forcing | external_baseline | 0.4555555555555555 | 3.2972222222222225 | runnable_direct |
| 7 | external_l1_max | external_baseline | 0.44999999999999996 | 1.927777777777778 | runnable_direct |
| 8 | external_l1_exact | external_baseline | 0.4222222222222222 | 2.25 | runnable_direct |
| 9 | adaptive_min_expand_1 | our_current_main | 0.35555555555555557 | 3.386111111111111 | runnable_direct |
| 10 | verifier_guided_search | internal_baseline | 0.26944444444444443 | 5.333333333333333 | runnable_direct |

## Fairness assumptions
- MODE A adapters are included as runnable fair baselines.
- MODE B and official full reproductions are not claimed here.

## Strongest wins/losses for our method
- Biggest losses (other beats ours):
  - `external_tale_prompt_budgeting`: net 63 (other_wins=131, ours_wins=68).
  - `reasoning_beam2`: net 53 (other_wins=116, ours_wins=63).
  - `reasoning_greedy`: net 49 (other_wins=112, ours_wins=63).
  - `self_consistency_3`: net 45 (other_wins=116, ours_wins=71).
  - `adaptive_min_expand_2`: net 41 (other_wins=115, ours_wins=74).
- Biggest wins (ours beats other):
  - `program_of_thought`: net -122 (other_wins=4, ours_wins=126).
  - `adaptive_min_expand_0`: net -47 (other_wins=49, ours_wins=96).
  - `verifier_guided_search`: net -31 (other_wins=58, ours_wins=89).
  - `external_l1_exact`: net 24 (other_wins=90, ours_wins=66).
  - `external_l1_max`: net 34 (other_wins=92, ours_wins=58).
