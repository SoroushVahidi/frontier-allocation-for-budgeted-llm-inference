# Stop-vs-act policy-coupled STOP baseline diagnosis note

## 1) Why matched randomness likely did not improve controller outcomes
- It addressed nuisance rollout noise, but not the semantic mismatch of STOP baseline itself.

## 2) Most plausible STOP-baseline mismatch now
- Default STOP reference is still a proxy subtraction, not an explicit policy-coupled reallocation of saved compute under same context.
- Default mean STOP reference gain: `0.2450`.
- Default mean delta sign-flip rate: `0.1383`.

## 3) Single lightweight strategy
- One-step policy-coupled STOP reallocation comparator (`proxy_policy_coupled_stop_reallocation`).
- ACT: act on current branch now. STOP: forbid current branch for first step and let same policy consume saved compute elsewhere.
