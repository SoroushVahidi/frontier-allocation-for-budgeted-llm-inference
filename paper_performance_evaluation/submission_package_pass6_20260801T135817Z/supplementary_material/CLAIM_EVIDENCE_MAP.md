# Public Claim-Evidence Map

Updated 2026-08-01 for the public Performance Evaluation artifact boundary.

This map replaces earlier unavailable routes with paths that exist in the public
checkout or in the submission supplement/source ZIPs. It does not claim that the public package can
regenerate proprietary API outputs or reconstruct every historical subset draw. It supports
deterministic verification of the reported aggregate tables and numerical invariants.

## Public Evidence Roots

- Compact matrix audit: `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/`.
- Manuscript source tables: `paper_performance_evaluation/tables/`.
- Manuscript source sections: `paper_performance_evaluation/sections/`.
- Supplementary checks: `paper_performance_evaluation/supplementary_material/`.
- Submission package: `paper_performance_evaluation/submission_package_pass6_20260801T135817Z/`.

## Manuscript-Facing Claims

| Claim | Reported value | Public evidence route |
| --- | --- | --- |
| Completed cells | 15/16 | `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/summary.json`; `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/cell_validation_status.csv`; `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/final_4x4_matrix.csv` |
| Blocked cell | Fireworks x GPQA-Diamond `BLOCKED_PROTOCOL_NONCONVERGENCE` | `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/blocked_cells.csv`; `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/cell_validation_status.csv`; `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/final_4x4_matrix.csv` |
| Completed-cell paired examples | n=3394 | `paper_performance_evaluation/tables/table6_heldout_selector_phase8.tex`; sum of completed-cell `paired_n` values in `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/final_4x4_matrix.csv` |
| Nominal budget | B=6 | `paper_performance_evaluation/sections/05_experimental_setup.tex`; `paper_performance_evaluation/sections/appendix.tex` |
| Pooled-4 aggregate | 2258/3394, 66.53% | `paper_performance_evaluation/tables/table6_heldout_selector_phase8.tex`; per-cell Pooled-4 entries in `paper_performance_evaluation/tables/table1_main_4x4_matrix.tex` |
| FTA aggregate | 2206/3394, 65.00% | `paper_performance_evaluation/tables/table6_heldout_selector_phase8.tex`; FTA columns in `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/final_4x4_matrix.csv` |
| Pooled-4 vs FTA paired test | McNemar p=0.00027; discordants 73/125/3196 | `paper_performance_evaluation/sections/07_search_vs_selection.tex`; exact-binomial recomputation from the reported discordant counts |
| Frontier pooled count | 2176/3394, 64.11% | `paper_performance_evaluation/tables/table6_heldout_selector_phase8.tex`; Frontier columns in `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/final_4x4_matrix.csv` |
| FTA vs Frontier cell signs | 8/6/1 | `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/summary.json`; `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/fta_vs_frontier_paired_stats.csv` |
| FIX-2/FIX-4 switches | 606/21, overlap 0 | `paper_performance_evaluation/sections/appendix.tex`; switch rows in `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/fta_frontier_change_diff_all_cells.csv`; per-cell summaries in `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/selector_behavior_by_cell.csv` |
| Azure FIX-2 transfer harm | 2/18 and 7/31 rescue/regression patterns | `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/selector_behavior_by_cell.csv`; `paper_performance_evaluation/sections/08_provider_analysis.tex` |
| Successful-call reconstruction | 2.78 to 5.38 of nominal B=6 | `paper_performance_evaluation/tables/table3_resource_accounting.tex`; `paper_performance_evaluation/sections/09_compute_accounting.tex` |
| Same-model SC control | Azure x GSM8K Frontier and SC-N=6 both 276/300 | `paper_performance_evaluation/sections/06_main_results.tex`; `paper_performance_evaluation/tables/table1_main_4x4_matrix.tex` |
| Repair asymmetry | Frontier differs on 151/3394 rows; external winner flips 0 | `paper_performance_evaluation/sections/10_ablations.tex`; `paper_performance_evaluation/tables/table4_baseline_fidelity.tex`; `paper_performance_evaluation/sections/appendix.tex` |
| Held-out selector | Pooled-4 selected in 15/15 leave-one-cell-out folds | `paper_performance_evaluation/tables/table6_heldout_selector_phase8.tex`; `paper_performance_evaluation/sections/07_search_vs_selection.tex` |
| Discovery-delta correlation | Pearson r=-0.185 | `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/selector_behavior_by_cell.csv`; `paper_performance_evaluation/sections/06_main_results.tex` |
| Azure x GPQA FTA replay status | Offline replay | `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/azure_gpqa_independent_fta_replay_summary.json`; `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/final_4x4_matrix.csv` |
| No paid calls in compact audit | `false` / NO | `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/api_calls_made.csv`; `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/summary.json` |

## Boundary Notes

- The public release contains aggregate audit records and source tables, not the earlier
  majority-analysis, FIX-ablation, repair-quantification, or chronology directories.
- Oracle rows are upper bounds only.
- Gold labels are offline-only evaluation labels and are not runtime selector features.
- Live API regeneration and complete historical subset reconstruction are outside the public replay
  boundary.
