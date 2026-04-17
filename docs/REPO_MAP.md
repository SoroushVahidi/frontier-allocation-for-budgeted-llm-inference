# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- budget-conditioned stop-vs-act control,
- oracle frontier headroom and anti-collapse design.

## Fast start

- Start here: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Then use [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md) for runnable entry points.
- For non-default active lines, see [`EXPLORATORY_INDEX.md`](EXPLORATORY_INDEX.md).
- For provenance-only interpretation, see [`HISTORICAL_AND_ARCHIVE_POLICY.md`](HISTORICAL_AND_ARCHIVE_POLICY.md).

## Directory map

- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `docs/`: canonical status / planning notes plus exploratory and historical guidance.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy/readme assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: preserved historical / provenance-only material.

## Canonical docs now

1. `docs/PROJECT_MASTER_PLAN.md`
2. `docs/CURRENT_PROJECT_STATUS.md`
3. `docs/CURRENT_BOTTLENECKS.md`
4. `docs/CURRENT_SAFE_CLAIMS.md`
5. `docs/STOP_VS_ACT_DIRECTION.md`
6. `docs/NEXT_LIGHTWEIGHT_STEPS.md`
7. `docs/LATER_HEAVIER_STEPS.md`
8. `docs/EXPERIMENT_STATUS.md`
9. `docs/PAPER_POSITIONING_NOTE.md`
10. `docs/REPO_MAP.md`

## Canonical scripts now

### Current paper path / controller path
- `scripts/run_cross_strategy_frontier_allocation.py`
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `scripts/run_new_paper_frontier_matrix.py`
- `scripts/run_comparative_frontier_audit.py`
- `scripts/run_new_paper_stop_vs_act_controller.py`
- `scripts/run_new_paper_stop_vs_act_target_stabilization_pass.py`
- `scripts/run_new_paper_stop_vs_act_matched_comparator_pass.py`
- `scripts/run_new_paper_stop_vs_act_policy_coupled_stop_pass.py`

### Supporting active lines
- pairwise BT branch-scorer pipelines,
- reliability-aware and tie-aware variants,
- oracle-label pilot and selective-distillation protocols,
- real-model pilot scripts,
- external baseline integration tooling.

## Classification labels

### Canonical
- frontier/controller allocation scaffold,
- stop-vs-act controller direction,
- canonical status / planning docs,
- matched evaluation and audit pathways.

### Exploratory
- reliability-aware BT variants,
- external warm-start lines,
- tie-aware / ambiguity-aware variants,
- one-off method notes and narrower audits.

### Historical
- old manuscript / binary revise-routing material,
- dated memos superseded by the current canonical docs,
- provenance-only assets that should not define the current project.

## Practical collaborator start path

1. Read the canonical docs in order from `docs/CANONICAL_START_HERE.md`.
2. Use `scripts/CANONICAL_START_HERE.md` to find current runnable entry points.
3. Treat exploratory notes as evidence traces, not as the default project interpretation.
4. When writing the paper, use `CURRENT_SAFE_CLAIMS.md` and `PAPER_POSITIONING_NOTE.md` as first constraints.
