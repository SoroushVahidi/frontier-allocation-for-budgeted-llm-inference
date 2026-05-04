# Repository polish pass — 2026-05-04

## Scope

This was a conservative organization and polish pass. It intentionally avoided deleting, renaming, or rewriting timestamped provenance artifacts under `outputs/`, `archive/`, `logs/`, or cluster-output paths.

## Changes made

- Added `docs/CLAIMS.md` as a compact claim-scope guide for readers, reviewers, and agents.
- Simplified the README fast path so reviewers see reproduction, claims, current status, external-baseline gap, and repo map before historical artifacts.
- Updated `REVIEWER_FIRST.md` to point to `docs/CLAIMS.md` and to state the discovery/coverage bottleneck more directly.
- Refreshed `scripts/check_repo_health.py` so its banner matches the current project name and its required front-door paths include the current claims/status docs.

## Explicit non-changes

- No provenance folders were deleted.
- No timestamped output directories were renamed.
- No result numbers were reinterpreted.
- No selector or method implementation was changed.
- No paid/API scoring was triggered.

## Current preferred reader path

1. `REVIEWER_FIRST.md`
2. `docs/CLAIMS.md`
3. `START_HERE_CURRENT.md`
4. `docs/CURRENT_PROJECT_STATUS.md`
5. `docs/CURRENT_EXTERNAL_BASELINE_GAP.md`
6. `docs/REPO_MAP.md`
7. `docs/PAPER_SOURCE_OF_TRUTH.md`
8. `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`

## Follow-up cleanup candidates

These should be handled in separate reviewable changes:

- Add a small script that reports oversized or local-only artifact candidates without deleting them.
- Split historical docs from current docs more visibly, possibly via `docs/historical/` only if links are updated carefully.
- Tighten lint settings gradually after stabilizing active scripts.
- Add a CI workflow for `make health`, `make reviewer-test`, and `make selector-test` if GitHub Actions is enabled for the repository.
