# Repository polish pass (2026-04-17)

## Scope

This note records a **bounded navigation and readability polish pass** for the repository.

The goal of this pass is **not** a large structural reorganization. The repository already has a strong canonical/exploratory/historical separation, and a disruptive move would risk breaking that clarity.

Instead, this pass focuses on:
- making the shortest canonical reading path more obvious,
- reducing first-read confusion for collaborators and future agents,
- clarifying what not to read first,
- and tightening the smallest runnable code entry paths.

## What was changed

### 1. Top-level README polish

The top-level `README.md` now more explicitly provides:
- a **fastest reliable start** path,
- a shorter dashboard-oriented path,
- an explicit **what to avoid at first** section,
- and a clearer pointer to this polish note.

### 2. Documentation index polish

`docs/README.md` now more clearly separates:
- the **shortest reading paths**,
- the canonical truth path,
- the shortest dashboard path,
- the smallest script-entry path,
- and a short **do not start here** warning.

This is intended to reduce the chance that someone starts from isolated experiment notes or historical materials and then misreads the repo identity.

### 3. Script entry-page polish

`scripts/CANONICAL_START_HERE.md` now includes a **smallest runnable path** section for three common intents:
- current paper direction,
- current hard-case bottleneck,
- current value-supervision line.

This makes it easier to choose a first script without scanning the full script index.

## What was intentionally not changed

This pass intentionally did **not**:
- move large groups of files,
- rename major directories,
- collapse exploratory notes into canonical docs,
- or rewrite the repository around a new structure.

Reason: the current repo already has a real interpretive structure. The main problem was more about **entry friction** than about missing folder categories.

## Current organization judgment

The repository is already strong on:
- canonical identity,
- grouped navigation,
- provenance discipline,
- and explicit separation between current, exploratory, and historical material.

The remaining organization risk is mainly:
- too many possible entry points,
- too much dense documentation for first-time readers,
- and accidental overreading of bounded method notes as settled headline conclusions.

## Recommended reading rule after this pass

For almost all collaborators and future execution agents:

1. Start with `README.md`.
2. Then read `docs/CANONICAL_START_HERE.md`.
3. Then read `docs/CURRENT_PROJECT_STATUS.md`, `docs/CURRENT_BOTTLENECKS.md`, and `docs/CURRENT_SAFE_CLAIMS.md`.
4. Only then branch into method-specific or output-specific notes.
5. Use `scripts/CANONICAL_START_HERE.md` before scanning the full script index.

## Recommended maintenance rule

Prefer future polish passes of this form:
- add short continuation-oriented summary docs,
- improve top-level navigation,
- tighten grouped entry points,
- and avoid broad file movement unless there is a very strong reason.

The repo’s main need is continued **interpretive compression**, not aggressive restructuring.

## Conservative conclusion

This bounded pass improves repository usability without changing the project’s conceptual center or creating reorganization risk.

The repository should still be interpreted as:

> a strong research platform for fixed-budget branch allocation in LLM reasoning whose main unresolved issue is supervision semantics and selective ambiguity handling for hard branch comparisons.
