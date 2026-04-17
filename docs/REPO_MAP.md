# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- next-step branch allocation over active branches,
- oracle frontier headroom and anti-collapse design.

## Fast start

- Start here: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Then use [`REPOSITORY_START_PATHS.md`](REPOSITORY_START_PATHS.md) for goal-based navigation.
- Then use [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md) for runnable entry points.
- For grouped method notes, see [`METHOD_STATUS_INDEX.md`](METHOD_STATUS_INDEX.md).
- For grouped evaluation/baseline notes, see [`EVALUATION_AND_BASELINES_INDEX.md`](EVALUATION_AND_BASELINES_INDEX.md).
- For non-default active lines, see [`EXPLORATORY_INDEX.md`](EXPLORATORY_INDEX.md).
- For provenance-only interpretation, see [`HISTORICAL_AND_ARCHIVE_POLICY.md`](HISTORICAL_AND_ARCHIVE_POLICY.md).

## Directory map

- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `docs/`: canonical status / planning notes plus grouped method/evaluation indexes, exploratory notes, and historical guidance.
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
5. `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
6. `docs/WHAT_IS_NOT_WORKING_NOW.md`
7. `docs/PAPER_POSITIONING_NOTE.md`
8. `docs/REPO_MAP.md`

## Current hard-case / ambiguity docs

- `docs/HARD_PAIR_SUPERVISION_CLEANUP_NEXT_STEP.md`
- `docs/STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md`
- `docs/ORACLE_PROXY_DEFER_TARGET_STATUS.md`
- `docs/DEFER_CONDITIONED_FALLBACK_STATUS.md`
- `docs/REPOSITORY_AUDIT_AND_NEXT_STEP_2026_04_18.md`

## Grouped navigation pages

- `docs/METHOD_STATUS_INDEX.md`
- `docs/EVALUATION_AND_BASELINES_INDEX.md`
- `docs/REPOSITORY_START_PATHS.md`
- `scripts/HISTORICAL_INDEX.md`

## Canonical scripts now

### Current paper path / controller path
- `scripts/run_cross_strategy_frontier_allocation.py`
- `scripts/run_multi_action_allocation_pass.sh`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `scripts/run_new_paper_frontier_matrix.py`
- `scripts/run_comparative_frontier_audit.py`
- `scripts/run_imported_methodology_frontier_eval.py`

### Current hard-case / data-quality line
- `scripts/build_bruteforce_target_regimes.py`
- `scripts/train_bruteforce_branch_allocator.py`
- `scripts/run_target_fidelity_regime_experiment.py`
- `scripts/run_hard_case_feature_representation_experiment.py`
- `scripts/run_ambiguity_calibration_and_fallback_experiment.py`
- `scripts/run_near_tie_policy_experiment.py`
- `scripts/run_near_tie_pointwise_expert_experiment.py`
- `scripts/run_pairwise_svm_margin_experiment.py`
- `scripts/run_structured_ambiguity_experiment.py`
- `scripts/run_defer_fallback_experiment.py`

### Supporting active lines
- pairwise BT branch-scorer pipelines,
- reliability-aware and tie-aware variants,
- oracle-label pilot and selective-distillation protocols,
- external baseline integration tooling.

## Classification labels

### Canonical
- frontier/controller allocation scaffold,
- branch-priority / next-step allocation framing,
- canonical status / planning docs,
- matched evaluation and audit pathways,
- structured ambiguity, oracle-proxy defer, and defer-conditioned fallback work as the current hard-case line.

### Exploratory
- reliability-aware BT variants,
- external warm-start lines,
- tie-aware / ambiguity-aware variants,
- one-off method notes and narrower audits.

### Historical
- old manuscript / binary revise-routing material,
- dated memos superseded by the current canonical docs,
- archived historical script entry points,
- provenance-only assets that should not define the current project.

## Practical collaborator start path

1. Read the canonical docs in order from `docs/CANONICAL_START_HERE.md`.
2. Use `docs/REPOSITORY_START_PATHS.md` for the shortest path matching your goal.
3. Use `docs/METHOD_STATUS_INDEX.md` or `docs/EVALUATION_AND_BASELINES_INDEX.md` depending on your question.
4. Use `scripts/CANONICAL_START_HERE.md` to find current runnable entry points.
5. Treat exploratory notes as evidence traces, not as the default project interpretation.
6. When writing the paper, use `CURRENT_SAFE_CLAIMS.md` and `PAPER_POSITIONING_NOTE.md` as first constraints.
