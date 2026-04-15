# Stop-vs-act bounded policy-coupled STOP baseline comparison note

## Setup
- Anchor baseline: current default `proxy_best_other_gain`.
- New mode: `proxy_policy_coupled_stop_reallocation`.
- Grid: seeds=[31, 32, 33], budgets=[10, 14].

## Results (bounded)
- Default vs heuristic W/L/T (accuracy): `{'wins': 5, 'losses': 1, 'ties': 0, 'total': 6}`.
- Policy-coupled vs heuristic W/L/T (accuracy): `{'wins': 3, 'losses': 2, 'ties': 1, 'total': 6}`.
- Policy-coupled vs default W/L/T (accuracy): `{'wins': 3, 'losses': 3, 'ties': 0, 'total': 6}`.
- Mean learned-vs-heuristic accuracy margin: default `+0.0396` vs policy-coupled `+0.0250`.
- Mean label sign-flip-rate: default `0.1383` vs policy-coupled `0.2362`.

## Conservative interpretation
- If comparator alignment improves but controller outcomes do not, do not replace current default.
- Current recommendation: `keep_current_default`.
