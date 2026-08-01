# Stop-vs-act slightly longer-horizon policy-coupled STOP diagnosis note

## 1) Why one-step policy-coupled STOP likely failed to improve outcomes
- One-step coupling improved immediate comparator realism but stayed shallow: it did not capture allocator adaptation over subsequent steps.

## 2) Most plausible STOP-baseline bottleneck
- STOP meaning is still too local; preserved compute is represented mostly as immediate diversion, not bounded downstream reuse under the same policy context.

## 3) Why slightly longer-horizon reallocation-aware STOP is next
- Minimal bounded extension to h=3 keeps the pass lightweight while making opportunity cost more faithful.

## 4) Exact target definition used
- ACT path: force one action on current branch now, then run same policy for h=3 steps.
- STOP path: skip current branch now, preserve that action, then run same policy for h=3 steps so compute is naturally reallocated.
- ACT and STOP use paired per-sample RNG seeds and the same active snapshot.
