# NeurIPS Paper Artifacts

## Purpose

This guide documents the text-only manuscript artifact pipeline for the current NeurIPS direction:
fixed-budget adaptive test-time compute allocation with frontier/oracle-gap analysis and anti-collapse diagnostics.

## Canonical inputs used by this pipeline

- `outputs/imported_methodology_frontier_eval/20260417T000000Z/`
- `outputs/imported_methodology_frontier_eval/20260420T_multidataset_frontier_v1/`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/`
- `outputs/branch_label_bruteforce_learning/soft_prob_tie_matched_20260417/`
- `outputs/branch_scorer_v3_final_eval/final_summary.json` (auxiliary robustness context)

## Generated outputs

Plot data:
- `outputs/paper_plot_data/figure1_problem_schematic.json`
- `outputs/paper_plot_data/main_frontier_curves.csv`
- `outputs/paper_plot_data/oracle_gap_curves.csv`
- `outputs/paper_plot_data/allocation_composition.csv`
- `outputs/paper_plot_data/anti_collapse_diagnostics.csv`
- `outputs/paper_plot_data/failure_decomposition.csv`
- `outputs/paper_plot_data/per_dataset_frontiers.csv`
- appendix plot-data CSVs under `outputs/paper_plot_data/appendix_*.csv`

Tables:
- `outputs/paper_tables/benchmark_method_summary.{csv,tex}`
- `outputs/paper_tables/main_frontier_comparison.{csv,tex}`
- `outputs/paper_tables/oracle_headroom_summary.{csv,tex}`
- `outputs/paper_tables/anti_collapse_summary.{csv,tex}`
- `outputs/paper_tables/failure_decomposition.{csv,tex}`
- `outputs/paper_tables/robustness_sensitivity.{csv,tex}`

## Script entry points

- Canonical runner: `scripts/paper/run_all_neurips_paper_artifacts.py`
- Multi-dataset frontier evaluator: `scripts/run_imported_methodology_frontier_eval_multidataset.py`

## Figure/table claim structure support

- Figure 2 + Table 2: fixed-budget frontier behavior and strongest baseline comparisons.
- Figure 3 + Table 3: oracle headroom / regret accounting.
- Figure 4 + Figure 5 + Table 4: allocation composition and anti-collapse diagnostics.
- Figure 6 + Table 5: honest failure decomposition proxies (tree-generation-like vs output-layer-like failures).
- Figure 7 + Table 6: per-dataset and robustness scope boundaries.

## Main-paper safe artifacts

Main-paper safe now:
- Frontier curves, oracle-gap curves, anti-collapse/control diagnostics, and failure proxy decomposition from canonical import runs.

Appendix-only now:
- Tie-aware formulation/fallback slices from near-tie branch-comparison artifacts.
- Branch-scorer robustness context from `branch_scorer_v3_final_eval`.

## Build commands

From repository root:

- `python scripts/paper/run_all_neurips_paper_artifacts.py`
- `python scripts/run_imported_methodology_frontier_eval_multidataset.py --datasets "openai/gsm8k,HuggingFaceH4/MATH-500,Idavidrein/gpqa" --subset-size 24 --budgets "8,10" --api-backend simulator --run-id "20260420T_multidataset_frontier_v1"`

Optional local rendering of binaries (not committed):

- `python scripts/paper/run_all_neurips_paper_artifacts.py --render-plots`

## Missing pieces for stronger NeurIPS submission

- Native strict-coupled/tie-aware controller integration in `frontier_matrix_core` (instead of alias-bridge reporting).
- A direct committed old-vs-current tree-generation summary table for appendix.
- A committed targeted output-layer repair study aligned with frontier runs.
- Wider real-model scale with stronger statistical confidence intervals.
