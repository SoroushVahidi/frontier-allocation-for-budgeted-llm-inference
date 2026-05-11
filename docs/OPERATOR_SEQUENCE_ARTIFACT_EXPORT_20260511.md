# Operator Sequence Artifact Export

## Source Chosen

Primary source artifact:
`outputs/cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/per_example_records.jsonl`

Why this source:

- It is an existing completed offline artifact bundle.
- It contains consistent per-example traces across the paired PAL/retry comparison.
- It is richer than a singleton record bundle, but still safe to process without any API calls.

## Exported Row Type

The exporter writes conservative pseudo-path prefix rows from per-example trace metadata.

- If `action_trace` is present, rows are chained in trace order.
- If only `final_nodes` are present, those are exported as a one-node pseudo-path.
- If neither trace form exists, a singleton record-level row is exported.

This is artifact-level mining, not a full tree reconstruction.

## Gold-Leakage Policy

- `feature_*` fields are derived only from observable trace metadata and support counts.
- Gold-derived values appear only in `label_*` fields.
- The exporter does not place obvious gold labels in `feature_*` names.

## Limitations

- Parent/child links in the selected artifact are not reliable enough for a stable tree export.
- The row set is therefore conservative and sequence-based rather than a verified branching tree.
- The exporter does not change runtime defaults.
- No paid/model API calls are made.

## Claim Boundary

This export is a data-preparation step for later operator-sequence mining.
It is not a baseline result and should not be cited as one.
