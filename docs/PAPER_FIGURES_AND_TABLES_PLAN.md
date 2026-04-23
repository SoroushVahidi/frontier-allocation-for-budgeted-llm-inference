# PAPER_FIGURES_AND_TABLES_PLAN

Concrete paper artifact planning tied to current repo outputs.

## Main figures/tables (target)

| Section | Artifact family | Generation script | Interpretation doc |
|---|---|---|---|
| Main result: method identity and decision | `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/<ts>/` | `scripts/run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py` | `PAPER_METHOD_DECISION_BUNDLE_20260422T175142Z.md` |
| Main result: canonical plots | `outputs/paper_plot_data/`, `outputs/paper_figures/` | `scripts/paper/run_all_neurips_paper_artifacts.py` | `NEURIPS_PAPER_ARTIFACTS.md`, `FINAL_FIGURE_PACKAGE_REPORT_20260422T181524Z.md` |
| Main result: canonical tables | `outputs/paper_tables/` | `scripts/paper/run_all_neurips_paper_artifacts.py` | `PUBLICATION_TABLES_AND_FINAL_EXPERIMENT_PACKAGE_20260422T235959Z.md` |
| Default operational evidence | `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/` | `scripts/run_broader_strict_phased_default_decision_eval.py` | `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md` |

## Ablations

| Ablation type | Artifact family | Script | Doc |
|---|---|---|---|
| Operational-surface component ablation | `outputs/integrated_controller_component_ablation_<ts>/` | `scripts/run_integrated_controller_component_ablation.py` | `INTEGRATED_CONTROLLER_COMPONENT_ABLATION_REPORT_2026_04_22.md` |
| Manuscript-surface component ablation (`strict_f3`) | `outputs/manuscript_surface_component_ablation_<ts>/` and `outputs/component_ablation_strict_f3_paper_surface/<ts>/` | `scripts/run_manuscript_surface_component_ablation.py`, `scripts/package_strict_f3_component_ablation_paper_surface.py` | `MANUSCRIPT_SURFACE_COMPONENT_ABLATION_REPORT_2026_04_22.md` |

## Failure analysis

| Family | Artifact family | Script | Doc |
|---|---|---|---|
| Exact-loss failure statistics | `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/` | `scripts/build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py` | `CANONICAL_HUNDRED_STRICT_GATE1_CAP_K6_VS_BEST_FAILURE_STATISTICS_20260421T160120Z.md` |
| Current-vs-best fresh slice | `outputs/twenty_exact_current_full_vs_best_fresh_20260420/` | `scripts/build_twenty_exact_current_full_vs_best_fresh.py` | `TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md` |

## Baseline tables

| Family | Artifact family | Script | Doc |
|---|---|---|---|
| Paper-facing baseline tables | `outputs/paper_facing_baseline_tables/<run_id>/` | `scripts/build_paper_facing_baseline_tables.py` | `PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md` |
| Baseline readiness classification | `outputs/external_baseline_readiness/<run_id>/` | `scripts/build_external_baseline_readiness_package.py` | `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md` |

## Appendix/supporting material

- Adjacent/import-validated baseline bundles (`outputs/*adjacent_integration*/`).
- Multiseed robustness bundles (`outputs/matched_surface_multiseed_main_comparison_*`).
- Strict-phased gate/cap diagnostic sweeps (`outputs/hundred_*`, `outputs/hard_max_family_expansions_*`).

## Practical rule

Run paper plot/table generation only after checks in `PAPER_REPRODUCTION_CHECKLIST.md` are green.
