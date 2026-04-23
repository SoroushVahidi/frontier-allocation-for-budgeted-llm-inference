# Outputs directory guide

`outputs/` is an artifact store, not the interpretation authority.

Always pair output inspection with canonical docs before citing results.

## Interpretation classes

### Canonical (paper-facing or current-claim-critical)
Use first when writing manuscript text or summary claims.

- `final_strict_phased_default_decision_eval_20260421T042913Z/`
- `canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/`
- `canonical_matched_surface_regime_breakdown_20260423T012859Z/`
- `matched_surface_multiseed_main_comparison_<timestamp>/`
- `paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/<timestamp>/`
- `paper_facing_baseline_tables/<timestamp>/`
- `paper_plot_data/`
- `paper_figures/`
- `paper_tables/`

### Exploratory/supportive
Useful for mechanism diagnosis and side investigations; do not treat as default claim surface unless a canonical doc promotes them.

Examples:
- `integrated_controller_component_ablation_<timestamp>/`
- `manuscript_surface_component_ablation_<timestamp>/`
- `budget_aware_family_cap_eval_20260421T162842Z/`
- `stop_vs_act_*` families
- `full_method_comparison_bundle/` and similarly bounded comparison bundles

### Historical/provenance
Preserve for traceability; not current project defaults.

Examples:
- older bounded bundles superseded by canonical April 20–23 tracks,
- older import-only baseline attempts that were replaced by newer closure packages,
- pilot or one-off run families with no canonical promotion.

## Canonical paper artifact outputs

These are the only canonical paper-asset output directories:
- `paper_plot_data/`
- `paper_figures/`
- `paper_tables/`

Regeneration entry point:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Mandatory surface distinction

Keep surfaces explicit when citing output folders:
- manuscript-facing matched surface winner: `strict_f3`
- broader operational surface default: `strict_gate1_cap_k6`

## Before citing any folder

Check these docs first:
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `docs/PAPER_ARTIFACT_MAP.md`
- `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
- `docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md`

## Practical rule

If a folder is not explicitly referenced by current canonical docs, treat it as supportive/provenance only.
