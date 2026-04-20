# Appendix output-layer repair figure note

## What this figure shows

`appendix_output_layer_repair` summarizes currently committed repair evidence in two aligned views:

- **Targeted subset view:** before-vs-after surfaced correctness on the subset where correct internal reasoning is already present.
- **Full failure-slice view:** repaired vs unresolved counts on the full current 20-case failure slice.

This supports the appendix statement:
"On the subset where correct internal reasoning is already present, deterministic output-layer repair yields a real but bounded improvement."

## Why this is the strongest currently supported version

The repository currently does not contain the machine-readable bundle path
`outputs/current_failure_output_layer_repair_20260420/summary.json` in this checkout.
So this appendix figure is built from the committed status artifact:

- `docs/CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md`

using its explicitly reported counts (targeted subset size, resolved-by-repair count, and the referenced current 20-case failure slice).

This keeps the figure honest and repository-backed, while still communicating the intended claim:
repair helps when the answer is already in-tree, but does not remove upstream/tree-generation failures outside that slice.
