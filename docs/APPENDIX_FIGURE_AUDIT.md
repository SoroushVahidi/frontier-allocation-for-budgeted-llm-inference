# Appendix Figure Audit

This note records appendix figure reality in the current checkout and prevents references to non-existent artifacts.

## Appendix figures that already exist and are usable

- Per-dataset frontier appendix support (preserved as-is):
  - `outputs/paper_figures/appendix_per_dataset_frontier_HuggingFaceH4_MATH*`
  - `outputs/paper_figures/appendix_per_dataset_frontier_Idavidrein_gpqa.{pdf,png}`
  - `outputs/paper_figures/appendix_per_dataset_frontier_openai_gsm8k.{pdf,png}`
- Promoted-vs-adversary failure-slice appendix support (preserved as-is):
  - `outputs/paper_figures/appendix_promoted_vs_adversary_failure_slices.{pdf,png}`
- Targeted output-layer repair appendix support:
  - `outputs/paper_figures/appendix_output_layer_repair.{pdf,png}`
  - `outputs/paper_plot_data/appendix_output_layer_repair.csv`

## Appendix figures removed in cleanup

- Removed as stale/mixed-scope:
  - `appendix_promoted_vs_adversary_failure_slices.{pdf,png}`
  - `appendix_promoted_vs_adversary_failure_slices.csv`

## Missing figures that can be generated from current artifacts

- `appendix_output_layer_repair.{pdf,png}` and `appendix_output_layer_repair.csv` are now generated from:
  - `outputs/current_failure_output_layer_repair_20260420/manifest.json`
  - `outputs/current_failure_output_layer_repair_20260420/summary.json`
  - `outputs/current_failure_output_layer_repair_20260420/per_case_results.jsonl`
  - `outputs/current_failure_output_layer_repair_20260420/mismatch_breakdown.json`
  - `outputs/current_failure_output_layer_repair_20260420/targeted_16_table.csv`
  - `docs/CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md`

## Figures that should not be referenced in paper text

- Do not reference removed bounded-surface figure `appendix_promoted_vs_adversary_failure_slices.pdf`.
- Do not reference `appendix_broad_comparison_frontier.pdf` (no such figure file in this checkout).
- Do not reference `appendix_old_vs_current_tree_comparison.pdf` (no such figure file in this checkout).

Instead, use existing appendix support:
- per-dataset frontier subsection -> `appendix_per_dataset_frontier_*`
- promoted-vs-adversary failure-slice subsection -> `appendix_promoted_vs_adversary_failure_slices.*`

