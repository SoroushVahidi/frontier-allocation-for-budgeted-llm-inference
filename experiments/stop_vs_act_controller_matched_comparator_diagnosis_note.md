# Stop-vs-act matched-comparator diagnosis note

## 1) Why stabilization likely failed to move controller outcomes
- Repeated averaging reduced target noise but kept the same local comparison object; it did not fix ACT-vs-STOP comparator mismatch.

## 2) Most plausible mismatch bottleneck now
- Primary mismatch: stop-baseline mismatch + downstream randomness mismatch between ACT and STOP futures.
- Default sign-flip-rate mean: `0.1383`.
- Default delta-std mean: `0.0906`.

## 3) Single lightweight next strategy
- Use matched ACT-vs-STOP horizon-2 local comparator with paired RNG seeds.
- Keep ACT and STOP futures identical except for the first-step intervention (ACT-here vs skip-here).
