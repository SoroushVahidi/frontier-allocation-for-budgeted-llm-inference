# Current baseline next steps (2026-04-21)

## Purpose

This note is the shortest current answer to:
- which external baselines are already in the strongest usable state,
- which external baseline should be strengthened next,
- and what the safest integration order is after the default-model lock-in.

## Current repository state

The repository now has a finalized current broad default promoted model on the evaluated strict-phased surface:
- **`strict_gate1_cap_k6`**

So the next major strengthening task is no longer default-model selection.
It is:
- **external-baseline strengthening and closure**.

## Current safest baseline taxonomy summary

Use the normalized v1 taxonomy from:
- `BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`
- `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json`

At a high level:
- **MODE A adapter-based near-direct:** `s1`, `TALE`, `L1`
- **official/import-validated adjacent:** `BEST-Route`, `when_solve_when_verify`, `rest_mcts`, and similar adjacent imports
- **discuss-only:** `Q*`, `Let's Verify Step by Step`, `Rational Metareasoning` and other framing/ingredient references without strong runnable integration

## Current strongest usable external stack

### Near-direct matched-substrate baselines
- **s1 MODE A**
- **TALE MODE A**
- **L1 MODE A**

### Adjacent official baselines already strengthened beyond pure import validation
- **BEST-Route** — stronger than before, but still not stable enough for a full reproduced row in this environment
- **When To Solve / When To Verify** — strengthened adjacent integration lane
- **ReST-MCTS*** — now in the strongest current state among the adjacent search baselines because it reached an honest **partial runnable** status

## Current adjacent execution status

### BEST-Route
Current safest status:
- official
- stronger than pure import validation
- but still **not** a fully reproduced stable run in this environment

Practical current interpretation:
- useful as an adjacent comparator with explicit caveats,
- not yet the strongest clean adjacent baseline for the main external table because its real run path still has unresolved runtime instability.

See:
- `BEST_ROUTE_STRENGTHENING_PASS_2026_04_21.md`
- `BEST_ROUTE_FULL_INTEGRATION_ATTEMPT_20260421T221721Z.md`

### When To Solve / When To Verify
Current safest status:
- official
- import_validated
- adjacent

Strengthening status:
- validator lane kept strict and adjacent-only,
- canonical adjacent runner + comparison contract added,
- output artifact family now mirrors BEST-Route style (`outputs/when_solve_when_verify_adjacent_integration/<run_id>/`).

### ReST-MCTS*
Current safest status:
- official
- adjacent
- **partial runnable**

Why this matters:
- it is now stronger than a pure import-validated row,
- it has an artifact-backed official-code integration lane,
- and it is now ready to appear in the main external-baseline table as an adjacent partial-runnable baseline with explicit caveats.

See:
- `REST_MCTS_PARTIAL_RUNNABLE_INTEGRATION_20260421T225645Z.md`
- `outputs/rest_mcts_partial_runnable_integration_<run_id>/`

## Current next baseline to strengthen

### 1. BEST-Route crash-fix / stabilization pass
This is the current highest-value next external-baseline task.

Why next:
- BEST-Route already has the strongest provenance among the adjacent routing baselines,
- dependency installation and CLI wiring have already been pushed farther than before,
- but the real run path still fails due to runtime instability,
- so the next best move is **stabilization**, not abandoning the baseline.

The goal is not to overclaim full reproduction.
The goal is to upgrade BEST-Route from “stronger than import validation but unstable” into a cleaner **partial runnable** adjacent baseline.

### 2. Q*
Q* is still scientifically important, but it should **not** be the next external baseline to fix before BEST-Route stabilization.

Why:
- closer conceptually to frontier expansion control,
- but higher reproduction and provenance risk,
- no equally clean official integration path in the current repo state,
- more likely to tempt overclaiming via an unofficial adapter.

So Q* remains a **second-wave** or later baseline unless the official-code/provenance situation becomes much stronger.

## Practical strengthening order

Recommended order now:
1. **BEST-Route stabilization / crash-fix pass**
2. **Q*** only after BEST-Route is pushed to its strongest honest state
3. later-wave discuss-only or ingredient references only if their provenance/integration path materially improves

## Current paper-facing guidance

For manuscript-facing text right now:
- treat `s1`, `TALE`, and `L1` as the strongest matched-substrate near-direct external comparisons,
- treat **ReST-MCTS*** as the strongest current adjacent search baseline because it has reached partial-runnable official-code status,
- treat **BEST-Route** as a strengthened adjacent routing baseline that still needs stabilization before it is as clean as ReST-MCTS* for the main table,
- treat `when_solve_when_verify` as a strengthened adjacent comparison lane,
- and treat `Q*` as an important discuss-only or later-wave baseline unless its integration path becomes much stronger.

## Cross-links

Also see:
- `CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
- `main_baselines.md`
- `BASELINE_REPAIR_AND_STATUS_AUDIT_20260420T225833Z.md`
- `CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
