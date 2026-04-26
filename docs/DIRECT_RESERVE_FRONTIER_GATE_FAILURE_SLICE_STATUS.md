# DIRECT_RESERVE_FRONTIER_GATE_FAILURE_SLICE_STATUS

- Output directory: `outputs/direct_reserve_frontier_gate_traced_failure_slice_20260426T212138Z`
- Diagnostic type: `not_evaluable_missing_traced_candidate_pool`
- Matched examples: 30
- `external_l1_max` accuracy: 0.8
- `strict_f3` accuracy: 0.5333333333333333
- `direct_reserve_frontier_gate_v1` accuracy: NA_not_run_no_cached_traces_or_api
- Override count: NA_not_run
- Helpful overrides: NA_not_run
- Harmful overrides: NA_not_run
- Direct-solved cases preserved: NA_not_run
- Direct-solved cases harmed: NA_not_run
- Reserve-use rate: NA_not_run
- Override rate: NA_not_run
- Support/maturity metadata coverage: 0/30 matched cases; 0 trace tables present

Interpretation: a paired candidate-pool diagnostic is not possible offline from the old cached Cohere Stage-1 artifacts. The method was not rerun and must not be promoted. The smallest justified real-model step is the exact 30-cell traced replay; a larger pilot is not justified until that replay shows helpful overrides without harmful overrides.
