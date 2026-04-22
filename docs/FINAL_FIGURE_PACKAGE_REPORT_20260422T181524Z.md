# Final Figure Package Report (20260422T181524Z)

## Scope
- Task: finalize manuscript and appendix figure package while keeping Figure 1 unchanged.
- Figure 1 policy: `outputs/paper_figures/figure1.jpg` was not modified.
- Experiment policy: no experiment reruns were performed; figures were rebuilt from existing machine-readable canonical artifacts.

## Final main-paper figures
- Figure 1: `outputs/paper_figures/figure1.jpg` (unchanged)
- Figure 2: `outputs/paper_figures/figure2_main_frontier.{pdf,png}`
- Figure 3: `outputs/paper_figures/figure3_failure_decomposition.{pdf,png}`

## Final appendix figures
- Figure A1: `outputs/paper_figures/appendix_figure_a1_oracle_gap_regret.{pdf,png}`
- Figure A2: `outputs/paper_figures/appendix_figure_a2_anti_collapse.{pdf,png}`
- Figure A3: `outputs/paper_figures/appendix_figure_a3_allocation_composition.{pdf,png}`
- Figure A4: `outputs/paper_figures/appendix_figure_a4_component_ablation.{pdf,png}`

## Canonical machine-readable plot data
- Main:
  - `outputs/paper_plot_data/figure2_main_frontier.csv`
  - `outputs/paper_plot_data/figure3_failure_decomposition.csv`
- Appendix:
  - `outputs/paper_plot_data/appendix_a1_oracle_gap_regret.csv`
  - `outputs/paper_plot_data/appendix_a2_anti_collapse.csv`
  - `outputs/paper_plot_data/appendix_a3_allocation_composition.csv`
  - `outputs/paper_plot_data/appendix_a4_component_ablation.csv`

## Canonical data sources used
- Paper-method decision bundle (matched manuscript surface):
  - `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/20260422T175142Z/`
  - Used files: `budget_performance_frontier.csv`, `oracle_gap_regret.csv`, `failure_decomposition_plot_data.csv`, `anti_collapse_plot_data.csv`, `decision_table.csv`
- strict_f3 manuscript-surface component-ablation package:
  - `outputs/component_ablation_strict_f3_paper_surface/20260422T180445Z/`
  - Used file: `component_summary_table.csv`

## What was replaced
- Replaced old main Figure 3 oracle-gap artifact with manuscript-story failure decomposition as main Figure 3.
- Replaced prior appendix figure set with A1-A4 aligned to manuscript strict_f3 lock and matched surface.

## What was deleted as stale/conflicting
- From `outputs/paper_figures/`:
  - `figure3_oracle_gap.{pdf,png}`
  - `figure4_allocation_composition.{pdf,png}`
  - `figure5_anti_collapse.{pdf,png}`
  - `figure6_failure_decomposition.{pdf,png}`
  - `figure7_per_dataset_summary.{pdf,png}`
  - `figure8_component_ablation.{pdf,png}`
  - `appendix_budget_formula_curves.{pdf,png}`
  - `appendix_output_layer_repair.{pdf,png}`
- From `outputs/paper_plot_data/`:
  - `figure3_oracle_gap.csv`
  - `figure4_allocation_composition.csv`
  - `figure5_anti_collapse.csv`
  - `figure6_failure_decomposition.csv`
  - `figure7_per_dataset_summary.csv`
  - `appendix_per_dataset_frontier_curves.csv`
  - `appendix_output_layer_repair.csv`

## Figure quality and consistency checks
- Numbering/story alignment:
  - Main-paper figures reduced to high-value set: Figure 1, Figure 2, Figure 3.
  - Appendix figures mapped to A1-A4.
- Naming consistency:
  - Method names standardized to manuscript-facing methods (`strict_f3`, `strict_gate1_cap_k6`, strongest fair external comparator).
- Plot readability:
  - Simplified comparator set to avoid legend crowding.
  - Axis labels and titles standardized and non-conflicting.
  - `figure3_failure_decomposition` legend/layout was cleaned so legend text does not overlap the plotted region.
  - Main Figure 3 keeps only `strict_f3`, `strict_gate1_cap_k6`, and `external_l1_max` because `external_l1_max` is the strongest fair near-direct external baseline on the locked manuscript surface.
  - Expanded all-externals appendix view is provided at `outputs/paper_figures/figure3_failure_decomposition_all_externals_appendix.{pdf,png}`.

## Omitted figures and rationale
- Prior broad default and formula-sweep heavy figures were omitted from final manuscript package because they conflict with the locked manuscript-facing strict_f3 story or add low-value redundancy under page pressure.
- Appendix output-layer-repair figure was omitted from this final set to keep appendix compact and prioritized around A1-A4.

## Remaining limitations
- The anti-collapse metrics available on the manuscript decision bundle are summary-level diagnostics; deeper family-share telemetry is not available in that bundle and is therefore not plotted here.
- Figure captions in manuscript text may still need final wording updates in whichever external manuscript source consumes these outputs.
