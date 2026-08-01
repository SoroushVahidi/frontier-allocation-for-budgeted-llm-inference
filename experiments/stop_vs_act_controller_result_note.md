# Stop-vs-act lightweight controller result note

This run is a bounded first-pass experiment for fixed-budget branch/controller allocation.

## Label construction rule
- Binary target: ACT if estimated +1 action gain on this branch beats the best alternative branch gain by `gain_margin`; else STOP.
- Estimation: small bounded one-step rollout (`expand` then optional `verify`) over a few local samples.
- Delta proxy: `delta = E[act_gain_here] - best_other_expected_next_gain`.

## Uncertainty filtering/weighting rule
- Mark example uncertain if delta is near zero or rollout delta variance is high.
- Training policy in this run: uncertain examples are retained with reduced sample weight (downweight mode).

## Compact output summary
- Classification: accuracy=0.8827, ROC-AUC=0.9678, Brier=0.0845.
- Learned controller: accuracy=0.5840, avg_best_score=0.7059.
- Heuristic baseline: accuracy=0.5480, avg_best_score=0.7067.
- Uncertainty-threshold-only baseline: accuracy=0.5600, avg_best_score=0.7036.
- Margin learned vs heuristic (accuracy): +0.0360.
- Margin learned vs uncertainty-only (accuracy): +0.0240.

## Conservative interpretation
- This is promising only if the learned controller is consistently better than both baselines across seeds/budgets.
- Treat this as a lightweight feasibility check; no claim of final superiority.
