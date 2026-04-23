# REPOSITORY_POLISH_SUMMARY_2026_04_23

## What was cleaned

- Strengthened manuscript-facing front door with a compact paper-writing document set.
- Added explicit source-of-truth, artifact map, claim-evidence discipline, and reproduction checklist.
- Added conservative baseline honesty memo with readiness buckets aligned to current canonical baseline decision package.
- Added terminology and naming policy to reduce method/surface naming drift.

## What was reorganized

- No destructive file moves were performed.
- Preferred approach was additive indexing and policy notes to preserve provenance and avoid breaking paths.
- README/QUICKSTART/docs index updated to point to the new manuscript path.

## Guidance added

- `PAPER_START_HERE.md` for minimal reading path.
- `PAPER_SOURCE_OF_TRUTH.md` for claim-safe citation policy.
- `PAPER_ARTIFACT_MAP.md` and `PAPER_FIGURES_AND_TABLES_PLAN.md` for section-to-artifact mapping.
- `PAPER_REPRODUCTION_CHECKLIST.md` for pre-paper health/repro checks.
- `PAPER_OPEN_GAPS_AND_RISKS.md` for unresolved submission blockers.

## Packaging and development clarity changes

- Clarified dependency split by moving core runtime dependencies into `pyproject.toml` and keeping `requirements.txt` runtime-focused.
- Added `requirements-dev.txt` as explicit developer convenience layer.
- Added `make prepaper` and integrated pre-paper checks in Makefile.

## What remains unresolved

- Broader independent confirmation beyond current bounded passes.
- Full external baseline closure (only a subset currently main-table ready).
- Wider real-model confirmation breadth for stronger generalization claims.

## Recommended workflow before manuscript drafting

1. Run `make prepaper`.
2. Follow `PAPER_START_HERE.md` -> `PAPER_SOURCE_OF_TRUTH.md` -> `PAPER_CLAIMS_AND_EVIDENCE_MAP.md`.
3. Generate/refresh artifact families listed in `PAPER_ARTIFACT_MAP.md`.
4. Keep baseline status wording aligned with `PAPER_BASELINE_HONESTY_STATUS.md`.
5. Explicitly preserve `strict_gate1_cap_k6` vs `strict_f3` surface separation in all draft sections.
