# Stop-vs-act small-horizon ACT-vs-STOP diagnosis note

## 1) Why this is the best next target
- Default target is still a one-step proxy subtraction, and the failed here-vs-best-other target still hinges on alternative-branch matching.
- A small-horizon ACT-vs-STOP target is a cleaner local decision objective: does acting here now improve short-horizon trajectory value vs skipping here now?

## 2) What issue it is intended to fix
- Versus default proxy: reduce static stop-baseline mismatch by simulating both ACT and STOP trajectories.
- Versus failed here-vs-best-other: avoid over-committing to best-other one-step matching and directly model ACT-vs-STOP under same context.

## 3) Exact target used
- Mode: `counterfactual_act_vs_stop_h2` with `small_horizon_steps=2`.
- `delta = E[value_h(force first action on current branch) - value_h(skip current branch on first step)]`.
- Horizon-end value is max snapshot utility over active branches.
