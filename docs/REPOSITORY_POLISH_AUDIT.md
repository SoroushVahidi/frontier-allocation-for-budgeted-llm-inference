# Repository polish audit (NeurIPS 2026 anonymous artifact)

Date: 2026-04-28 (UTC)

## Scope and non-goals

- Kept scientific conclusions and claim boundaries unchanged.
- Preserved method-surface split:
  - manuscript-facing matched-surface representative: `strict_f3`
  - broader operational default on a different surface: `strict_gate1_cap_k6`
- Did not promote diagnostic or real-model artifacts to headline evidence.

## Files changed

- `README.md`
- `QUICKSTART.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
- `docs/REPO_MAP.md`
- `scripts/CANONICAL_START_HERE.md`
- `scripts/README.md`
- `scripts/check_repo_health.py`
- `tests/test_check_repo_health_paths.py` (new)
- `docs/REPOSITORY_POLISH_AUDIT.md` (new)

## What was improved

### Front-door consistency

- Aligned `README.md`, `QUICKSTART.md`, and canonical docs to one evidence hierarchy:
  - canonical paper-facing artifacts from `scripts/paper/run_all_neurips_paper_artifacts.py`
  - supporting/diagnostic/real-model artifacts are non-headline by default unless canonically promoted.
- Added explicit conservative wording to avoid accidental over-claiming.

### Repository navigation

- Expanded `docs/REPO_MAP.md` with explicit roles for:
  - `docs/`, `scripts/`, `scripts/paper/`, `experiments/`, `configs/`, `outputs/`, `tests/`, `references/`, `external/`, `archive/`
  - `manuscript_integration/`, `neurips2026_anonymous_artifact/`, `batch/`, `jobs/`, `logs/`.
- Tightened `scripts/README.md` wording to mark historical index as provenance-only and canonical docs as authority.

### Health checks and reproducibility hygiene

- Updated `scripts/check_repo_health.py` required canonical paths to include:
  - `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
  - `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
  - `scripts/README.md`
  - canonical output roots: `outputs/paper_tables`, `outputs/paper_plot_data`, `outputs/paper_figures`
- Added stable test `tests/test_check_repo_health_paths.py` to verify:
  - front-door claim docs are included in `REQUIRED_PATHS`
  - all required health-check paths currently exist.

## Canonical entry points (confirmed)

- Docs:
  - `docs/CANONICAL_START_HERE.md`
  - `docs/MANUSCRIPT_SUPPORT_DASHBOARD.md`
  - `docs/PAPER_SOURCE_OF_TRUTH.md`
  - `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`
  - `docs/PAPER_OPEN_GAPS_AND_RISKS.md`
- Scripts:
  - `scripts/check_repo_health.py`
  - `scripts/paper/run_all_neurips_paper_artifacts.py`

## Artifact source-of-truth directories

- Canonical paper-facing outputs:
  - `outputs/paper_tables/`
  - `outputs/paper_plot_data/`
  - `outputs/paper_figures/`
- Supporting/diagnostic outputs remain non-headline unless promoted by canonical decision docs.

## Commands run and outcomes

- `python scripts/check_repo_health.py`
  - Outcome: **pass** (`Repository health check: OK`).
- `python -m pytest -q`
  - Outcome: **partial pass / fails present**
  - Summary: `4 failed, 234 passed, 1 skipped`
  - Failure classes:
    1. model pickle/env compatibility mismatch in direct-reserve scorer tests (`numpy`/`sklearn` serialized artifact compatibility; `PCG64` unpickle error),
    2. non-math dataset/feature environment mismatch (`datasets` feature type error),
    3. missing generated non-math output artifact expected by paper-table builder test.
  - Blocking status: **not blocking this doc/navigation polish**, but blocking for a fully green `pytest -q`.
- `python scripts/paper/run_all_neurips_paper_artifacts.py`
  - Outcome: **pass**; canonical paper artifact builder completed and wrote paper table/plot outputs.

## Remaining risks (known)

- Full test suite is not green in this environment due to artifact-version and optional dataset/runtime dependencies.
- Some legacy/historical docs remain verbose by design for provenance; they are now more clearly bounded, but still numerous.
- Real-model/diagnostic outputs continue to require careful claim discipline to prevent accidental headline promotion.

## Archival/removal actions

- No files were deleted in this pass.
- No historical files were removed; provenance-preserving stance maintained.
