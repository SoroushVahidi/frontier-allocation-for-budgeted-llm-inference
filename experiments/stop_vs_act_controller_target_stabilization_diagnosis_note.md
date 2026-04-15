# Stop-vs-act target stabilization diagnosis note

## 1) Most plausible instability source
- Most plausible bottleneck: high variance from too-few local samples in a noisy ACT/STOP paired comparison, not a new target-family mismatch.

## 2) Why this diagnosis
- Default mean delta std: `0.0906`.
- Default near-margin rate (|delta-gain_margin|<=0.01): `0.0122`.
- Default uncertain rate: `0.8151`.

## 3) One lightweight stabilization strategy
- Keep default target mode (`proxy_best_other_gain`) and add repeated local estimation with averaging.
- For each (state, branch), run K local estimates, average delta_mean, and compute `delta_estimator_std` for reliability.
- Optional training weight: `target_reliability_weight = 1/(1+delta_estimator_std)`.
