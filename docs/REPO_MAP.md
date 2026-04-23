# Repository map

## Purpose

This page maps where to look for canonical interpretation, runnable entry points, and provenance materials.

## Canonical onboarding path

1. `../README.md`
2. `CANONICAL_START_HERE.md`
3. `CANONICAL_EXPERIMENT_STACK.md`
4. `PAPER_SOURCE_OF_TRUTH.md`
5. `../scripts/CANONICAL_START_HERE.md`
6. `CANONICAL_INSTALL_AND_DEV.md`

## Directory roles

- `docs/` — interpretation and policy layer.
  - Canonical: current project/paper truth.
  - Exploratory: bounded analysis and development notes.
  - Historical: provenance-preserving legacy records.
- `scripts/` — runnable entry points and orchestration wrappers.
- `experiments/` — reusable implementation modules used by scripts.
- `configs/` — machine-readable contracts for datasets, baselines, and runs.
- `outputs/` — generated artifacts (never interpretation authority by itself).
- `tests/` — lightweight correctness/regression checks.
- `references/` — literature and citation material.
- `external/` — external baseline integration assets.
- `archive/` — historical/provenance-only preserved material.

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
- Preserve historical artifacts for provenance; do not delete merely for cosmetic cleanup.
