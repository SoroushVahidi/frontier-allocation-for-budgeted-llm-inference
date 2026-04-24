# PAPER_ARTIFACT_MAP

Scan-first map for manuscript artifact usage and regeneration provenance.

## A. Main results section

| Artifact family | Purpose | Regeneration script | Interpretation doc |
|---|---|---|---|
| `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/` | broader strict-phased operational default evidence (`strict_gate1_cap_k6`) | `scripts/run_broader_strict_phased_default_decision_eval.py` | `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md` |
| `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/<ts>/` | manuscript-facing decision package between operational default and matched-surface winner | `scripts/run_paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3.py` | `PAPER_METHOD_DECISION_BUNDLE_20260422T175142Z.md` |
| `outputs/matched_surface_multiseed_main_comparison_20260423T235900Z/` | manuscript matched-surface multi-seed stability context | `scripts/run_matched_surface_multiseed_main_comparison.py` | `MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_20260423T235900Z.md` |
| `outputs/paper_figures/`, `outputs/paper_tables/`, `outputs/paper_plot_data/` | final paper-facing figure/table/rendered plotting artifacts | `scripts/paper/run_all_neurips_paper_artifacts.py` | `NEURIPS_PAPER_ARTIFACTS.md` |
| `outputs/unified_claim_safety_statistical_audit_20260424T200000Z/` + `outputs/paper_tables/table_claim_safety_statistical_tests.{csv,tex}` | paper-facing claim-safety statistical boundary table (paired/bootstrap/permutation) | `scripts/paper/build_claim_safety_statistical_table.py` (or via canonical paper runner) | `CLAIM_SAFETY_STATISTICAL_TABLE_NOTE.md` |

## B. Ablations

| Artifact family | Purpose | Regeneration script | Interpretation doc |
|---|---|---|---|
| `outputs/integrated_controller_component_ablation_<ts>/` | broader operational-surface component attribution | `scripts/run_integrated_controller_component_ablation.py` | `INTEGRATED_CONTROLLER_COMPONENT_ABLATION_REPORT_2026_04_22.md` |
| `outputs/manuscript_surface_component_ablation_<ts>/` | matched-surface internal component attribution for `strict_f3` | `scripts/run_manuscript_surface_component_ablation.py` | `MANUSCRIPT_SURFACE_COMPONENT_ABLATION_REPORT_2026_04_22.md` |
| `outputs/component_ablation_strict_f3_paper_surface/<ts>/` | paper-facing packaging of strict_f3 ablation outputs | `scripts/package_strict_f3_component_ablation_paper_surface.py` | `COMPONENT_ABLATION_STRICT_F3_PAPER_SURFACE_20260422T180445Z.md` |

## C. Failure analysis

| Artifact family | Purpose | Regeneration script | Interpretation doc |
|---|---|---|---|
| `outputs/canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/` | canonical exact-loss failure statistics vs strongest internal adversary | `scripts/build_canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics.py` | `CANONICAL_HUNDRED_STRICT_GATE1_CAP_K6_VS_BEST_FAILURE_STATISTICS_20260421T160120Z.md` |
| `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/` | newest-vs-best failure tracking | `scripts/build_new_hundred_newest_vs_best_failure_statistics.py` | `NEW_HUNDRED_NEWEST_VS_BEST_FAILURE_STATISTICS_20260421T032711Z.md` |
| `outputs/twenty_exact_current_full_vs_best_fresh_20260420/` | fine-grained exact fresh slice diagnostics | `scripts/build_twenty_exact_current_full_vs_best_fresh.py` | `TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md` |

## D. Baseline tables

| Artifact family | Purpose | Regeneration script | Interpretation doc |
|---|---|---|---|
| `outputs/paper_facing_baseline_tables/<run_id>/` | manuscript-safe baseline table pack | `scripts/build_paper_facing_baseline_tables.py` | `PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md` |
| `outputs/external_baseline_readiness/<run_id>/` | readiness bucket classification for baseline honesty | `scripts/build_external_baseline_readiness_package.py` | `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md` |
| `outputs/canonical_external_baseline_closure_20260424T000020Z/` | closure summary for baseline readiness/fairness status | `scripts/run_canonical_external_baseline_closure.py` | `CANONICAL_EXTERNAL_BASELINE_CLOSURE_20260424T000020Z.md` |

## E. Appendix / supporting material

| Artifact family | Use policy |
|---|---|
| `outputs/*adjacent_integration*/` | appendix/supportive; adjacent import-validated baselines |
| `outputs/extended_budget_frontier_<run_id>/` | appendix/robustness-only extended budgets (10/12/14); do not replace canonical 4/6/8 main artifacts without explicit promotion |
| `outputs/hundred_*` strict-phased sweeps | supportive mechanism evidence unless promoted explicitly |
| `outputs/hard_max_family_expansions_*` | supportive ablation / mechanism explanation |
| `outputs/imported_methodology_frontier_eval/` | historical/provenance unless explicitly scoped |

## Manuscript usage guardrails

1. Identify target section first (main result, ablation, failure, baseline, appendix).
2. Pick artifact family from this map only.
3. Verify script + doc provenance before citing numbers.
4. Keep surface qualifier on any strict method claim.


## Claim-boundary note

- `strict_f3` vs `strict_gate1_cap_k6` should be reported as fragile/non-decisive on matched-surface slices unless future evidence changes this.
- External baseline comparisons in claim-safety tables are slice-specific and action-budget/matched-substrate constrained; do not phrase them as universal dominance.
