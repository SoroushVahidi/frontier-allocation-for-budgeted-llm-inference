# Stop-vs-act bounded label-refinement comparison note

## What changed
- Single refinement: instability guard band in uncertainty labeling (`instability_guard_band=0.150`).
- Unstable examples are marked uncertain only when their `|delta_mean|` is within the guard band.

## Matched comparison setup
- Seeds: `31,32,33`
- Budgets: `10,14`
- Uncertainty policy fixed: `downweight_nonpositive`
- Episodes per cell: `700`; eval episodes per run: `280`

## Results
- Old label rule vs heuristic: `{'wins': 5, 'losses': 1, 'ties': 0, 'total': 6}`.
- Revised label rule vs heuristic: `{'wins': 4, 'losses': 2, 'ties': 0, 'total': 6}`.
- Revised minus old margin vs heuristic: mean `-0.0030`, std `0.0235`, W/L/T `{'wins': 3, 'losses': 3, 'ties': 0, 'total': 6}`.
- Mean uncertain-rate change: `0.8138 -> 0.4054`.
- Mean ACT-label-rate change: `0.0241 -> 0.0241`.

## Conservative interpretation
- This is a bounded small-grid result only.
- If gain is small/noisy, treat the direction as promising-but-mixed rather than solved.
- If gains plateau, the next bottleneck is likely the local delta proxy quality rather than simple thresholding.

## Recommendation
- **keep stop-vs-act mixed and focus next on the local delta proxy, not further threshold tweaking**.
