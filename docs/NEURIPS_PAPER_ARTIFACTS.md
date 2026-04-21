## NeurIPS Paper Artifacts

## Canonical input sources (current)

The canonical paper pipeline now reads from:
- `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/`
- `outputs/budget_aware_family_cap_eval_20260421T162842Z/`
- `outputs/current_failure_output_layer_repair_20260420/` (appendix output-layer repair)

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
- `outputs/paper_figures/appendix_output_layer_repair.{pdf,png}`
- `outputs/paper_plot_data/appendix_output_layer_repair.csv`

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

## Policy

- Canonical runner: `python scripts/paper/run_all_neurips_paper_artifacts.py`
- Compatibility shim: `scripts/paper/run_all_neurips_artifacts.py` (forwards to canonical runner)
- See cleanup report: `docs/PAPER_ARTIFACT_CLEANUP_REPORT_2026_04_21.md`
