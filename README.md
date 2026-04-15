# adaptive-reasoning-budget-allocation

Repository for the **current NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Canonical project question

> **Which active branch should receive the next unit of compute?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending here, relative to spending it elsewhere?**

This repository is no longer centered on the old binary revise-routing paper. Its canonical identity is now:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches,
- oracle frontier headroom,
- anti-collapse controller design,
- supervision-target design for allocation decisions.

## Current interpretation

This repo should currently be interpreted as:
- a **strong research platform**,
- with **active-development method maturity**,
- aimed at a **careful NeurIPS paper story** rather than an overclaimed finished winner.

### What is already strong
- frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- dataset and baseline integration readiness,
- oracle-label pilot infrastructure,
- careful provenance notes and safe-claim discipline.

### What is not solved yet
- robust supervision targets for branch-priority allocation,
- reliable branch-score / continuation calibration across budgets / seeds / datasets,
- broad decisive real-model evidence,
- a robust universally winning learned allocator.

## Main bottleneck

The canonical bottleneck is:

**supervision target quality / proxy-label mismatch for next-step branch allocation.**

The repo’s current view is that the project is **not** primarily blocked by:
- missing infrastructure,
- lack of heavier models,
- or lack of larger sweeps.

## Best near-term method direction

The recommended next method direction is:

- a **branch-priority / next-step allocation policy** over active branches,
- with pairwise or pointwise branch scoring as the main decision mechanism,
- and, if useful, a lightweight local gate that asks whether the current candidate branch really deserves the next unit of budget.

The important conceptual center is the **ranking/allocation problem**, not a standalone stop-vs-act binary formulation.

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the main challenge is learning how to rank active branches and allocate the next unit of compute under uncertainty and limited budget.**

A local stop-vs-act gate may still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the project.

## Canonical reading path

1. [`docs/PROJECT_MASTER_PLAN.md`](docs/PROJECT_MASTER_PLAN.md)
2. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
3. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
4. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
5. [`docs/STOP_VS_ACT_DIRECTION.md`](docs/STOP_VS_ACT_DIRECTION.md)
6. [`docs/NEXT_LIGHTWEIGHT_STEPS.md`](docs/NEXT_LIGHTWEIGHT_STEPS.md)
7. [`docs/LATER_HEAVIER_STEPS.md`](docs/LATER_HEAVIER_STEPS.md)
8. [`docs/EXPERIMENT_STATUS.md`](docs/EXPERIMENT_STATUS.md)
9. [`docs/PAPER_POSITIONING_NOTE.md`](docs/PAPER_POSITIONING_NOTE.md)
10. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
11. [`scripts/README.md`](scripts/README.md)

## Canonical vs exploratory vs historical

- **Canonical now**: the docs listed above and the corresponding frontier-allocation / branch-priority scripts.
- **Exploratory**: reliability-aware BT variants, warm-start variants, tie-aware / ambiguity-aware targeted experiments, and method-specific diagnostic notes.
- **Historical**: old manuscript / binary revise-routing material and dated memo snapshots.

See [`docs/README.md`](docs/README.md) and [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for exact labels and collaborator start guidance.
