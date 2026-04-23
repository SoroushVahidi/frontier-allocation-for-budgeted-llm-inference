# Experiments directory guide

This directory contains implementation modules and compact experiment/result notes.

## Role

- Keep experiment logic close to method components.
- Preserve lightweight result-note provenance for local runs.
- Avoid treating single note files here as canonical manuscript truth by default.

## Interpretation

- **Canonical interpretation lives in `docs/`**, especially `docs/CANONICAL_START_HERE.md`, `docs/PAPER_SOURCE_OF_TRUTH.md`, and `docs/PAPER_CLAIMS_AND_EVIDENCE_MAP.md`.
- Files in `experiments/` are implementation/provenance support unless explicitly promoted by canonical docs.

## Conventions

- Prefer clear, surface-aware naming.
- Keep deterministic assumptions explicit in matching notes.
- Do not delete older notes that still carry provenance; mark superseded status in docs instead.

## Related navigation

- `scripts/README.md` for runnable entry points.
- `outputs/README.md` for artifact-family interpretation.
- `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md` for experiment-family context.
