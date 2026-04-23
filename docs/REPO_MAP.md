# Repository map

## Purpose

Maps where to find canonical interpretation, runnable entry points, and provenance material.

## Canonical onboarding path

1. `../README.md`
2. `CANONICAL_START_HERE.md`
3. `MANUSCRIPT_SUPPORT_DASHBOARD.md`
4. `PAPER_SOURCE_OF_TRUTH.md`
5. `../scripts/CANONICAL_START_HERE.md`
6. `CANONICAL_INSTALL_AND_DEV.md`

## Directory roles

- `docs/` — interpretation and policy layer.
  - Canonical: current project/paper truth.
  - Exploratory: bounded investigations and side branches.
  - Historical: provenance-preserving records.
- `scripts/` — runnable entry points and orchestration wrappers.
- `experiments/` — reusable implementation modules used by scripts.
- `configs/` — machine-readable contracts for datasets/baselines/runs.
- `outputs/` — generated artifacts (not interpretation authority by itself).
- `tests/` — lightweight correctness/regression checks.
- `references/` — literature and citation material.
- `external/` — external baseline integration assets.
- `archive/` — preserved historical/provenance material.

## Manuscript-support documents

- Source of truth: `PAPER_SOURCE_OF_TRUTH.md`
- Artifact policy: `NEURIPS_PAPER_ARTIFACTS.md`, `../outputs/README.md`
- Promotion/decision outcome: `INTERNAL_METHOD_FINAL_DECISION_PACKAGE_2026_04_22.md`
- Matched-surface rerun: `MATCHED_SURFACE_MULTI_SEED_MAIN_COMPARISON_20260423T235900Z.md`
- Conditional-risk status (supportive, not replacement):
  - `CONDITIONAL_RISK_CAP_MANUSCRIPT_PROMOTION_DECISION_20260423T203259Z.md`
  - `CONDITIONAL_RISK_CAP_PROMOTION_DECISION_CONFIRMATION_20260423.md`
- Baseline fairness outcome: `MAIN_TABLE_EXTERNAL_BASELINE_FAIRNESS_AUDIT_20260423T205134Z.md`

## Paper-facing runners

- Primary: `../scripts/paper/run_all_neurips_paper_artifacts.py`
- Compatibility alias: `../scripts/paper/run_all_neurips_artifacts.py`

## Paper-facing output roots

- `../outputs/paper_plot_data/`
- `../outputs/paper_figures/`
- `../outputs/paper_tables/`

## Guardrails

- Keep the `strict_f3` vs `strict_gate1_cap_k6` surface distinction explicit.
- Do not treat non-canonical output folders as headline evidence unless promoted by canonical docs.
- Preserve historical artifacts for provenance; demote/label rather than delete.
