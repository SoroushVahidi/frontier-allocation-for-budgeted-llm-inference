# External baseline runnability verification note

- run_id: `20260421T190758Z`
- scope: s1 / TALE / L1 mode-A and mode-B adapter paths + BEST-Route + when_solve_when_verify + cascade_routing + mob_majority_of_bests + rest_mcts + openr adjacent import validators
- interpretation: smoke verification only (runnability + blocker-state consistency)

| baseline | mode | runnable | mode_b_status | expected | matches |
|---|---|---:|---|---|---:|
| s1 | mode_a | True | not_requested | not_requested | True |
| s1 | mode_b | True | blocked | blocked | True |
| tale | mode_a | True | not_requested | not_requested | True |
| tale | mode_b | True | blocked | blocked | True |
| l1 | mode_a | True | not_requested | not_requested | True |
| l1 | mode_b | True | blocked | blocked | True |
| best_route | adjacent_import | True | valid | valid | True |
| when_solve_when_verify | adjacent_import | True | valid | valid | True |
| cascade_routing | adjacent_import | True | valid | valid | True |
| mob_majority_of_bests | adjacent_import | True | valid | valid | True |
| rest_mcts | adjacent_import | True | valid | valid | True |
| openr | adjacent_import | True | valid | valid | True |
