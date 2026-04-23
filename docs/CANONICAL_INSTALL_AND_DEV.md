# Canonical install and development

Practical setup + low-friction developer workflow for this repository.

## Environment

- Python >= 3.10
- virtual environment recommended
- run commands from repo root

## Install

```bash
python -m venv .venv
source .venv/bin/activate
make setup
```

## Standard checks

```bash
make smoke
make health
make lint
make test
make check
```

## Pre-paper check bundle

```bash
make prepaper
```

## Minimal orientation sequence

Read (in order):
1. `CANONICAL_START_HERE.md`
2. `CANONICAL_EXPERIMENT_STACK.md`
3. `PAPER_SOURCE_OF_TRUTH.md`
4. `REPO_MAP.md`
5. `../scripts/CANONICAL_START_HERE.md`
6. `../CONTRIBUTING.md`

## Workflow rules

1. Start from canonical docs before running or interpreting experiments.
2. Keep runnable logic in `scripts/` and reusable logic in `experiments/`.
3. Keep generated artifacts in `outputs/`.
4. Preserve claim boundaries and surface distinctions in docs and PRs.
5. Prefer small, scoped, reviewable changes.
