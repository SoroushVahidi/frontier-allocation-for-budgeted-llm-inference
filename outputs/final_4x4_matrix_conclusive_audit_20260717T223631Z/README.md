# Final 4x4 Matrix Conclusive Audit

Timestamp: `20260717T223631Z`

This package recomputes all available 4x4 cells from per-example artifacts, reruns FTA through
`experiments/fta_policy.py::apply_fta_to_row`, and leaves Fireworks x GPQA blocked under the
existing protocol-nonconvergence evidence.

Key outcomes:

- Completed validated cells: `15/16`
- FTA available cells: `15/16`
- Blocked cells: `fireworks::accounts/fireworks/models/deepseek-v4-pro::gpqa_diamond`
- Paid API calls made during this audit: `NO`
- Azure x GPQA FTA replay: `102/198`
- Vertex x GPQA discrepancy resolved: canonical sanitized replay `125/198`, stale unsanitized replay `124/198`

Tie policy:

- Method winners are all methods tied for the maximum integer correct count in a completed cell.
- Strict sole wins require exactly one top method.
- OUR is Frontier or FTA; external baselines are L1, S1, and TALE.
- Fireworks x GPQA is excluded from winner counts because no comparable winner is defined.
