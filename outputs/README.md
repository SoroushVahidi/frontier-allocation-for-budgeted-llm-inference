# Outputs directory guide

`outputs/` is an artifact store, not interpretation authority.

Always pair artifact reading with canonical docs before making claims.

## Interpretation classes

### Canonical (paper-facing or claim-critical)

Use first for manuscript-facing statements.

- `final_strict_phased_default_decision_eval_20260421T042913Z/`
- `canonical_hundred_strict_gate1_cap_k6_vs_best_failure_statistics_20260421T160120Z/`
- `canonical_matched_surface_regime_breakdown_20260423T012859Z/`
- `matched_surface_multiseed_main_comparison_20260423T235900Z/`
- `paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/<timestamp>/`
- `paper_plot_data/`
- `paper_figures/`
- `paper_tables/`

### Exploratory / supportive

Useful for mechanism work and appendix context; not automatic headline evidence.

Examples:
- `integrated_controller_component_ablation_<timestamp>/`
- `manuscript_surface_component_ablation_<timestamp>/`
- `stop_vs_act_*`
- bounded comparison bundles not promoted by canonical decision docs

### Historical / provenance

Preserved for traceability; not default current evidence.

Examples:
- superseded dated bundles,
- pilot one-off runs,
- legacy integration attempts replaced by newer closure packages.

## Canonical paper artifact generation

Primary runner:

```bash
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Compatibility alias:

```bash
python scripts/paper/run_all_neurips_artifacts.py
```

## Mandatory surface distinction

Keep these separate when interpreting artifacts:
- manuscript-facing matched surface winner: `strict_f3`
- broader operational surface default: `strict_gate1_cap_k6`

## Before citing any output folder

Check:
- `docs/PAPER_SOURCE_OF_TRUTH.md`
- `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
- `docs/PAPER_ARTIFACT_MAP.md`
- `docs/PAPER_BASELINE_HONESTY_STATUS.md`
- `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`

## Current manuscript-support status reminders

- Manuscript-facing internal method remains `strict_f3` on the canonical matched surface.
- `strict_gate1_cap_k6` remains the broader operational default on a separate surface.
- Conditional-risk variant stays supportive/appendix-level unless promoted by a future canonical decision doc.
- Main-table external baseline fairness audit found no material issue for the current near-direct main-table policy (`docs/MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`).
