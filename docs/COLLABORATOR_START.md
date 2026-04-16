# Collaborator start

This file is the shortest safe entry point for a new collaborator.

## What this repository is about

The canonical project is:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches.

The main question is:

> **Which active branch should receive the next unit of compute?**

## What this repository is not primarily about

This is **not** the old binary revise-routing manuscript repo.

A stop-vs-act gate may still appear in the implementation, but it is a helper mechanism, not the full conceptual center.

## Current project state in one sentence

The repo already has strong infrastructure, experiments, and audits; the main unresolved issue is **supervision target quality for branch allocation**.

## Read these next

1. [`PROJECT_MASTER_PLAN.md`](PROJECT_MASTER_PLAN.md)
2. [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
3. [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
4. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
5. [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md)
6. [`REPO_MAP.md`](REPO_MAP.md)
7. [`../scripts/CANONICAL_START.md`](../scripts/CANONICAL_START.md)

## Practical interpretation rules

- Treat the canonical docs as the source of truth for paper planning.
- Treat exploratory notes as experiment-specific traces, not the default repo story.
- Treat historical notes as provenance only.
- For code, start with the canonical scripts before opening the full script inventory.

## First code paths to know

- `scripts/run_cross_strategy_frontier_allocation.py`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `scripts/run_new_paper_frontier_matrix.py`
- `scripts/run_comparative_frontier_audit.py`

## Working rule for writing and discussion

When describing the repo, center it on:
- frontier allocation,
- branch ranking / next-step allocation,
- anti-collapse controller design,
- supervision-target quality.

Do **not** center it on “should we revise?” or on a generic stop-vs-act story.
