# Stop-vs-act bounded counterfactual-target comparison note

## What changed
- Single target revision: switch from `proxy_best_other_gain` to `counterfactual_here_vs_best_other`.
- Old: `E[gain_here] - best_other_expected_next_gain`.
- Revised: `E[gain_here - gain_best_other_one_step]` via bounded local rollouts.

## Matched comparison setup
- Seeds: `31,32,33`
- Budgets: `10,14`
- Episodes per cell: `700`; eval episodes: `280`
- Uncertainty policy fixed: `downweight_nonpositive`

## Results
- Old target vs heuristic W/L/T: `{'wins': 4, 'losses': 2, 'ties': 0, 'total': 6}`.
- Revised target vs heuristic W/L/T: `{'wins': 2, 'losses': 4, 'ties': 0, 'total': 6}`.
- Revised-minus-old margin vs heuristic: mean `-0.0286`, std `0.0523`, W/L/T `{'wins': 2, 'losses': 4, 'ties': 0, 'total': 6}`.
- Learned ACT usage (primary actions): old `7.158` vs revised `6.893`.

## Conservative recommendation
- `do_not_replace_yet`.
- Do not overclaim from this bounded pass; use as a target-quality signal only.
