# adaptive-reasoning-budget-allocation

Repository for the current **NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Canonical project question

> **Which active branch should receive the next unit of compute, and when should the system continue versus commit?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending on this branch relative to spending it elsewhere, given the current answer-group evidence?**

## Current repository identity

This repository is currently centered on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- next-step branch allocation over active branches,
- answer-group-level commit control,
- useful diversity realization under budget,
- answer-support aggregation,
- and real-model confirmation of branch-allocation policies.

This repository is **not** currently centered on the older binary revise-routing paper.

## Current state in one paragraph

The strongest current repository-backed line remains the **broad diversity-aware branch-allocation family with answer-support aggregation**. The current promoted integrated path adds **anti-collapse allocation**, **soft repeat-expansion control**, and **deterministic output-layer repair**. The codebase now has materially better failure analysis, old-vs-current tree comparison, targeted current-failure bundles, and output-layer repair diagnostics, but it still needs a fresh broad comparison bundle and stronger independent validation before making strong broad-best claims.

## Fastest reliable reading path

Read these first:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`](docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md)
3. [`docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`](docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md)
4. [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
5. [`docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md)
6. [`docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`](docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md)

Then use:
- [`docs/README.md`](docs/README.md) for grouped navigation,
- [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the canonical map,
- [`scripts/README.md`](scripts/README.md) for runnable entry points,
- [`docs/REPOSITORY_AUDIT_AND_CLEANUP_2026_04_20.md`](docs/REPOSITORY_AUDIT_AND_CLEANUP_2026_04_20.md) for the current repo audit/cleanup rationale.

## What to avoid at first

Do **not** start by reading arbitrary one-off status notes or isolated `outputs/` artifacts in isolation.

Use this interpretation rule instead:
- **Canonical** docs define the current project identity.
- **Exploratory** docs preserve active side branches and narrower ideas.
- **Historical** materials are provenance-only and should not define the current paper story.

For the full interpretation policy, see:
- [`docs/README.md`](docs/README.md)
- [`docs/EXPLORATORY_INDEX.md`](docs/EXPLORATORY_INDEX.md)
- [`docs/HISTORICAL_AND_ARCHIVE_POLICY.md`](docs/HISTORICAL_AND_ARCHIVE_POLICY.md)

## What is already strong

- frontier/controller experimentation scaffold,
- diversity-aware controller mechanisms,
- answer-support aggregation infrastructure,
- observability-enabled semantic failure analysis,
- comparative mistake auditing against the strongest baseline,
- bounded real-model confirmation,
- exact old-vs-current tree comparison artifacts,
- targeted current-failure bundles,
- output-layer repair diagnostics,
- and a stronger learner-side supervision stack than before.

## What is not solved yet

- broad-best ranking confirmation for the latest integrated method,
- stronger independent validation beyond targeted repaired subsets,
- honest external-baseline completeness closure,
- stable real-model leadership among close variants,
- broader paper-grade real-model evidence,
- and final current-state comparison closure after the newest integrated updates.

## Main bottleneck

The current bottleneck is now split:
1. in some cases, the correct answer is still absent from the tree;
2. in many targeted current-failure cases, the tree already contains the correct answer but the surfaced/evaluated output layer still needed repair.

## Repository layout

- `docs/`: canonical interpretation, planning notes, navigation pages, reference/baseline indexes, result/artifact indexes, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget branch allocation for LLM reasoning, where early tree shape matters, but the latest repository evidence also shows that some remaining errors are no longer pure search failures and instead live in the final output layer after correct internal reasoning has already been found.**

The repository now has a strong integrated promoted line and a much better exact-failure stack, but it is **not yet in final broad-best-claim shape** because fresh independent validation and a new current full comparison bundle are still needed.
