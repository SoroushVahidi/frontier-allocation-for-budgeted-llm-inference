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

## Current repository decision point

The current strongest repository-backed conclusion is:

- many nearby bounded target/control refinements did **not** clearly displace the multistep-k3 line,
- fresh observability-enabled runs now allow real semantic diagnosis of contested failures,
- and the current highest-value question is now the **target/oracle definition** for hard close-branch states.

The current bounded repository stance is:

> **keep continuation value as the core oracle/target, and augment it with bounded completion-aware evidence only in disagreement slices, especially near-ties.**

## Read this first

If you want the shortest current synthesis, read:
- [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)

Read this note early:
- [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)

If you want the shortest path from current truth to current failure diagnosis, read:
- [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)
- [`docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`](docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md)
- [`docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`](docs/ORACLE_MISMATCH_STUDY_2026_04_18.md)
- [`docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`](docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md)

## Fastest reliable start

If you only read a few files, use this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
3. [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
4. [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)
5. [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)
6. [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
7. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
8. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
9. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
10. [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)

If you want the shortest repository-facing summary instead, use:
- [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/EXPERIMENT_LEDGER_2026_04_18.md`](docs/EXPERIMENT_LEDGER_2026_04_18.md)
- [`docs/CONTINUATION_PLAN_2026_04_18.md`](docs/CONTINUATION_PLAN_2026_04_18.md)
- [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
- [`docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`](docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md)
- [`docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`](docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md)

## What to avoid at first

Do **not** start by reading arbitrary experiment notes, historical memos, or one-off outputs in isolation.

Do **not** assume the next best move is another nearby bounded target/controller tweak.

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
2. [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
3. [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
4. [`docs/CURRENT_LEADING_DIRECTION_2026_04_17.md`](docs/CURRENT_LEADING_DIRECTION_2026_04_17.md)
5. [`docs/DIAGNOSTIC_READING_PATH_2026_04_18.md`](docs/DIAGNOSTIC_READING_PATH_2026_04_18.md)
6. [`docs/PROJECT_SITUATION_REPORT_2026_04_18.md`](docs/PROJECT_SITUATION_REPORT_2026_04_18.md)
7. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
8. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
9. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
10. [`docs/PAPER_POSITIONING_NOTE.md`](docs/PAPER_POSITIONING_NOTE.md)
11. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)

### Shortest repository-facing orientation path
Use:
- [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/EXPERIMENT_LEDGER_2026_04_18.md`](docs/EXPERIMENT_LEDGER_2026_04_18.md)
- [`docs/CONTINUATION_PLAN_2026_04_18.md`](docs/CONTINUATION_PLAN_2026_04_18.md)
- [`docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`](docs/ORACLE_MISMATCH_STUDY_2026_04_18.md)
- [`docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`](docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md)
- [`docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`](docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md)
- [`docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`](docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md)

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
- [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- [`docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`](docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md)
- [`docs/WHAT_IS_NOT_WORKING_NOW.md`](docs/WHAT_IS_NOT_WORKING_NOW.md)
- [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
- [`docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`](docs/ORACLE_MISMATCH_STUDY_2026_04_18.md)
- [`docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`](docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md)
- [`docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`](docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md)

## Current state at a glance

### What is already strong
- frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- dataset and baseline integration readiness,
- oracle-label pilot infrastructure,
- imported manuscript-style evaluation support,
- careful provenance notes and safe-claim discipline,
- fresh observability-enabled semantic failure analysis.

### What is not solved yet
- final frozen target/oracle definition for hard close-branch states,
- broader answer-level validation beyond the bounded contested slice,
- broad decisive real-model evidence under the final target definition,
- a robust universally winning learned allocator under that frozen definition.

### Main bottleneck
The current bottleneck is best described as:

**target-definition clarity for hard close-branch decisions, especially near-tie disagreement states.**

The current repository view is that the project is **not** primarily blocked by:
- missing infrastructure,
- lack of heavier models,
- or lack of larger sweeps.

### Best near-term direction
The current best near-term direction is:
- keep the branch-allocation framing,
- keep continuation value as the core oracle/target,
- study bounded completion-aware correction only in disagreement slices,
- and avoid broad new nearby families until the target-definition question is formally frozen.

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

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the main challenge is learning how to rank active branches and allocate the next unit of compute under uncertainty and limited budget, and where fresh bounded evidence now suggests the key unresolved issue is the target/oracle definition for hard disagreement states rather than another nearby local tweak.**

A local stop-vs-act gate may still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the project.
