# Tests directory guide

This directory contains lightweight repository health and regression tests.

## Purpose

- Protect repository structure/import assumptions.
- Catch lightweight breakage in key scripts and adapters.
- Keep CI/local checks fast enough for frequent use.

## Recommended local checks

```bash
make smoke
make health
make lint
make test
make check
```

## Scope policy

- Tests here should remain lightweight and not trigger expensive experiments.
- Heavy experiment validity belongs in documented artifact bundles, not unit tests.
- If a behavior depends on optional external assets, gate it clearly and keep failure modes explicit.
