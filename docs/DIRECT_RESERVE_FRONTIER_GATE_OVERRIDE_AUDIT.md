# DIRECT_RESERVE_FRONTIER_GATE_OVERRIDE_AUDIT

- Output directory: `outputs/direct_reserve_frontier_gate_override_audit_20260426T220757Z`
- Source diagnostic: `outputs/direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL`
- V1 accuracy: 0.6667
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- V1 overrides: 3 total, 1 reported helpful, 2 reported harmful

## Recommended variant

`direct_reserve_frontier_gate_v2` should be a stricter diagnostic-only filter over v1:

1. Require `frontier_support >= 2`.
2. Require `frontier_candidate_family_count >= 2`.
3. Require `support_margin >= 1`.
4. Require `direct_reserve_agreement_count <= 1`.
5. Require the external/near-direct incumbent answer to have zero support in the traced candidate pool.
6. Never override when incumbent support is at least frontier support.

Offline reported-surface sweep for the recommended rule: accuracy 0.7333, overrides 1, reported helpful 1, reported harmful 0.

## Interpretation

This offline rule improves over v1 in the reported surface metric and blocks both reported harmful overrides, but the only preserved helpful case is an output-repair artifact. Keep this diagnostic-only; do not edit the manuscript or run a larger real-model pilot.

## Trace-loading note

The replay source has complete per-case CSV and `per_example_records.jsonl` metadata, but trace JSON filenames are not seed/budget-qualified. Per-case conclusions in this audit use the CSV tables and per-example metadata rather than relying on unique JSON paths.
