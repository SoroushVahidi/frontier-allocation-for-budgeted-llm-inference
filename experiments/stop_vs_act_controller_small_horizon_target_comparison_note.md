# Stop-vs-act bounded small-horizon ACT-vs-STOP comparison note

## What changed
- New target mode: `counterfactual_act_vs_stop_h2` (small-horizon ACT-vs-STOP).
- Compare horizon value after forcing ACT-here first vs skipping this branch first under the same local context.

## Matched setup
- Seeds: `31,32,33`; budgets: `10,14`; episodes/cell: `700`; eval episodes: `280`.
- Small horizon steps: `2`.

## Results
- Default vs heuristic W/L/T: `{'wins': 4, 'losses': 2, 'ties': 0, 'total': 6}`.
- Failed here-vs-best-other vs heuristic W/L/T: `{'wins': 2, 'losses': 4, 'ties': 0, 'total': 6}`.
- New small-horizon vs heuristic W/L/T: `{'wins': 3, 'losses': 3, 'ties': 0, 'total': 6}`.
- New minus default margin mean/std: `-0.0268` / `0.0367`, W/L/T `{'wins': 2, 'losses': 4, 'ties': 0, 'total': 6}`.
- New minus failed-here-vs-best-other margin mean/std: `0.0018` / `0.0355`, W/L/T `{'wins': 3, 'losses': 3, 'ties': 0, 'total': 6}`.

## Conservative recommendation
- `keep_default`.
- Do not overclaim from this small pass.
