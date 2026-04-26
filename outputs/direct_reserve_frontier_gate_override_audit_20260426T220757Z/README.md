# Direct Reserve Frontier Gate Override Audit

- Source diagnostic: `outputs/direct_reserve_frontier_gate_failure_slice_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN_DIAGNOSTIC_ACTUAL`
- Source replay: `outputs/cohere_real_model_cost_normalized_validation_TRACE_REPLAY_COHERE_GSM8K_STAGE1_MIN`
- V1 accuracy: 0.6667
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- V1 overrides: 3 total, 1 reported helpful, 2 reported harmful

## Key finding

The single reported helpful override (`openai_gsm8k_2`, seed 11, budget 8) is not a clean frontier-answer rescue: the stored frontier candidate is `475` while gold is `450`; the surfaced gate result is correct because output-layer repair selected `450`. Treat this as an output-repair artifact, not proof that the frontier override is safe.

## Helpful vs harmful comparison

All three v1 overrides had `frontier_support=2`, `frontier_candidate_family_count=2`, and `support_margin=1`, so the obvious multi-branch/multi-family thresholds do not separate helpful from harmful cases. The clearest conservative separator is whether the external incumbent answer appears in the traced candidate pool:

- Reported helpful case: external answer support in traced pool = 0.
- Two reported harmful cases: external answer support in traced pool > 0.

## Recommended diagnostic variant

`direct_reserve_frontier_gate_v2`: keep v1 as a base but allow override only when the frontier has multi-branch and multi-family support and the external/near-direct incumbent answer has zero support in the traced pool. Offline, this preserves the one reported helpful v1 override and blocks both reported harmful v1 overrides, yielding reported-surface accuracy 0.7333.

## Trace-loading note

The replay source contains complete per-case CSV rows and `per_example_records.jsonl` metadata for all 30 cells. The JSON trace filenames are not seed/budget-qualified, so repeated example/method traces collide on disk; this audit therefore treats the CSV tables and per-example metadata as authoritative for per-case fields.

## Caveat

Because the helpful case is output-repair driven, this rule is only a diagnostic hypothesis. Do not promote it or run a larger pilot before validating a cleaned v2 implementation on this same traced slice.
