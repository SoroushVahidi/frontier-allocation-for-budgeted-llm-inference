# Direct Reserve Frontier Gate V2 Failure Slice Diagnostic

- Diagnostic type: `offline_saved_trace_v2_diagnostic`
- `direct_reserve_frontier_gate_v2` is diagnostic-only and not canonical.
- Matched examples: 30
- v1 accuracy: 0.6667
- v2 accuracy: 0.7333
- `external_l1_max` accuracy: 0.7000
- v2 overrides: 1
- v2 helpful overrides: 1
- v2 harmful overrides: 0

The preserved reported-helpful override is artifact-sensitive because the earlier audit found it depends on output repair rather than a clean frontier-answer rescue. A larger real-model pilot is not justified yet, and the manuscript should not be changed.
