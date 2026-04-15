# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- action-conditional branch/controller allocation decisions.

## Directory map

- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `docs/`: canonical status/method notes plus exploratory/historical memos.
- `configs/`: dataset/baseline registries and pilot configs.
- `datasets/`: dataset policy/readme assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts (gitignored provenance outputs).

## Canonical entry points now

### Canonical docs

- `docs/CURRENT_PROJECT_STATUS.md`
- `docs/CURRENT_BOTTLENECKS.md`
- `docs/STOP_VS_ACT_DIRECTION.md`
- `docs/NEXT_LIGHTWEIGHT_STEPS.md`
- `docs/EXPERIMENT_STATUS.md`
- `docs/PAPER_POSITIONING_NOTE.md`

### Canonical scripts

- `scripts/run_cross_strategy_frontier_allocation.py` (legacy filename; canonical frontier scaffold)
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `scripts/run_comparative_frontier_audit.py`
- `scripts/run_new_paper_frontier_matrix.py`

## Classification labels

### Canonical (current path)

- Frontier/controller allocation scaffold and matched evaluation scripts.
- Canonical docs listed above.

### Exploratory (important but not default winners)

- Reliability-aware BT variants.
- External warm-start branch-scorer variants.
- Tie-aware/near-tie targeted variants and diagnostic audits.
- Method-specific one-off notes in `experiments/*result_note.md`.

### Historical

- Old manuscript/binary revise-routing material.
- Dated memo snapshots.
- Earlier high-level docs superseded by current canonical docs.

## Practical collaborator start path

1. Read canonical docs in order from README.
2. Run smoke/integration checks from `scripts/README.md`.
3. Start with bounded experiments from `docs/NEXT_LIGHTWEIGHT_STEPS.md`.
4. Treat heavier plans in `docs/LATER_HEAVIER_STEPS.md` as post-HPC sequence.
