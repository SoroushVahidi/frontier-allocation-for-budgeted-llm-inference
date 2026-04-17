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

## Fastest reliable start

If you only read a few files, use this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
3. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
4. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
5. [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)

If you want the shortest repository-facing summary instead, use:
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/EXPERIMENT_LEDGER_2026_04_18.md`](docs/EXPERIMENT_LEDGER_2026_04_18.md)
- [`docs/CONTINUATION_PLAN_2026_04_18.md`](docs/CONTINUATION_PLAN_2026_04_18.md)
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
2. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
3. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
4. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
5. [`docs/PAPER_POSITIONING_NOTE.md`](docs/PAPER_POSITIONING_NOTE.md)
6. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)

### Shortest repository-facing orientation path
Use:
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/EXPERIMENT_LEDGER_2026_04_18.md`](docs/EXPERIMENT_LEDGER_2026_04_18.md)
- [`docs/CONTINUATION_PLAN_2026_04_18.md`](docs/CONTINUATION_PLAN_2026_04_18.md)
- [`docs/REFERENCES_ORGANIZATION_2026_04_18.md`](docs/REFERENCES_ORGANIZATION_2026_04_18.md)
- [`outputs/repository_polish/repository_polish_summary_2026_04_18.json`](outputs/repository_polish/repository_polish_summary_2026_04_18.json)

### Compact repository-facing audit
Use:
- [`docs/FULL_REPOSITORY_AUDIT_AND_POLISH_2026_04_18.md`](docs/FULL_REPOSITORY_AUDIT_AND_POLISH_2026_04_18.md)
- [`outputs/repository_audit/repository_audit_summary_2026_04_18.json`](outputs/repository_audit/repository_audit_summary_2026_04_18.json)
- [`docs/REPOSITORY_POLISH_PASS_2026_04_17.md`](docs/REPOSITORY_POLISH_PASS_2026_04_17.md)

### Runnable code entry path
Start with:
- [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)
- [`scripts/README.md`](scripts/README.md)

### Current hard ambiguous-case line
Read next:
- [`docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`](docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md)
- [`docs/HARD_PAIR_SUPERVISION_CLEANUP_NEXT_STEP.md`](docs/HARD_PAIR_SUPERVISION_CLEANUP_NEXT_STEP.md)
- [`docs/STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md`](docs/STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md)
- [`docs/ORACLE_PROXY_DEFER_TARGET_STATUS.md`](docs/ORACLE_PROXY_DEFER_TARGET_STATUS.md)
- [`docs/DEFER_CONDITIONED_FALLBACK_STATUS.md`](docs/DEFER_CONDITIONED_FALLBACK_STATUS.md)
- [`docs/REPOSITORY_AUDIT_AND_NEXT_STEP_2026_04_18.md`](docs/REPOSITORY_AUDIT_AND_NEXT_STEP_2026_04_18.md)

### Current target-design and value-supervision direction
Use:
- [`docs/RESEARCH_TAKEAWAYS_ON_TARGET_DESIGN_AND_SELECTIVE_ALLOCATION_2026_04_18.md`](docs/RESEARCH_TAKEAWAYS_ON_TARGET_DESIGN_AND_SELECTIVE_ALLOCATION_2026_04_18.md)
- [`docs/RESEARCH_TAKEAWAYS_ON_VALUE_TARGETS_AND_ABSTENTION_2026_04_18.md`](docs/RESEARCH_TAKEAWAYS_ON_VALUE_TARGETS_AND_ABSTENTION_2026_04_18.md)
- `outputs/research_takeaways/research_takeaways_target_design_and_selective_allocation_2026_04_18.json`
- `outputs/research_takeaways/research_takeaways_value_targets_and_abstention_2026_04_18.json`

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
The recommended current direction is:
- a branch-priority / next-step allocation policy over active branches,
- pairwise branch comparison as the main learned decision object,
- `v3` structured ambiguity features and defer-aware representations as the current stronger hard-case line,
- a cleaner selective accept/defer rule for hard ambiguous cases,
- a more principled oracle-proxy defer target rather than only heuristic ambiguity bands,
- and defer-conditioned fallback policies that test what should happen after unresolved states are detected.

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

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the main challenge is learning how to rank active branches and allocate the next unit of compute under uncertainty and limited budget, especially when some states should be treated as unresolved rather than forced into immediate binary commitment.**

A local stop-vs-act gate may still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the project.
