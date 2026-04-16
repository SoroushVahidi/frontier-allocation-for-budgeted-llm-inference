# Repo polish pass — 2026-04-15

This note records the repository-organization pass applied during the current frontier-allocation phase.

## Goal

Improve collaborator onboarding and reduce confusion about:
- the canonical project story,
- the current setup path,
- the difference between canonical and exploratory material,
- and basic repository health expectations.

## What this pass added

### 1) Package/test markers

Added:
- `experiments/__init__.py`
- `tests/__init__.py`

Why:
- make the reusable code/tests layout more explicit,
- reduce ambiguity for local imports and editor tooling,
- and clarify that `experiments/` is part of the active Python code surface.

### 2) Lightweight regression tests

Added:
- `tests/test_frontier_router.py`
- `tests/test_repository_structure.py`

Why:
- give the repo at least a minimal regression floor,
- validate core router-label logic,
- and check that the most important canonical repo files remain present.

### 3) Canonical workflow note

Added:
- `docs/CANONICAL_INSTALL_AND_DEV.md`

Why:
- provide one short collaborator-facing install/dev reference,
- reduce setup drift,
- and make repo-health commands explicit.

## Interpretation after this pass

The repo should still be interpreted primarily through:
- `README.md`
- `docs/README.md`
- `docs/PROJECT_MASTER_PLAN.md`
- `docs/CURRENT_PROJECT_STATUS.md`
- `docs/CURRENT_BOTTLENECKS.md`
- `docs/CURRENT_SAFE_CLAIMS.md`
- `docs/REPO_MAP.md`
- `scripts/README.md`

This polish pass does **not** change the scientific direction. It improves organization and local reliability.

## Remaining cleanup items

The following items still deserve a later cleanup pass if tooling allows direct in-place replacement:

1. synchronize `pyproject.toml`, `requirements.txt`, and the actual runtime imports more tightly,
2. strengthen `scripts/smoke_test.py` from a banner check into a real lightweight health check,
3. expand `Makefile` targets to cover `experiments/` and `tests/` by default,
4. move or label stale snapshot/audit notes more aggressively if they are no longer canonical.

## Conservative status label

After this pass, the repository is better organized and easier to onboard into, but it should still be treated as an **active research codebase**, not a frozen production package.
