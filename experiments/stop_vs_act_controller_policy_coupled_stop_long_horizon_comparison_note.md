# Stop-vs-act bounded slightly longer-horizon policy-coupled STOP comparison note

## Setup
- Anchor baseline: current default `proxy_best_other_gain`.
- New mode: `proxy_policy_coupled_stop_reallocation_horizon` with h=3.
- Grid: seeds=[41, 42], budgets=[10, 14].

## Results (bounded)
- Default vs heuristic W/L/T (accuracy): `{'wins': 2, 'losses': 2, 'ties': 0, 'total': 4}`.
- Long-horizon vs heuristic W/L/T (accuracy): `{'wins': 0, 'losses': 4, 'ties': 0, 'total': 4}`.
- Long-horizon vs default W/L/T (accuracy): `{'wins': 0, 'losses': 4, 'ties': 0, 'total': 4}`.
- Mean learned-vs-heuristic accuracy margin: default `+0.0080` vs long-horizon `-0.0273`.
- Mean label sign-flip-rate: default `0.1364` vs long-horizon `0.3532`.
- Context only: one-step policy-coupled mean learned-vs-heuristic accuracy margin `-0.0114`.

## Conservative interpretation
- Slight gains are not enough to replace default unless they are robust.
- Current recommendation: `keep_current_default`.
