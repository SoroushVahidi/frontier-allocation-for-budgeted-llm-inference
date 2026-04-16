# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- branch-priority / next-step allocation over active branches,
- oracle frontier headroom,
- anti-collapse controller design.

## What this map is for

Use this file to answer three questions quickly:
1. What part of the repo is canonical?
2. Where should a collaborator start?
3. Which scripts matter first for the current paper path?

## Directory map

- `docs/` — canonical project interpretation, bottlenecks, safe claims, planning notes, and supporting references.
- `scripts/` — runnable entry points and orchestration wrappers.
- `experiments/` — implementation modules and compact experiment/result notes.
- `configs/` — dataset, baseline, and experiment configuration files.
- `datasets/` — dataset policy/readme assets.
- `external/` — external baseline references and integration notes.
- `outputs/` — generated artifacts, audits, and paper-support outputs.

## Canonical collaborator path

A new collaborator should follow this order:

1. Read [`COLLABORATOR_START.md`](COLLABORATOR_START.md).
2. Read [`PROJECT_MASTER_PLAN.md`](PROJECT_MASTER_PLAN.md).
3. Read [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md).
4. Read [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md).
5. Read [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md).
6. Read [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md).
7. Read [`../scripts/CANONICAL_START.md`](../scripts/CANONICAL_START.md).
8. Use [`../scripts/README.md`](../scripts/README.md) only after the canonical path is clear.

## Canonical scripts now

These are the main current-paper entry points.

### Primary frontier / controller path
- `scripts/run_cross_strategy_frontier_allocation.py`
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `scripts/run_new_paper_frontier_matrix.py`
- `scripts/run_comparative_frontier_audit.py`

### Local stop-vs-act helper path
- `scripts/run_new_paper_stop_vs_act_controller.py`
- `scripts/run_new_paper_stop_vs_act_target_stabilization_pass.py`
- `scripts/run_new_paper_stop_vs_act_matched_comparator_pass.py`
- `scripts/run_new_paper_stop_vs_act_policy_coupled_stop_pass.py`

## Classification labels

### Canonical
- frontier/controller allocation scaffold,
- branch-priority / next-step allocation work,
- canonical status / planning docs,
- matched evaluation and audit pathways,
- paper-facing baseline-integration status.

### Exploratory
- reliability-aware BT variants,
- external warm-start lines,
- tie-aware / ambiguity-aware variants,
- one-off method notes and narrower audits.

### Historical
- old manuscript / binary revise-routing material,
- dated memos superseded by the current canonical docs.

## Practical rule

When in doubt:
- use the docs in the canonical order,
- treat exploratory notes as evidence traces rather than the default repo interpretation,
- and use the canonical scripts before opening the larger script inventory.
