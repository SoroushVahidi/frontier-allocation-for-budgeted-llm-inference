## NeurIPS Paper Artifacts

## Canonical paper pipeline model

- Canonical entrypoint: `python scripts/paper/run_all_neurips_paper_artifacts.py`
- Canonical output roots:
  - `outputs/paper_plot_data/` (machine-readable figure data)
  - `outputs/paper_figures/` (publication figure binaries)
  - `outputs/paper_tables/` (publication tables)
- Artifact classes:
  - main-paper artifacts,
  - appendix artifacts,
  - historical/provenance-only artifacts (outside canonical paper output roots unless explicitly noted).

## Canonical input sources (current)

The canonical paper pipeline for the finalized manuscript figure package now reads from:
- `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/20260422T175142Z/`
- `outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z/`
- `outputs/paper_plot_data/figure1_problem_setup.json` (Figure 1 schematic input; unchanged)

Method-status contract for these manuscript artifacts:
- manuscript-facing internal winner on canonical manuscript-facing matched surface: `strict_f3`
- broader operational default on broader strict-phased surface (separate contract): `strict_gate1_cap_k6`
- decision authority: `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`

## Generated figure outputs

Main-paper figures (PDF + PNG):
- `outputs/paper_figures/figure1.jpg`
- `outputs/paper_figures/figure1_problem_setup.{pdf,png}` (canonical vector/raster companion exports)
- `outputs/paper_figures/figure2_main_frontier.{pdf,png}`
- `outputs/paper_figures/figure3_failure_decomposition.{pdf,png}`

Main-paper plot data:
- `outputs/paper_plot_data/figure1_problem_setup.json`
- `outputs/paper_plot_data/figure2_main_frontier.csv`
- `outputs/paper_plot_data/figure3_failure_decomposition.csv`

Appendix figures and data:
- `outputs/paper_figures/appendix_figure_a1_oracle_gap_regret.{pdf,png}`
- `outputs/paper_figures/appendix_figure_a2_anti_collapse.{pdf,png}`
- `outputs/paper_figures/appendix_figure_a3_allocation_composition.{pdf,png}`
- `outputs/paper_figures/appendix_figure_a4_component_ablation.{pdf,png}`
- `outputs/paper_plot_data/appendix_a1_oracle_gap_regret.csv`
- `outputs/paper_plot_data/appendix_a2_anti_collapse.csv`
- `outputs/paper_plot_data/appendix_a3_allocation_composition.csv`
- `outputs/paper_plot_data/appendix_a4_component_ablation.csv`

## Generated table outputs

- `outputs/paper_tables/table1_benchmark_method_summary.{csv,tex}`
- `outputs/paper_tables/table2_main_frontier.{csv,tex}`
- `outputs/paper_tables/table3_oracle_headroom.{csv,tex}`
- `outputs/paper_tables/table4_anti_collapse.{csv,tex}`
- `outputs/paper_tables/table5_failure_decomposition.{csv,tex}`
- `outputs/paper_tables/table6_robustness.{csv,tex}`
- `outputs/paper_tables/table8_method_contract.{csv,tex}`
- `outputs/paper_tables/table9_surface_decision_contract.{csv,tex}`
- `outputs/paper_tables/table10_manuscript_stability_check.{csv,tex}`

## Component ablation support

The manuscript-facing strict_f3 component-ablation figure input is derived from:
- `outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z/component_summary_table.csv`

## Claim support mapping

- Figure 1: Problem framing and pipeline identity (fixed-budget next-step allocation + commit control).
- Figure 2: Budget-performance frontier on the matched manuscript surface.
- Figure 3: Failure decomposition on the matched manuscript surface.
- Appendix Figure A1: Oracle gap / regret on the matched manuscript surface.
- Appendix Figure A2: Anti-collapse diagnostic comparison.
- Appendix Figure A3: Allocation composition comparison.
- Appendix Figure A4: strict_f3 component-ablation summary.
- Tables 1-6: benchmark/method surface, frontier comparison, oracle headroom, anti-collapse summary, failure decomposition, robustness/limitations.
- Table 8: compact manuscript-facing method naming/comparison contract.
- Table 9: compact surface-sensitivity decision contract (`strict_f3` manuscript-facing winner vs `strict_gate1_cap_k6` broader operational default on separate surface).
- Table 10: compact per-seed stability packaging for `strict_f3` vs `strict_gate1_cap_k6` from existing manuscript decision-bundle artifacts.

## Main paper vs appendix placement

Main-paper recommended:
- Figure 1 (unchanged), Figure 2, Figure 3.

Appendix recommended:
- Figures A1-A4 listed above.

Historical / provenance-only:
- older bounded imported-methodology artifacts and associated historical audits are preserved for traceability only and are not canonical paper outputs.

## How to regenerate

Run:

- `python scripts/paper/run_all_neurips_paper_artifacts.py`

This regenerates:
- all plot-data CSV/JSON,
- all tables (CSV + TeX),
- all main and supported appendix figure binaries (PDF + PNG).

Reproducibility caveat:
- The current paper runner is reproducible from committed canonical machine-readable bundles, including timestamped decision/ablation inputs listed above.
- It is a canonical packaging/regeneration path, not a full raw experiment recomputation pipeline by itself.

Script naming note:
- Some `scripts/paper/plot_figure*.py` filenames are legacy-numbered, while emitted figure filenames are canonical. Treat output filenames under `outputs/paper_figures/` as the source of truth.

## Policy

- Canonical runner: `python scripts/paper/run_all_neurips_paper_artifacts.py`
- Compatibility shim: `scripts/paper/run_all_neurips_artifacts.py` (forwards to canonical runner)
- See cleanup report: `docs/PAPER_ARTIFACT_CLEANUP_REPORT_2026_04_21.md`
