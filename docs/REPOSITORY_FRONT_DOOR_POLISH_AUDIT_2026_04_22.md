# Repository Front-Door Polish Audit (2026-04-22)

## Scope

This pass focused on NeurIPS-oriented front-door clarity and navigation consistency, while preserving provenance and avoiding destructive cleanup.

## What was cleaned

- Aligned `README.md`, `docs/README.md`, `docs/REPO_MAP.md`, `scripts/README.md`, `scripts/CANONICAL_START_HERE.md`, and `outputs/README.md` to the same current identity:
  - fixed-budget adaptive test-time compute allocation,
  - strict-phased F1->F2->F3 control discipline,
  - broad default promoted model = `strict_gate1_cap_k6`.
- Added explicit guidance where the repo has two active interpretation surfaces:
  - broad default surface,
  - manuscript-facing matched/fairness surface.

## What was reorganized

- Script front door now explicitly includes manuscript-facing ablation entrypoint:
  - `scripts/run_manuscript_surface_component_ablation.py`
- Added explicit paper-artifact regeneration pointer in script canonical start:
  - `scripts/paper/run_all_neurips_paper_artifacts.py`
- Updated docs index and repo map to include manuscript-surface ablation report and NeurIPS paper-artifact policy doc.

## What was relabeled

- `outputs/README.md` now separates:
  - current-canonical output families,
  - manuscript-facing package families that are generated conditionally,
  - canonical paper artifact outputs vs historical bounded evidence families.
- `docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md` now states explicitly that:
  - `outputs/paper_plot_data/` is canonical for paper reproducibility,
  - but does not replace broad default-decision evidence for repository-wide default claims.
- Paper artifact docs were updated for current file naming reality:
  - `figure1.jpg` (instead of stale `figure1_problem_setup.{pdf,png}` references).

## Intentionally unchanged

- No canonical scientific decision was changed.
- No evidence-producing output family was deleted.
- No historical/provenance bundles were removed.
- Makefile / pyproject / requirements were left structurally unchanged (already lightweight and adequate for current hygiene goals).

## Remaining future work

- Add a compact single-page matrix mapping:
  - claim type -> allowed surface -> allowed artifact families.
- Add lightweight CI check(s) to detect stale file references in front-door docs.
- Continue periodic sync when canonical status docs roll forward to new dates/run IDs.
