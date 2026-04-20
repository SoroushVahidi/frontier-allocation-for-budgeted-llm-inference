# Appendix Figure Audit

## Scope and audit rules

This audit checks what appendix figures are already present, what is reproducibly supportable from canonical artifacts, and what is not currently supportable without fabricating sources.

Primary canonical sources used in this audit:

- `outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/`
- `outputs/full_method_comparison_bundle/20260419T214335Z/`
- `outputs/current_failure_output_layer_repair_20260420/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `scripts/paper/`

## Main-paper figures already present

All main figures already exist in `outputs/paper_figures/` and are supported by committed plot-data/scripts:

- `figure1_problem_setup.{pdf,png}`
- `figure2_main_frontier.{pdf,png}`
- `figure3_oracle_gap.{pdf,png}`
- `figure4_allocation_composition.{pdf,png}`
- `figure5_anti_collapse.{pdf,png}`
- `figure6_failure_decomposition.{pdf,png}`
- `figure7_per_dataset_summary.{pdf,png}`

No unnecessary re-creation was required for this task.

## Appendix figures already present and supported

### 1) Output-layer repair appendix figure

- Figure files:
  - `outputs/paper_figures/appendix_output_layer_repair.pdf`
  - `outputs/paper_figures/appendix_output_layer_repair.png`
- Plot-data:
  - `outputs/paper_plot_data/appendix_output_layer_repair.csv`
- Script:
  - `scripts/paper/plot_appendix_output_layer_repair.py`
- Source artifacts:
  - `outputs/current_failure_output_layer_repair_20260420/{manifest.json,summary.json,per_case_results.jsonl,mismatch_breakdown.json,targeted_16_table.csv}`
  - `docs/CURRENT_FAILURE_OUTPUT_LAYER_REPAIR_STATUS_2026_04_20.md`

Status: **supported and now aligned to targeted-subset-only presentation**.

### 2) Per-dataset frontier appendix curves

- Figure files:
  - `outputs/paper_figures/appendix_per_dataset_frontier_*.{pdf,png}`
- Plot-data:
  - `outputs/paper_plot_data/appendix_per_dataset_frontier_curves.csv`
- Script:
  - `scripts/paper/plot_appendix_figures.py` (`plot_appendix_per_dataset_curves`)
- Source artifacts:
  - `outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/budget_frontier_summary.csv`

Status: **already supported and preserved**.

### 3) Broader comparison frontier (more baselines than main-paper display)

Existing support is via the appendix per-dataset full-curve panels:

- `appendix_per_dataset_frontier_*.{pdf,png}` includes all canonical methods from the canonical frontier CSV.
- This is broader than the constrained method display used in `figure7_per_dataset_summary`.

Status: **already supported by existing appendix per-dataset frontier figures**.

## Requested appendix figures currently not supportable

### Old-vs-current tree comparison summary figure

Current docs reference an old-vs-current tuned tree bundle path, but that bundle is not present in this checkout under `outputs/`.

- Referenced in docs: `outputs/twenty_case_old_vs_current_tuned_tree_comparison_20260420/`
- Present in this checkout: **not found**

Status: **not supportable from current repository outputs in this checkout**.
No figure was fabricated.

## Changes made in this pass

- Kept existing clean/supported main and appendix figures.
- Updated output-layer repair appendix figure pipeline to enforce targeted-subset-only content.
- Regenerated:
  - `outputs/paper_plot_data/appendix_output_layer_repair.csv`
  - `outputs/paper_figures/appendix_output_layer_repair.pdf`
  - `outputs/paper_figures/appendix_output_layer_repair.png`

