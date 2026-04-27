# DIRECT_RESERVE_FRONTIER_GATE_V2_STATUS

- Output directory: `outputs/direct_reserve_frontier_gate_v2_failure_slice_20260426T222200Z`
- Variant: `direct_reserve_frontier_gate_v2`
- Status: diagnostic-only; not canonical.
- Matched examples: 30
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- v1 accuracy: 0.6667
- v2 accuracy: 0.7333
- v2 total overrides: 1
- v2 helpful overrides: 1
- v2 harmful overrides: 0
- v2 blocks harmful v1 overrides: 1
- v2 preserves reported helpful override: 1

Interpretation: v2 improves the saved-trace reported surface metric by blocking both harmful v1 overrides, but the only preserved helpful override remains artifact-sensitive. Do not edit the manuscript or run a larger real-model pilot yet.
