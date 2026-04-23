# PAPER_SOURCE_OF_TRUTH

This page defines which files are safe to cite for manuscript claims.

## Source-of-truth hierarchy

1. **Canonical decision docs** (first authority).
2. **Canonical generated artifact families** (must match decision docs).
3. **Supportive diagnostics** (only for mechanism explanation / appendix).
4. **Historical/provenance notes** (not headline evidence).

## Canonical authority set (paper-facing)

- `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
- `MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`
- `FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `PAPER_METHOD_DECISION_BUNDLE_20260422T175142Z.md`
- `MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_20260423T235900Z.md`
- `CONDITIONAL_RISK_CAP_MANUSCRIPT_PROMOTION_DECISION_20260423T203259Z.md`
- `CONDITIONAL_RISK_CAP_PROMOTION_DECISION_CONFIRMATION_20260423.md`
- `FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
- `EXTERNAL_BASELINE_PAPER_READINESS_DECISION_PACKAGE.md`
- `PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`
- `MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`

## Canonical artifact families (paper-facing)

- `outputs/final_strict_phased_default_decision_eval_20260421T042913Z/`
- `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/<timestamp>/`
- `outputs/matched_surface_multiseed_main_comparison_20260423T235900Z/`
- `outputs/matched_surface_multiseed_main_comparison_20260423T203259Z/` (conditional-risk promotion-decision supplement)
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`
- `outputs/paper_facing_baseline_tables/<run_id>/`

## Supportive-only families (do not over-claim)

- `outputs/integrated_controller_component_ablation_*/`
- `outputs/manuscript_surface_component_ablation_*/`
- `outputs/new_hundred_newest_vs_best_failure_statistics_20260421T032711Z/`
- `outputs/hundred_*` strict-phased diagnostics and gate sweeps
- `outputs/*adjacent_integration*/` external adjacent adapters

Use these for ablations, mechanism discussion, or appendix context unless promoted by a canonical decision document.

## Historical/provenance-only

- `archive/`
- superseded dated docs not linked by canonical front-door pages
- older bounded surfaces explicitly marked as legacy/historical in `outputs/README.md` or `docs/HISTORICAL_AND_ARCHIVE_POLICY.md`

## Canonical status notes

- Conditional-risk variant remains supportive/appendix-level and does not replace the canonical manuscript-facing method lock (`strict_f3`).
- External main-table baseline fairness audit outcome: no material issue found on the current near-direct main-table comparison surface.

## Claim discipline

A claim is manuscript-safe only if:
1. It appears in, or is directly implied by, a canonical authority doc.
2. Its supporting artifacts are in canonical artifact families.
3. Surface scope is explicit (broader operational vs matched manuscript-facing).
