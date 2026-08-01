# Figure and Table Audit - Pass 5

Date: 2026-08-01

Scope: `paper_performance_evaluation/` only. No experiments, live API calls, paid calls, or result
regeneration were run.

## Figures

| Source asset | Manuscript status | Pass 5 action | Scientific/layout assessment |
|---|---|---|---|
| `figures/figure1_protocol_schematic.tex` | Added as Figure 1 | New compact protocol schematic added in the Introduction | Clarifies nominal budget vs realized resources, discovery vs selection, provider-transfer labels, and protocol-blocked outcomes. Pure schematic; no result values invented. Rendered without overlap after removing arrow labels. |
| `figures/figure1_search_vs_selection_concept.pdf` | Not used in manuscript | Removed from manuscript inclusion, file left in place | Scientifically correct but partly duplicated by the new protocol schematic and less complete for Pass 5 goals. |
| `figures/figure5_fta_vs_pooled4_delta_heatmap.pdf` | Retained | Enlarged from `0.62\linewidth` to `0.78\linewidth`; flexible float placement | Necessary main identical-pool selector result. Labels and colorbar readable; no clipping observed. |
| `figures/figure2_fta_frontier_delta_heatmap.pdf` | Retained | Enlarged from `0.55\linewidth` to `0.74\linewidth`; flexible float placement | Necessary provider-transfer/sign-reversal figure. Labels readable; blocked cell explicitly shown. |
| `figures/figure4_accuracy_vs_cost_tradeoff.pdf` | Retained | Enlarged from `0.62\linewidth` to `0.80\linewidth`; flexible float placement | Necessary compute-accounting figure. Open Frontier markers and lower-bound arrows remain legible. |
| `figures/figure3_search_vs_selection_scatter.pdf` | Retained in appendix | Converted from paired minipage to standalone appendix figure at `0.78\linewidth` | Secondary diagnostic; appropriate appendix placement. Labels readable. |

## Tables

| Source asset | Manuscript status | Pass 5 action | Scientific/layout assessment |
|---|---|---|---|
| `tables/table4_baseline_fidelity.tex` | Retained in Experimental Protocol | Refit as compact width-fitted disclosure table; shortened row labels only | Necessary to avoid overclaiming L1/S1/TALE adapter fidelity. Result values unaffected. |
| `tables/table1_main_4x4_matrix.tex` | Retained in main text | Provider names and headers abbreviated; table set at readable `\footnotesize` with tighter columns | Necessary workload landscape. Counts and blocked-cell label unchanged. |
| `tables/table5_compute_matched_phase7.tex` | Retained in main text | Flexible float placement; panel text shortened | Necessary single-cell call/sample-entitlement control. Counts and accuracies unchanged. |
| `tables/table6_heldout_selector_phase8.tex` | Retained in main text | Converted to `tabularx`; shortened header | Necessary leakage-free cell-level selector control. Counts and accuracies unchanged. |
| `tables/table2_provider_fix_analysis.tex` | Retained in main text | Provider names and headers abbreviated; readable `\footnotesize` | Necessary transfer/gate diagnosis. Counts unchanged. |
| `tables/table3_resource_accounting.tex` | Retained in main text | Header shortened; flexible placement | Necessary resource-accounting summary. Resource values unchanged. |
| Appendix inline `tab:frontier-public-params` | Retained in appendix | Converted to `tabularx` for long parameter descriptions | Necessary pseudocode/public-parameter disclosure. Values unchanged. |
| `tables/table7_historical_component_ablation.tex` | Retained in appendix | Converted to `tabularx` | Secondary historical diagnostic; appendix placement appropriate. Values unchanged. |
| `tables/table8_non_math_pilot.tex` | Retained in appendix | Wider provenance column; existing width fit retained | Secondary pilot provenance; appendix placement appropriate. Values unchanged. |
| Appendix inline `tab:same-model-sc` | Retained in appendix | Width-fitted appendix table | Historical partial same-model context; appendix placement appropriate. Values unchanged. |

## Reference and Numbering Check

- All manuscript figures and tables are referenced at least once.
- No duplicate labels found across manuscript, appendix, and table files.
- All substantive displayed equations are numbered.
- One citation cluster with five citations was split into two clusters of four and one.
- Scientific result values and evidence boundaries were not changed.
