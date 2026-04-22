# External adjacent baseline bundle (2026-04-22T01:14:00Z)

## Purpose

This note introduces a manuscript-safe aggregate reporting layer for the strengthened **official adjacent external baselines**:

- BEST-Route
- when_solve_when_verify
- Let's Verify Step by Step
- ReST-MCTS*

It consolidates existing integration/status artifacts into one paper-facing bundle without changing any underlying baseline lane semantics.

## Why these are grouped together

These three baselines are all currently treated as:

- official upstream references with auditable provenance,
- integrated through import-validation and/or partial-runnable adjacent lanes,
- reviewer-relevant for adaptive reasoning/control comparisons,
- **adjacent** rather than direct control-equivalent frontier-allocation baselines.

## Important taxonomy separation (manuscript guardrail)

Keep this split explicit in paper text and tables:

- **Near-direct matched-substrate adapters:** `s1` MODE A, `TALE` MODE A, `L1` MODE A (`adapter_based`, `near_direct`).
- **Official adjacent external baselines:** BEST-Route, when_solve_when_verify, ReST-MCTS* (`import_validated`, `adjacent` in the normalized matrix).

Do not collapse the adjacent family into near-direct MODE A rows.

## Canonical aggregate artifact bundle

Generated bundle:

- `outputs/external_adjacent_baseline_bundle/20260422T011400Z/summary.json`
- `outputs/external_adjacent_baseline_bundle/20260422T011400Z/summary.csv`
- `outputs/external_adjacent_baseline_bundle/20260422T011400Z/summary.md`
- `outputs/external_adjacent_baseline_bundle/20260422T011400Z/manuscript_table.csv`
- `outputs/external_adjacent_baseline_bundle/20260422T011400Z/README.md`

Builder script:

```bash
python scripts/build_external_adjacent_baseline_bundle.py
```

## Current safest aggregate classification

- `best_route_microsoft`: official, `import_validated`, `adjacent`.
- `when_solve_when_verify`: official, `import_validated`, `adjacent`.
- `lets_verify_step_by_step`: official, `import_validated`, `adjacent` with a stabilized `partial_runnable_adjacent` lane (`scripts/run_lets_verify_step_by_step_adjacent_integration.py`, contract v1, canonical artifacts) while full paper-stack reproduction remains out of scope.
- `rest_mcts`: official, `import_validated`, `adjacent` with a stabilized `partial_runnable_adjacent` lane (`scripts/run_rest_mcts_adjacent_integration.py`, contract v2, canonical artifacts) while full self-training reproduction remains out of scope.

## Safe manuscript scope for this family

Safe now:

- report these as **official adjacent** baselines with artifact-backed import-validation status,
- include them in adjacent comparison tables with explicit `adjacent_only` scope,
- cite their limitations directly in table notes.

Out of scope now:

- claiming control-space equivalence to branch-level marginal budget allocation,
- claiming full faithful in-repo reproduction of all upstream training/inference stacks,
- merging adjacent rows with near-direct MODE A rows in one undifferentiated “direct baseline” block.

## Manuscript-safe paragraph (ready to reuse)

> We report BEST-Route, When To Solve/When To Verify, Let's Verify Step by Step, and ReST-MCTS* as **official adjacent external baselines** with conservative, artifact-backed integration status. In this repository they are used under import-validated/partial-runnable adjacent protocols for reviewer-defensible comparison context, but they are not treated as direct control-equivalent substitutes for our branch-level marginal budget-allocation objective. We therefore keep these adjacent rows explicitly separated from near-direct matched-substrate MODE A baselines (s1/TALE/L1) and avoid full in-repo faithful-reproduction claims.
