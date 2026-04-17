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

## Fast start

### If you want the quickest correct overview
Read these first:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/PROJECT_MASTER_PLAN.md`](docs/PROJECT_MASTER_PLAN.md)
3. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
4. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
5. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
6. [`docs/PAPER_POSITIONING_NOTE.md`](docs/PAPER_POSITIONING_NOTE.md)
7. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)

### If you want to run code
Start with:
- [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)
- [`scripts/README.md`](scripts/README.md)

### If you want to understand method bottlenecks
Read next:
- [`docs/HARD_CASE_FEATURE_REPRESENTATION_STATUS.md`](docs/HARD_CASE_FEATURE_REPRESENTATION_STATUS.md)
- [`docs/TARGET_FIDELITY_BRANCH_COMPARISON_STATUS.md`](docs/TARGET_FIDELITY_BRANCH_COMPARISON_STATUS.md)
- [`docs/NEAR_TIE_POINTWISE_EXPERT_STATUS.md`](docs/NEAR_TIE_POINTWISE_EXPERT_STATUS.md)
- [`docs/STRICT_COUPLED_NEAR_TIE_CONTROLLER_STATUS.md`](docs/STRICT_COUPLED_NEAR_TIE_CONTROLLER_STATUS.md)

## What is already strong

- frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- dataset and baseline integration readiness,
- oracle-label pilot infrastructure,
- careful provenance notes and safe-claim discipline.

## What is not solved yet

- robust supervision targets for branch-priority allocation,
- reliable branch-score / continuation calibration across budgets / seeds / datasets,
- broad decisive real-model evidence,
- a robust universally winning learned allocator.

## Main bottleneck

The canonical bottleneck is:

**supervision target quality / proxy-label mismatch for next-step branch allocation.**

The current repository view is that the project is **not** primarily blocked by:
- missing infrastructure,
- lack of heavier models,
- or lack of larger sweeps.

## Best near-term method direction

The recommended current direction is:
- a branch-priority / next-step allocation policy over active branches,
- pairwise or pointwise branch scoring as the main learned decision object,
- and, when useful, a lightweight local gate that asks whether the current candidate branch really deserves the next unit of budget.

The conceptual center is the **ranking/allocation problem**, not a standalone stop-vs-act binary formulation.

## Directory map

- `docs/`: canonical, exploratory, and historical navigation/docs.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy/readme assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: historical/provenance-only material reserved for non-current paths.

## Canonical vs exploratory vs historical

- **Canonical**: the current frontier-allocation / branch-allocation path and the docs/scripts that define it.
- **Exploratory**: active method branches and diagnostics that are useful but not the default summary.
- **Historical**: superseded or provenance-only materials that should not be read as the current project identity.

For interpretation rules, see:
- [`docs/README.md`](docs/README.md)
- [`docs/EXPLORATORY_INDEX.md`](docs/EXPLORATORY_INDEX.md)
- [`docs/HISTORICAL_AND_ARCHIVE_POLICY.md`](docs/HISTORICAL_AND_ARCHIVE_POLICY.md)

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the main challenge is learning how to rank active branches and allocate the next unit of compute under uncertainty and limited budget.**

A local stop-vs-act gate may still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the project.
