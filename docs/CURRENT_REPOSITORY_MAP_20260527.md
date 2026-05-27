# Current Repository Map (2026-05-27)

## Active Manuscript
- Primary manuscript tree: `paper_applied_intelligence/`
- Legacy trees (non-primary): `paper_ml_journal/`, `paper_ml_journal_snjnl_stage/`

## Active Code and Ops Directories
- `scripts/`
- `experiments/`
- `configs/`
- `batch/`
- `tools/`
- `tests/`

## Generated Output Policy
- `outputs/` is generated-artifact storage.
- Default rule: do not commit generated run outputs unless a small, intentionally curated report is required.
- Never delete/move/overwrite existing outputs during routine polish.

## Current Audit References
- Structure audit root:
  - `outputs/repository_structure_audit_20260527/run_20260527T144834Z/`
- Repo polish run root:
  - `outputs/repo_polish_organization_update_20260527/`

## Cleanliness Warning
- Current branch is significantly dirty; use scoped commits and explicit path lists.
- Prefer commit-by-theme (docs/config vs manuscript vs scripts/tests) over broad staging.
