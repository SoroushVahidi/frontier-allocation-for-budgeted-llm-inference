# Stop-vs-act bounded matched-comparator comparison note

## Setup
- Anchor baseline: current default `proxy_best_other_gain`.
- New mode: `counterfactual_act_vs_stop_h2_matched` with paired RNG ACT/STOP rollouts.
- Grid: seeds=[31, 32, 33], budgets=[10, 14].

## Results (bounded)
- Default vs heuristic W/L/T (accuracy): `{'wins': 5, 'losses': 1, 'ties': 0, 'total': 6}`.
- Matched comparator vs heuristic W/L/T (accuracy): `{'wins': 3, 'losses': 3, 'ties': 0, 'total': 6}`.
- Matched comparator vs default W/L/T (accuracy): `{'wins': 3, 'losses': 3, 'ties': 0, 'total': 6}`.
- Mean learned-vs-heuristic accuracy margin: default `+0.0396` vs matched `+0.0187`.
- Mean sign-flip-rate: default `0.1383` vs matched `0.3161`.

## Conservative interpretation
- Treat this as a small matched signal only.
- If local comparator stability improves but controller metrics do not, do not promote replacement.
- Current recommendation: `keep_current_default`.
