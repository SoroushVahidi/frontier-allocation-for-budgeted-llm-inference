# Stop-vs-act bounded target-stabilization comparison note

## Setup
- Anchor baseline: current default `proxy_best_other_gain` target.
- Single new option: `repeated_local_averaging` stabilization with optional reliability weighting.
- Grid: seeds=[31, 32, 33], budgets=[10, 14].

## Results (bounded)
- Default vs heuristic W/L/T (accuracy margin): `{'wins': 5, 'losses': 1, 'ties': 0, 'total': 6}`.
- Stabilized vs heuristic W/L/T (accuracy margin): `{'wins': 5, 'losses': 1, 'ties': 0, 'total': 6}`.
- Stabilized vs default W/L/T (accuracy margin): `{'wins': 2, 'losses': 4, 'ties': 0, 'total': 6}`.
- Mean learned-vs-heuristic accuracy margin: default `+0.0396` vs stabilized `+0.0302`.
- Margin std: default `0.0423` vs stabilized `0.0481`.

## Conservative interpretation
- Treat this as a bounded local signal only.
- If mean/stability gains are small or mixed, do not overclaim; keep default anchor and continue refinement.
- Current recommendation from this pass: `keep_current_default`.
