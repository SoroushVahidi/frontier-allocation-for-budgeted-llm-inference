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

## Current interpretation

The repo should currently be interpreted as:
- a **strong research platform**,
- with **active-development method maturity**,
- aimed at a **careful NeurIPS paper story** rather than an overclaimed finished winner.

### What is already strong
- frontier/controller experimentation scaffold,
- anti-collapse controller mechanisms and audits,
- branch-scorer experimentation stack,
- canonical corpus / audit / matched-learning pathways,
- dataset and baseline integration readiness,
- provenance-aware reporting and safe-claim discipline.

### What is not solved yet
- decision-aligned supervision for next-step branch allocation,
- reliable hard-slice behavior on near-tie / adjacent-rank / exact-promoted cases,
- clear broad-vs-aligned separation for external process supervision,
- broad decisive real-model evidence,
- a robust universally winning learned allocator.

## Canonical bottleneck

The main unresolved issue is now best described as:

**decision-aligned supervision quality for budget-aware branch comparison, especially on hard slices.**

That includes:
- proxy-label mismatch,
- noisy branch-comparison targets,
- imperfect opportunity-cost modeling,
- weak held-out support on the hardest slices,
- and incomplete transfer alignment from external process supervision to internal branch-allocation decisions.

The repo’s current view is that it is **not** primarily blocked by:
- missing infrastructure,
- lack of heavier models,
- or lack of larger sweeps by themselves.

## Current method picture

The strongest current method picture is:
- keep **branch-priority / next-step allocation** as the conceptual center,
- treat pairwise and pointwise branch scoring as the main learned objects,
- use stop-vs-act only as a bounded helper view,
- and evaluate progress through matched comparisons on canonical corpora with hard-slice diagnostics.

Internal data and learning now support a serious paper-facing story, but the repo still does **not** support a claim that any learned controller is a robust universal winner.

## External supervision status

The repo now includes a conservative external-supervision path for:
- **PRM800K**,
- **Math-Shepherd**,
- **APPS** (registry-integrated but still environment-caveated).

Current conservative interpretation:
- PRM800K is now technically integrated and non-degenerate,
- PRM-based methods can improve over the internal anchor in rebuilt evaluation families,
- but broad vs aligned PRM usage is still not clearly separated,
- and Math-Shepherd should still wait until evidence quality is stronger on the key hard slices.

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget cross-controller frontier allocation for LLM reasoning, where the main challenge is learning how to rank active branches and allocate the next unit of compute under uncertainty, limited budget, and imperfect supervision.**

A local stop-vs-act gate may still be useful as an implementation simplification, but it should not be treated as the full conceptual center of the project.

## Start here

If you are new to the repo, read these in order:

1. [`docs/PROJECT_MASTER_PLAN.md`](docs/PROJECT_MASTER_PLAN.md)
2. [`docs/CURRENT_PROJECT_STATUS.md`](docs/CURRENT_PROJECT_STATUS.md)
3. [`docs/CURRENT_BOTTLENECKS.md`](docs/CURRENT_BOTTLENECKS.md)
4. [`docs/CURRENT_SAFE_CLAIMS.md`](docs/CURRENT_SAFE_CLAIMS.md)
5. [`docs/PAPER_POSITIONING_NOTE.md`](docs/PAPER_POSITIONING_NOTE.md)
6. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
7. [`docs/README.md`](docs/README.md)
8. [`scripts/README.md`](scripts/README.md)

## Canonical vs exploratory vs historical

- **Canonical**: current status/planning docs, canonical corpora, matched learning passes, and paper-facing evaluation/audit paths.
- **Exploratory**: reliability-aware BT variants, warm-start variants, tie-aware / ambiguity-aware targeted experiments, and narrower diagnostics.
- **Historical**: old binary revise-routing material and superseded memo snapshots.

See [`docs/README.md`](docs/README.md) and [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the exact interpretation rules and collaborator start guidance.
