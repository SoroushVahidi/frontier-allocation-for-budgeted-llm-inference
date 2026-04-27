# Direct Reserve Frontier Gate Failure Slice Diagnostic

This is a cached/offline diagnostic for the Cohere GSM8K Stage-1 slice where `strict_f3` lost to `external_l1_max`.

- Diagnostic type: `diagnostic_limited_prediction_level`
- Matched examples: 30
- `external_l1_max` accuracy: 0.7667
- `strict_f3` accuracy: 0.5000
- `direct_reserve_frontier_gate_v1` accuracy: 0.7667
- Total overrides: 0
- Helpful overrides: 0
- Harmful overrides: 0

The cached failure slice does not include candidate-pool support/maturity fields, so the fallback copies the direct reserve (`external_l1_max`) with zero overrides and does not promote this variant to canonical evidence.
