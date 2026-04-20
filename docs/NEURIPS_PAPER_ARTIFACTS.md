# NeurIPS Paper Artifacts

## Canonical input sources

The paper pipeline reads from:
- `outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/`
- `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
- `outputs/full_method_comparison_bundle/20260419T214335Z/`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/` (appendix support)

## Generated figure outputs

Main-paper figures (PDF + PNG):
- `outputs/paper_figures/figure1_problem_setup.{pdf,png}`
- `outputs/paper_figures/figure2_main_frontier.{pdf,png}`
- `outputs/paper_figures/figure3_oracle_gap.{pdf,png}`
- `outputs/paper_figures/figure4_allocation_composition.{pdf,png}`
- `outputs/paper_figures/figure5_anti_collapse.{pdf,png}`
- `outputs/paper_figures/figure6_failure_decomposition.{pdf,png}`
- `outputs/paper_figures/figure7_per_dataset_summary.{pdf,png}`

Main-paper plot data:
- `outputs/paper_plot_data/figure1_problem_setup.json`
- `outputs/paper_plot_data/figure2_main_frontier.csv`
- `outputs/paper_plot_data/figure3_oracle_gap.csv`
- `outputs/paper_plot_data/figure4_allocation_composition.csv`
- `outputs/paper_plot_data/figure5_anti_collapse.csv`
- `outputs/paper_plot_data/figure6_failure_decomposition.csv`
- `outputs/paper_plot_data/figure7_per_dataset_summary.csv`

Appendix figures and data:
- `outputs/paper_figures/appendix_*.{pdf,png}`
- `outputs/paper_plot_data/appendix_*.csv`

## Generated table outputs

- `outputs/paper_tables/table1_benchmark_method_summary.{csv,tex}`
- `outputs/paper_tables/table2_main_frontier.{csv,tex}`
- `outputs/paper_tables/table3_oracle_headroom.{csv,tex}`
- `outputs/paper_tables/table4_anti_collapse.{csv,tex}`
- `outputs/paper_tables/table5_failure_decomposition.{csv,tex}`
- `outputs/paper_tables/table6_robustness.{csv,tex}`

## Claim support mapping

- Figure 1: Problem framing and pipeline identity (fixed-budget next-step allocation + commit control).
- Figure 2: Main frontier (macro across datasets).
- Figure 3: Oracle gap / regret consistency with Figure 2.
- Figure 4: Expansion-vs-verification allocation composition.
- Figure 5: Anti-collapse diagnostics (entropy and concentration).
- Figure 6: Failure decomposition (defeat-case subtype proxy mapping).
- Figure 7: Per-dataset behavior on canonical multi-dataset surface.
- Tables 1-6: benchmark/method surface, frontier comparison, oracle headroom, anti-collapse summary, failure decomposition, robustness/limitations.

## Main paper vs appendix placement

Main-paper recommended:
- Figures 1-7 and Tables 1-6 listed above.

Appendix recommended:
- per-dataset full curve panels for all methods,
- promoted-vs-adversary failure-slice comparison,
- additional dense method comparisons.

## How to regenerate

Run:

- `python scripts/paper/run_all_neurips_paper_artifacts.py`

This regenerates:
- all plot-data CSV/JSON,
- all tables (CSV + TeX),
- all main and supported appendix figure binaries (PDF + PNG).

## Missing pieces for stronger final submission

- Native strict-coupled/tie-aware controller integration in frontier evaluator (remove alias bridge).
- Direct committed old-vs-current tree-comparison quantitative plot-data in canonical format.
- Direct committed output-layer repair effect bundle on the canonical multi-dataset frontier surface.
