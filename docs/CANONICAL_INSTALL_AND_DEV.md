# Canonical install and development workflow

This note is the canonical setup reference for collaborators during the current frontier-allocation phase.

## Purpose

Use this document when you need the shortest reliable answer to:
- how to install the repo,
- how to run basic repo-health checks,
- how to interpret the current code layout,
- and which commands are the default development workflow.

## Recommended environment

- Python `>=3.10`
- a fresh virtual environment
- repository root as the working directory

## Canonical install path

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .[dev]
```

## Default development checks

```bash
make health
make lint
make test
```

If you want formatting as well:

```bash
make format
```

## Interpretation reading order

Read these before doing substantial work:
1. `README.md`
2. `docs/README.md`
3. `docs/CANONICAL_START_HERE.md`
4. `docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
5. `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
6. `docs/CURRENT_SAFE_CLAIMS.md`
7. `docs/CURRENT_BOTTLENECKS.md`
8. `docs/REPO_MAP.md`
9. `scripts/README.md`

## Directory roles

- `scripts/`: runnable entry points and orchestration wrappers
- `experiments/`: reusable implementation modules and controller logic
- `docs/`: canonical notes, status docs, and supporting references
- `external/`: external baseline notes and integration-facing references
- `outputs/`: generated artifacts
- `tests/`: lightweight regression and repo-health tests

## Best-practice workflow

1. read the canonical docs first,
2. run `make health`,
3. pick one runnable script from `scripts/README.md`,
4. write outputs under `outputs/`,
5. keep new method notes in `docs/` before adding large code paths,
6. avoid presenting exploratory notes as canonical project truth.

## Scope note

This document is intentionally practical. It does not replace the main project-planning notes; it tells collaborators how to get oriented and start working without drifting into stale setup assumptions.
