# Appendix output-layer repair figure note

## Source artifacts used

The figure and plot-data are built directly from these committed artifacts:

- `outputs/current_failure_output_layer_repair_20260420/manifest.json`
- `outputs/current_failure_output_layer_repair_20260420/summary.json`
- `outputs/current_failure_output_layer_repair_20260420/mismatch_breakdown.json`
- `outputs/current_failure_output_layer_repair_20260420/per_case_results.jsonl`
- `outputs/current_failure_output_layer_repair_20260420/targeted_16_table.csv`
- `docs/CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md`

## Subset represented

`appendix_output_layer_repair` represents only the targeted subset where:

- current method is wrong,
- self-consistency baseline is correct, and
- the correct answer is already present in the method's final tree.

This subset has size 16 in the current canonical repair bundle.

## What the figure shows

The figure reports targeted-subset counts only:

- targeted subset size,
- incorrect before repair,
- correct after repair,
- unresolved after repair.

This supports the appendix statement:
"On the subset where correct internal reasoning is already present, deterministic output-layer repair yields a real but bounded improvement."

## What this figure does not claim

- It does **not** claim universal performance gains over all failures or all datasets.
- It does **not** claim that output-layer repair solves upstream tree-generation bottlenecks.
- It does **not** replace broad frontier/ranking evidence from main-paper figures.
