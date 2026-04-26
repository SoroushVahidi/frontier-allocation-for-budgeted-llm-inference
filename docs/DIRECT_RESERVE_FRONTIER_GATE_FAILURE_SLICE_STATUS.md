# DIRECT_RESERVE_FRONTIER_GATE_FAILURE_SLICE_STATUS

- Output directory: `outputs/direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL`
- Source replay directory: `outputs/cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN`
- Diagnostic type: `paired_candidate_pool_diagnostic`
- Matched examples: 30
- Support/maturity metadata coverage: 30/30
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- `direct_reserve_frontier_gate_v1` accuracy: 0.6667
- Paired delta vs `external_l1_max`: -0.0333
- Override count: 3
- Helpful overrides: 1
- Harmful overrides: 2
- Direct-solved cases preserved: 16
- Direct-solved cases harmed: 5
- Reserve-use rate: 0.9000
- Override rate: 0.1000

Token/cost/latency: `external_l1_max` used 15872 tokens / $0.083136 / 2.6843s mean latency; `strict_f3` used 31153 tokens / $0.157815 / 4.2754s; `direct_reserve_frontier_gate_v1` used 32798 tokens / $0.168822 / 12.4827s.

Interpretation: the traced diagnostic is now a paired candidate-pool diagnostic, but it does not justify a larger pilot. The method trails `external_l1_max` by 0.0333 accuracy, and 2 of 3 overrides are harmful. Keep diagnostic-only; do not promote as canonical evidence.
