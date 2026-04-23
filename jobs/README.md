# Jobs directory guide

This directory contains batch/HPC submission wrappers (e.g., `.sbatch` files).

## Purpose

- Preserve reproducible launcher commands for cluster runs.
- Keep long-running or resource-heavy orchestration out of ad hoc shell history.

## Usage notes

- Validate script/config paths locally before cluster submission.
- Keep job names and output paths aligned with `outputs/` family naming.
- Treat these launchers as execution wrappers; canonical interpretation still belongs in `docs/`.

## Related docs

- `docs/CANONICAL_INSTALL_AND_DEV.md`
- `docs/PAPER_REPRODUCTION_CHECKLIST.md`
- `scripts/README.md`
