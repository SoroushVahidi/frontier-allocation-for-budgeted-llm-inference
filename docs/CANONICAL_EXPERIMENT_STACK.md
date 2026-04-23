# Canonical experiment stack (compact)

This page is the compact answer to: "What is the current canonical stack for NeurIPS-facing claims?"

## Canonical method identity

- Core setting: fixed-budget adaptive test-time compute allocation.
- Core control: branch-level frontier allocation + answer-group evidence aggregation.
- Core robustness layer: anti-collapse / repeated-same-family control.

## Surface contract (must remain explicit)

- Manuscript-facing matched-surface internal winner: `strict_f3`
- Broader operational default on a different surface: `strict_gate1_cap_k6`

Do not collapse these into a single winner statement.

## Canonical decision docs

1. `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
2. `MANUSCRIPT_METHOD_VS_OPERATIONAL_DEFAULT.md`
3. `FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
4. `PAPER_SOURCE_OF_TRUTH.md`

## Canonical artifact families

- `outputs/matched_surface_multiseed_main_comparison_20260423T235900Z/`
- `outputs/paper_method_decision_bundle_strict_gate1_cap_k6_vs_strict_f3/<timestamp>/`
- `outputs/paper_plot_data/`
- `outputs/paper_figures/`
- `outputs/paper_tables/`

## Canonical script entry points

- `scripts/paper/run_all_neurips_paper_artifacts.py` (primary)
- `scripts/paper/run_all_neurips_artifacts.py` (compatibility alias)

## Interpretation guardrails

- Canonical docs outrank exploratory notes.
- Exploratory artifacts can support mechanism discussion but are not automatic headline evidence.
- Historical/provenance artifacts remain preserved and should not be rewritten as current canonical truth.
