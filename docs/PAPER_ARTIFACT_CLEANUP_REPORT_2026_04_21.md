# Paper Artifact Cleanup Report (2026-04-21)

## Scope

This cleanup canonicalizes paper-facing artifacts around the current strict-phased default story:

- default method: `strict_gate1_cap_k6`
- canonical default-decision evidence: `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- canonical failure decomposition evidence: `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/`
- canonical K-formula follow-up evidence: `outputs/budget_aware_family_cap_eval_20260421T162842Z/`

## Artifact Audit Matrix

| Artifact family | Source | Scope class | Status | Action |
|---|---|---|---|---|
| `figure2_main_frontier.*` | strict-phased default decision doc table | current-canonical | revised | regenerated |
| `figure3_oracle_gap.*` | strict-phased default decision table (regret proxy) | current-canonical | revised | regenerated |
| `figure4_allocation_composition.*` | strict-phased dataset table | current-canonical | revised | regenerated |
| `figure5_anti_collapse.*` | budget-aware K-formula aggregate summary | current-canonical | revised | regenerated |
| `figure6_failure_decomposition.*` | canonical hundred failure statistics | current-canonical | revised | regenerated |
| `figure7_per_dataset_summary.*` | strict-phased dataset table | current-canonical | revised | regenerated |
| `appendix_output_layer_repair.*` | output-layer repair bundle | current-canonical appendix | kept | regenerated |
| `appendix_per_dataset_frontier_*.{pdf,png}` | budget-aware formula curves | appendix/historical-compatible | revised | regenerated |
| legacy `appendix_promoted_vs_adversary_failure_slices.*` | old bounded frontier slice CSV | bounded-historical | removed | deleted |
| legacy non-`table[1-6]_*.{csv,tex}` in `outputs/paper_tables/` | mixed older surfaces | bounded-historical | removed | deleted |
| legacy extra CSVs in `outputs/paper_plot_data/` | mixed older surfaces | bounded-historical | removed | deleted |

## Canonical Pipeline Policy

- Canonical entrypoint: `python scripts/paper/run_all_neurips_paper_artifacts.py`
- `scripts/paper/run_all_neurips_artifacts.py` is retained as a compatibility shim and forwards to the canonical runner.
- Plot/table builders are now wired to strict-phased/current bundles rather than older imported frontier defaults.

## Final Main-Paper Artifact Set

- Figures: `figure1_problem_setup`, `figure2_main_frontier`, `figure3_oracle_gap`, `figure4_allocation_composition`, `figure5_anti_collapse`, `figure6_failure_decomposition`, `figure7_per_dataset_summary`
- Tables: `table1_benchmark_method_summary`, `table2_main_frontier`, `table3_oracle_headroom`, `table4_anti_collapse`, `table5_failure_decomposition`, `table6_robustness`

## Final Appendix Artifact Set

- `appendix_output_layer_repair.{pdf,png}` + `appendix_output_layer_repair.csv`
- `appendix_per_dataset_frontier_curves.csv`
- `appendix_per_dataset_frontier_HuggingFaceH4_MATH-500.{pdf,png}`
- `appendix_per_dataset_frontier_Idavidrein_gpqa.{pdf,png}`
- `appendix_per_dataset_frontier_openai_gsm8k.{pdf,png}`

## Regeneration Command

- `python scripts/paper/run_all_neurips_paper_artifacts.py`
