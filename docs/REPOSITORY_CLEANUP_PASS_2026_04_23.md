# Repository cleanup pass summary (2026-04-23)

## Scope of this pass

Conservative cleanup and organization pass focused on front-door clarity, doc consistency, and low-risk engineering hygiene for the NeurIPS-facing codebase.

## What was changed

### 1) Front-door simplification

- Simplified top-level onboarding in `README.md`.
- Rewrote `QUICKSTART.md` into a shorter, canonical-first sequence.
- Re-centered `docs/CANONICAL_START_HERE.md` around current scope + explicit guardrails.
- Reduced `docs/FRONT_DOOR.md` to a true redirect page.

### 2) Canonical stack compact summary

- Added `docs/CANONICAL_EXPERIMENT_STACK.md` as a compact canonical stack reference covering:
  - method identity,
  - surface distinction,
  - canonical decision docs,
  - canonical artifact families,
  - canonical runners.

### 3) Documentation consistency and sprawl reduction

- Rewrote `docs/REPO_MAP.md` with clearer role boundaries and fewer stale/duplicated navigation sections.
- Rewrote `docs/CANONICAL_INSTALL_AND_DEV.md` as a practical setup/workflow document.
- Updated `outputs/README.md` to align output interpretation guidance with current canonical runners and claim discipline.
- Rewrote `TODO.md` from stale project-bootstrap tasks into current maintenance backlog items.

### 4) Low-risk engineering improvements

- Updated `scripts/check_repo_health.py` to validate a broader canonical front door and paper runner presence.
- Improved import-failure traceback handling in `scripts/check_repo_health.py`.
- Updated `scripts/smoke_test.py` status messaging to remove stale "early-stage" wording.
- Expanded `tests/test_frontier_router.py` with additional stable unit tests:
  - strategy-order tie-break behavior,
  - multi-class model training path,
  - unmatched prediction handling.

## What was intentionally left unchanged

- No scientific conclusions were changed.
- No method rankings were changed.
- No claim boundaries were changed.
- No canonical-vs-supportive evidence policy was weakened.
- No provenance-critical historical artifacts were deleted.
- No binary files were created.

## Remaining cleanup debt

- Many dated docs remain by design for provenance; periodic indexing/superseded-labeling can continue.
- Additional low-risk link and naming consistency sweeps across the broader docs corpus can be done incrementally.
- Optional future refinement: add a lightweight automated link-check target for canonical docs only.
