# NEAR_DIRECT_RESERVE_FRONTIER_GATE_STATUS

- Output directory: `outputs/near_direct_reserve_frontier_gate_failure_slice_20260426T223900Z`
- Variant: `near_direct_reserve_frontier_gate_v1`
- Status: diagnostic-only; not canonical; not manuscript-ready.
- Matched examples: 30
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- `direct_reserve_frontier_gate_v1` accuracy: 0.6667
- `direct_reserve_frontier_gate_v2` accuracy: 0.7333
- `near_direct_reserve_frontier_gate_v1` accuracy: 0.7333
- Overrides: 1
- Helpful overrides: 1
- Harmful overrides: 0
- Direct-solved preserved: 18
- Direct-solved harmed: 3
- Matches offline protected-incumbent audit rule: yes.
- Can run runtime method end-to-end without new API calls: no.
- Additional real calls required: To run the runtime method end-to-end on the same 30 cells, call Cohere for near_direct_reserve_frontier_gate_v1 on openai/gsm8k seeds=11,23 budgets=4,6,8 examples openai_gsm8k_0..4 with --save-branch-traces.
- Artifact-sensitive helpful override remains: yes.
- Larger real-model pilot justified: no.

Interpretation: the runtime-aligned near-direct variant matches the saved-trace protected-incumbent audit rule, but the sole helpful override is still artifact-sensitive. Do not edit the manuscript or promote this method.
