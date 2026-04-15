# Stop-vs-act local-target diagnosis note (counterfactual revision pass)

## 1) Most likely weak aspect of the current local proxy
- The current target uses `best_other_expected_next_gain` as a fixed subtraction term while the ACT side is sampled through local rollout.
- This asymmetry likely misaligns labels when the best alternative branch's realized one-step gain differs from its expectation.

## 2) Main issue class
- Primary: **alternative-branch proxy mismatch** (and related redundancy blindness), not just threshold or uncertainty-band tuning.
- Pairwise old→new label change rate across diagnosis grid: `0.3434`.
- Mean old ACT→new STOP rate: `0.0067`; old STOP→new ACT: `0.3367`.

## 3) One lightweight counterfactual target revision
- **Revised target**: `delta = E[gain_after_one_step_here - gain_after_one_step_best_other]`.
- This keeps the same one-step bounded simulation budget and infrastructure, but explicitly compares compute-here vs compute-elsewhere under matched local rollouts.
