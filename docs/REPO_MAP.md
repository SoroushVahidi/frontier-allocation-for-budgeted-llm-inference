# Repository map

## Purpose

Maps where to find canonical interpretation, runnable entry points, selector artifacts, and provenance material.

## Canonical onboarding path

1. `../README.md`
2. `CURRENT_PROJECT_STATUS.md`
3. `DOCS_INDEX.md`
4. `CANONICAL_START_HERE.md`
5. `REPO_MAP.md`
6. `PAPER_SOURCE_OF_TRUTH.md`
7. `../scripts/CANONICAL_START_HERE.md`
8. `CANONICAL_INSTALL_AND_DEV.md`

## Selector-phase path

Use this path when the task is final-answer selector choosing or L1-defeat work:

1. `SELECTOR_WORK_START_HERE_20260501.md`
2. `SELECTOR_CHOOSING_PLAYBOOK_20260501.md`
3. `ARTIFACT_INDEX_20260501.md`
4. `FOCUSED33_TRACE_ENRICHMENT_RESULT_20260501T000906Z.md`
5. `OUTCOME_VERIFIER_SELECTOR_ROADMAP.md`
6. `FAST_SELECTOR_EXECUTION_POLICY.md`
7. `OUTPUTS_SELECTOR_TRACE_INDEX.md`

## Directory roles

- `docs/` — interpretation and policy layer.
  - Canonical: current project/paper truth.
  - Selector: current L1-defeat work, artifact indexes, selector promotion criteria.
  - Diagnostic: bounded investigations and side branches.
  - Historical: provenance-preserving records.
- `scripts/` — runnable entry points and orchestration wrappers.
- `scripts/paper/` — canonical paper artifact builders for anonymous NeurIPS deliverables.
- `experiments/` — reusable implementation modules used by scripts.
- `configs/` — machine-readable contracts for datasets/baselines/runs.
- `outputs/` — generated artifacts (not interpretation authority by itself).
- `tests/` — lightweight correctness/regression checks.
- `references/` — literature and citation material.
- `external/` — external baseline integration assets.
- `archive/` — preserved historical/provenance material.
- `manuscript_integration/` — manuscript-side integration helpers and packaging bridges.
- `neurips2026_anonymous_artifact/` — anonymous artifact payload staging area.
- `batch/` — Slurm submission scripts for non-interactive cluster runs.
- `jobs/` — job templates and generated scheduler files.
- `logs/` — lightweight run logs and command traces.

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

## Outputs orientation (non-authoritative index)

- Current selector artifact index: [`ARTIFACT_INDEX_20260501.md`](ARTIFACT_INDEX_20260501.md)
- Selector trace usability index: [`OUTPUTS_SELECTOR_TRACE_INDEX.md`](OUTPUTS_SELECTOR_TRACE_INDEX.md)
- Folder-level classes and OV rerank timestamp provenance: [`OUTPUTS_ARTIFACT_INDEX.md`](OUTPUTS_ARTIFACT_INDEX.md)
- Longer policy text: [`../outputs/README.md`](../outputs/README.md)

## Selector vs coverage roadmap

- Current selector choosing checklist: [`SELECTOR_CHOOSING_PLAYBOOK_20260501.md`](SELECTOR_CHOOSING_PLAYBOOK_20260501.md)
- Current focused selector front door: [`SELECTOR_WORK_START_HERE_20260501.md`](SELECTOR_WORK_START_HERE_20260501.md)
- Ordered plan (outcome verifier → PRM → pairwise → coverage-aware): [`SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md`](SELECTOR_AND_COVERAGE_CONTROLLER_ROADMAP_20260429.md)

## Guardrails

- Keep the `strict_f3` vs `strict_gate1_cap_k6` surface distinction explicit.
- Do not treat non-canonical output folders as headline evidence unless promoted by canonical docs.
- Preserve historical artifacts for provenance; demote/label rather than delete.
- For selector work, use existing candidate pools first, dry-run paid call counts, and cache every verifier score.
