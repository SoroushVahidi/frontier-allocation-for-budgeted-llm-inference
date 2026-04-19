# Repository polish and organization (2026-04-19)

## Purpose

This note records a compact assessment of the repository’s current organizational state and the practical cleanup rule for keeping the front door coherent.

It is **not** a new method note. It is a repository-structure note.

## Short assessment

The repository is already strong in the following ways:
- the scientific scope is now much clearer than in earlier phases,
- the broad-family paper direction is explicit,
- the baseline/evaluation surface is well documented,
- many experiment lines already write auditable status notes and machine-readable artifacts,
- and there is a real canonical / exploratory / historical separation rather than one undifferentiated pile of notes.

The main organization problem is no longer missing documentation.
It is the opposite:

> **the front door is too dense, too repetitive, and too easy to overread for a new collaborator.**

In practice this means:
- too many long reading lists appear in multiple places,
- several top-level docs say similar things with slightly different emphasis,
- the shortest collaborator path is harder to see than it should be,
- and narrower method-line notes can look more central than they really are if the reader starts in the wrong place.

## Current organization rule

The repository should be interpreted through this hierarchy:

### 1. Front door / canonical entry
These files should stay short, stable, and mutually consistent:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/REPO_MAP.md`
- `docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`
- `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- `docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`

### 2. Canonical project-state docs
These define what the project currently is and what is safe to claim:
- `docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md`
- `docs/CURRENT_PROJECT_STATUS.md`
- `docs/CURRENT_BOTTLENECKS.md`
- `docs/CURRENT_SAFE_CLAIMS.md`
- `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `docs/WHAT_IS_NOT_WORKING_NOW.md`
- `docs/PAPER_POSITIONING_NOTE.md`

### 3. Evidence / diagnostics docs
These explain why the current interpretation is what it is:
- `docs/FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`
- `docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`
- `docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`
- `docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`
- `docs/main_baselines.md`
- `docs/main_datasets.md`

### 4. Exploratory lines
These are valuable, but they are not the default project identity.
Use them when you need traceability for a specific line, not as the repo summary.

### 5. Historical / provenance material
This should remain available, but should not be part of the front door.

## Practical collaborator path

If a new collaborator asks where to start, the default answer should now be:

1. `README.md`
2. `docs/CANONICAL_START_HERE.md`
3. `docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`
4. `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
5. `docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`
6. `docs/REPO_MAP.md`
7. `scripts/CANONICAL_START_HERE.md`

That is enough to understand the project without reading dozens of notes first.

## Current maintenance rule

When the project phase changes materially, update the following together:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/REPO_MAP.md`
- `docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`
- `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- `docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`
- this file

This prevents the common failure mode where the repo’s scientific center changes, but the front door still points readers toward an older interpretation.

## Practical cleanup decision from this pass

This pass does **not** try to reorganize every note in the repository.
Instead, it enforces a narrower and more useful rule:

> **keep the front door short, keep the canonical reading path explicit, and let exploratory notes remain detailed without pretending they are the default entry path.**

## Recommendation

The repository does **not** need a broad structural refactor right now.
It mainly needs discipline about:
- which notes define the current truth,
- which notes are only evidence traces,
- and which files a collaborator should read first.

That is now the active organization standard for the repository.
