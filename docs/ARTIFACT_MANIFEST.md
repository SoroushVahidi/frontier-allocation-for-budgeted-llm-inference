# ARTIFACT_MANIFEST

This manifest classifies artifacts for anonymous review safety.

## A) Paper-facing canonical evidence

- Script: `scripts/paper/run_all_neurips_paper_artifacts.py`
- Outputs:
  - `outputs/paper_tables/`
  - `outputs/paper_plot_data/`
  - `outputs/paper_figures/`

No external API keys required.

## B) Appendix/supporting evidence

Representative families:
- anti-collapse calibration sweeps
- non-math external-validity bundles
- ToT-style matched-budget adapter analyses
- fairness/contract checklists

These support interpretation and robustness but are not headline claim anchors.

## C) Exploratory/provenance-only evidence

Representative families:
- real-model Cohere/OpenAI diagnostic bundles and decision packages
- rich failure-trace builders and partial outputs
- case-study algorithm exploration: `strict_f3_case_split_direction_aware_v1`

Status note (offline exploratory):
- `strict_f3_case_split_direction_aware_v1 = 0.5952`
- `strict_f3 = 0.6085`
- Therefore retained as negative/provenance evidence, not promoted.

## D) Non-review/private/local-only artifacts

Examples include local-machine paths, private task metadata, and ad-hoc local run debris. These are tracked in anonymization audit outputs and excluded from paper-facing claims.

## Optional API scripts (not for reviewer reproduction)

Scripts requiring provider APIs (OpenAI/Cohere) are optional and explicitly diagnostic/supporting only.
