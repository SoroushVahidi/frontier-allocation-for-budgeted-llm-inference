# adaptive-reasoning-budget-allocation

Repository for the **current NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Canonical project question

> **Which active branch should receive the next unit of compute?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending here, relative to spending it elsewhere?**

## Current repository identity

This repository is currently centered on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches,
- oracle frontier headroom,
- anti-collapse controller design,
- supervision-target quality for allocation decisions.

This repository is **not** currently centered on the old binary revise-routing paper.

## Current leading experimental direction

The shortest current reading of the repo is:
- many recent bounded fixes around the same one-step/local target family were negative,
- the first current direction with a meaningful positive signal is the **multi-step branch-utility target** line,
- but that direction is still **promising, not yet trustworthy**.

Read this note early:
- [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)

If you want the shortest path from current truth to current failure diagnosis, read:
- [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)

If you want the shortest new synthesis of what is done, what is active, and what next, read:
- [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
- [`docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`](docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md)
- [`docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`](docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md)
- [`outputs/repository_polish/current_repo_state_summary_2026_04_18.json`](outputs/repository_polish/current_repo_state_summary_2026_04_18.json)

## Fastest reliable start

If you only read a few files, use this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)
3. [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)
4. [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
5. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
6. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
7. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
8. [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)

If you want the shortest repository-facing summary instead, use:
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/EXPERIMENT_LEDGER_2026_04_18.md`](docs/EXPERIMENT_LEDGER_2026_04_18.md)
- [`docs/CONTINUATION_PLAN_2026_04_18.md`](docs/CONTINUATION_PLAN_2026_04_18.md)
- [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
- [`docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`](docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md)
- [`docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`](docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md)
- [`docs/REPOSITORY_POLISH_PASS_2026_04_17.md`](docs/REPOSITORY_POLISH_PASS_2026_04_17.md)

## What to avoid at first

Do **not** start by reading arbitrary experiment notes, historical memos, or one-off outputs in isolation.

Use these interpretation rules instead:
- **Canonical** docs/scripts define the current project identity.
- **Exploratory** materials are useful active branches, but not the default summary.
- **Historical** materials are provenance-only and should not define the current paper story.

For the formal interpretation rules, see:
- [`docs/README.md`](docs/README.md)
- [`docs/EXPLORATORY_INDEX.md`](docs/EXPLORATORY_INDEX.md)
- [`docs/HISTORICAL_AND_ARCHIVE_POLICY.md`](docs/HISTORICAL_AND_ARCHIVE_POLICY.md)

## Start here by goal

### Fastest correct overview
Read in this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)
3. [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)
4. [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
5. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
6. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
7. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
8. [`docs/PAPER_POSITIONING_NOTE.md`](docs/PAPER_POSITIONING_NOTE.md)
9. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)

### Shortest repository-facing orientation path
Use:
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/EXPERIMENT_LEDGER_2026_04_18.md`](docs/EXPERIMENT_LEDGER_2026_04_18.md)
- [`docs/CONTINUATION_PLAN_2026_04_18.md`](docs/CONTINUATION_PLAN_2026_04_18.md)
- [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)
- [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)
- [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
- [`docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`](docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md)
- [`docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`](docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md)
- [`docs/REFERENCES_ORGANIZATION_2026_04_18.md`](docs/REFERENCES_ORGANIZATION_2026_04_18.md)
- [`outputs/repository_polish/repository_polish_summary_2026_04_18.json`](outputs/repository_polish/repository_polish_summary_2026_04_18.json)
- [`outputs/repository_polish/current_repo_state_summary_2026_04_18.json`](outputs/repository_polish/current_repo_state_summary_2026_04_18.json)

### Compact repository-facing audit
Use:
- [`docs/FULL_REPOSITORY_AUDIT_AND_POLISH_2026_04_18.md`](docs/FULL_REPOSITORY_AUDIT_AND_POLISH_2026_04_18.md)
- [`outputs/repository_audit/repository_audit_summary_2026_04_18.json`](outputs/repository_audit/repository_audit_summary_2026_04_18.json)
- [`docs/REPOSITORY_POLISH_PASS_2026_04_17.md`](docs/REPOSITORY_POLISH_PASS_2026_04_17.md)

### Runnable code entry path
Start with:
- [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)
- [`scripts/README.md`](scripts/README.md)

### Current method and bottleneck path
Read next:
- [`docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`](docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md)
- [`docs/WHAT_IS_NOT_WORKING_NOW.md`](docs/WHAT_IS_NOT_WORKING_NOW.md)
- [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
- [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)
- [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)
- [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
- [`docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`](docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md)

### Evaluation and outputs
Use:
- [`docs/EVALUATION_AND_BASELINES_INDEX.md`](docs/EVALUATION_AND_BASELINES_INDEX.md)
- [`docs/OUTPUTS_INTERPRETATION_GUIDE.md`](docs/OUTPUTS_INTERPRETATION_GUIDE.md)
- [`docs/ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md`](docs/ASSET_AUDIT_AND_WORKING_SET_2026_04_17.md)

### Cleaner collaborator navigation
Use:
- [`docs/REPOSITORY_START_PATHS.md`](docs/REPOSITORY_START_PATHS.md)
- [`docs/README.md`](docs/README.md)

## Current state at a glance

### What is already strong
- frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- dataset and baseline integration readiness,
- oracle-label pilot infrastructure,
- imported manuscript-style evaluation support,
- careful provenance notes and safe-claim discipline.

### What is not solved yet
- robust supervision targets for branch-priority allocation,
- reliable selective pairwise trust/defer control on hard ambiguous cases,
- broad decisive real-model evidence,
- a robust universally winning learned allocator.

### Main bottleneck
The current bottleneck is best described as:

**principled selective pairwise control and supervision design for ambiguous hard cases.**

The current repository view is that the project is **not** primarily blocked by:
- missing infrastructure,
- lack of heavier models,
- or lack of larger sweeps.

### Best near-term method direction
The current best near-term direction is:
- keep the branch-allocation framing,
- treat many recent negative passes as evidence against reusing the same one-step/local target family,
- and validate the **multi-step branch-utility target** line more deeply before broadening again.

The conceptual center is the **ranking/allocation problem**, not a standalone stop-vs-act binary formulation.

## Repository layout

- `docs/`: canonical interpretation, planning notes, grouped navigation pages, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Interpretation rules

- **Canonical**: the current frontier-allocation / branch-allocation path and the docs/scripts that define it.
- **Exploratory**: active method branches and diagnostics that are useful but not the default summary.
- **Historical**: superseded or provenance-only materials that should not be read as the current project identity.

For interpretation rules and grouped navigation, see:
- [`docs/README.md`](docs/README.md)
- [`docs/REPOSITORY_START_PATHS.md`](docs/REPOSITORY_START_PATHS.md)
- [`docs/EXPLORATORY_INDEX.md`](docs/EXPLORATORY_INDEX.md)
- [`docs/HISTORICAL_AND_ARCHIVE_POLICY.md`](docs/HISTORICAL_AND_ARCHIVE_POLICY.md)

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the main challenge is learning how to rank active branches and allocate the next unit of compute under uncertainty and limited budget, and where recent evidence suggests that target locality may be a central part of the remaining hard-case bottleneck.**

A local stop-vs-act gate may still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the project.
