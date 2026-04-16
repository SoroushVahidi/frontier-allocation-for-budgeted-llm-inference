# adaptive-reasoning-budget-allocation

Repository for the **current NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Canonical project question

> **Which active branch should receive the next unit of compute?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending here, relative to spending it elsewhere?**

This repository is **not** centered on the older binary revise-routing paper. Its canonical identity is now:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches,
- oracle frontier headroom,
- anti-collapse controller design,
- supervision-target design for allocation decisions.

## What this repository already provides

- frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation paths,
- local gate / stop-vs-act dataset, train, and eval machinery,
- dataset and baseline integration readiness,
- oracle-label pilot infrastructure,
- provenance-aware reporting and safe-claim discipline.

## Main unresolved issue

The current bottleneck is:

**supervision target quality / proxy-label mismatch for next-step branch allocation.**

The repo’s current interpretation is that the project is **not** primarily blocked by missing infrastructure or by simply needing larger sweeps.

## Best current method direction

The strongest near-term direction is:
- a **branch-priority / next-step allocation policy** over active branches,
- with pairwise or pointwise branch scoring as the main learned object,
- optionally supported by a lightweight local gate that asks whether the current candidate really deserves the next unit of budget.

The conceptual center is the **ranking/allocation problem**, not a standalone stop-vs-act story.

## Repository layout

- `docs/` — canonical project status, planning notes, bottlenecks, safe claims, and supporting references.
- `scripts/` — runnable entry points and orchestration wrappers.
- `experiments/` — implementation modules and compact result notes.
- `configs/` — dataset, baseline, and experiment configuration files.
- `datasets/` — dataset policy/readme assets.
- `external/` — external baseline references and integration notes.
- `outputs/` — generated artifacts and paper-support outputs.

## Start here

If you are new to the repo, read these in order:

1. [`docs/COLLABORATOR_START.md`](docs/COLLABORATOR_START.md)
2. [`docs/PROJECT_MASTER_PLAN.md`](docs/PROJECT_MASTER_PLAN.md)
3. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
4. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
5. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
6. [`docs/PAPER_POSITIONING_NOTE.md`](docs/PAPER_POSITIONING_NOTE.md)
7. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
8. [`scripts/CANONICAL_START.md`](scripts/CANONICAL_START.md)
9. [`scripts/README.md`](scripts/README.md)

## Canonical vs exploratory vs historical

- **Canonical**: frontier-allocation / branch-priority work, canonical status docs, matched evaluation/audit paths, and the current paper-facing scripts.
- **Exploratory**: reliability-aware BT variants, warm-start variants, tie-aware and ambiguity-aware experiments, and narrower diagnostics.
- **Historical**: old binary revise-routing material and superseded memo snapshots.

See [`docs/README.md`](docs/README.md) and [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the exact interpretation rules.
