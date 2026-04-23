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
make setup
```

Equivalent manual path:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
# or: pip install -r requirements.txt && pip install -e .[dev]
```

## Default repo-health checks

```bash
make smoke
make health
make lint
make test
```

For the most common pre-commit maintenance pass, run:

```bash
make check
```

For a pre-manuscript gate, run:

```bash
make prepaper
```

## Interpretation rule

For current project interpretation, read in this order:
1. `README.md`
2. `docs/CANONICAL_START_HERE.md`
3. `docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
4. `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
5. `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
6. `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
7. `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
8. `docs/CURRENT_SAFE_CLAIMS.md`
9. `docs/REPO_MAP.md`
10. `CONTRIBUTING.md`
11. `scripts/README.md`
12. `docs/PAPER_START_HERE.md`
13. `docs/PAPER_SOURCE_OF_TRUTH.md`
14. `docs/PAPER_ARTIFACT_MAP.md`

## Directory roles

- `scripts/`: runnable entry points and orchestration wrappers
- `experiments/`: reusable implementation modules and controller logic
- `docs/`: canonical notes, status docs, and supporting references
- `external/`: external baseline notes and integration-facing references
- `references/`: paper/reference summaries and literature-facing provenance notes
- `outputs/`: generated artifacts
- `tests/`: lightweight regression and repo-health tests

## Current best-practice workflow

1. read the canonical docs first,
2. use `CONTRIBUTING.md` before adding new scripts, docs, or output families,
3. pick one runnable script from `scripts/README.md`,
4. write outputs under `outputs/`,
5. keep new method notes in `docs/` before adding large code paths,
6. avoid presenting exploratory notes as canonical project truth.

## Scope note

This document is intentionally practical. It does not replace the main project-planning notes; it tells collaborators how to get oriented and start working without drifting into stale setup assumptions.
