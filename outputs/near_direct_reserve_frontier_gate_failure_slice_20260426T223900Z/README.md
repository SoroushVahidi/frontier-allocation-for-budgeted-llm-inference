# Near Direct Reserve Frontier Gate Failure Slice Diagnostic

- `near_direct_reserve_frontier_gate_v1` is diagnostic-only, not canonical, and not manuscript-ready.
- Matched examples: 30
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- v1 accuracy: 0.6667
- v2 accuracy: 0.7333
- near-direct accuracy: 0.7333
- near-direct overrides: 1
- helpful/harmful: 1/0

This saved-trace diagnostic exactly matches the offline protected-incumbent audit rule by protecting the saved `external_l1_max` incumbent. The only helpful override remains artifact-sensitive, so a larger real-model pilot is not justified and the manuscript should not be changed.
