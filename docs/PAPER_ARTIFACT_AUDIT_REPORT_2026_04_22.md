# Paper Artifact Audit Report (2026-04-22)

## Status note (read this first)

This document is a **dated intermediate audit snapshot** from 2026-04-22. It is retained for provenance, but it **does not describe the current canonical NeurIPS paper output set** after the later manuscript-facing figure/table repackaging (including the reduced main-paper figure set and appendix A1-A4 naming).

For the current authoritative artifact list and regeneration policy, use:

- `docs/NEURIPS_PAPER_ARTIFACTS.md`
- `docs/FINAL_FIGURE_PACKAGE_REPORT_20260422T181524Z.md`

## Scope

This audit completed an end-to-end cleanup of the NeurIPS paper-facing figure and table pipeline under:

- `scripts/paper/run_all_neurips_paper_artifacts.py`

## What was kept (final canonical set)

Main-paper figures:
- `outputs/paper_figures/figure1_problem_setup.{pdf,png}`
- `outputs/paper_figures/figure2_main_frontier.{pdf,png}`
- `outputs/paper_figures/figure3_oracle_gap.{pdf,png}`
- `outputs/paper_figures/figure4_allocation_composition.{pdf,png}`
- `outputs/paper_figures/figure5_anti_collapse.{pdf,png}`
- `outputs/paper_figures/figure6_failure_decomposition.{pdf,png}`
- `outputs/paper_figures/figure7_per_dataset_summary.{pdf,png}`

Appendix figures:
- `outputs/paper_figures/appendix_budget_formula_curves.{pdf,png}`
- `outputs/paper_figures/appendix_output_layer_repair.{pdf,png}`

Main-paper tables:
- `outputs/paper_tables/table1_benchmark_method_summary.{csv,tex}`
- `outputs/paper_tables/table2_main_frontier.{csv,tex}`
- `outputs/paper_tables/table3_oracle_headroom.{csv,tex}`
- `outputs/paper_tables/table4_anti_collapse.{csv,tex}`
- `outputs/paper_tables/table5_failure_decomposition.{csv,tex}`
- `outputs/paper_tables/table6_robustness.{csv,tex}`

Canonical plot data:
- `outputs/paper_plot_data/figure1_problem_setup.json`
- `outputs/paper_plot_data/figure2_main_frontier.csv`
- `outputs/paper_plot_data/figure3_oracle_gap.csv`
- `outputs/paper_plot_data/figure4_allocation_composition.csv`
- `outputs/paper_plot_data/figure5_anti_collapse.csv`
- `outputs/paper_plot_data/figure6_failure_decomposition.csv`
- `outputs/paper_plot_data/figure7_per_dataset_summary.csv`
- `outputs/paper_plot_data/appendix_per_dataset_frontier_curves.csv`
- `outputs/paper_plot_data/appendix_output_layer_repair.csv`
- `outputs/paper_plot_data/sources/strict_phased_multidataset_frontier.csv`

## What was deleted

- Stale plot-data support files with unclear canonical role:
  - `outputs/paper_plot_data/figure1_support_metadata.csv`
  - `outputs/paper_plot_data/figure1_problem_schematic.json`
- Legacy appendix duplicate binaries (same curve copied under misleading dataset-specific names):
  - `outputs/paper_figures/appendix_per_dataset_frontier_HuggingFaceH4_MATH-500.{pdf,png}`
  - `outputs/paper_figures/appendix_per_dataset_frontier_Idavidrein_gpqa.{pdf,png}`
  - `outputs/paper_figures/appendix_per_dataset_frontier_openai_gsm8k.{pdf,png}`

## What was newly created

- Canonical structured source replacing markdown parsing:
  - `outputs/paper_plot_data/sources/strict_phased_multidataset_frontier.csv`
- Provenance READMEs:
  - `outputs/paper_figures/README.md`
  - `outputs/paper_tables/README.md`
- This audit report:
  - `docs/PAPER_ARTIFACT_AUDIT_REPORT_2026_04_22.md`

## Provenance and policy fixes

- Resolved contradiction on `outputs/paper_plot_data/` status: it is now consistently documented as canonical paper plot-data output.
- Demoted stale NeurIPS status/audit docs to historical snapshot role to prevent policy conflicts.
- Updated canonical docs to use one artifact class model:
  - main-paper artifacts,
  - appendix artifacts,
  - historical/provenance-only artifacts.
- Replaced fragile markdown-table parsing in `scripts/paper/paper_data_sources.py` with structured CSV loading.

## Figure/table polish highlights

- Figure 4 and Figure 5 no longer encode near-duplicate semantics:
  - Figure 4 focuses on action composition (`avg_actions`, `avg_expansions`, `avg_verifications`).
  - Figure 5 remains anti-collapse diagnostics (`longest_same_family_run`, `max_family_share`).
- Appendix figure naming now matches content (`appendix_budget_formula_curves`).
- Table TeX generation now escapes `_`, `%`, `&`, and backslashes for cleaner LaTeX output.

## Regeneration command

- `python scripts/paper/run_all_neurips_paper_artifacts.py`

## Remaining limitations

- Canonical input bundles are still timestamp-pinned in script constants and may need periodic source updates as new canonical runs are promoted.
- Figure quality is validated by script-level layout constraints; final manuscript integration should still perform visual spot checks in the target LaTeX template column widths.
