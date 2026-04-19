# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- next-step branch allocation over active branches,
- answer-group-level commit control,
- useful diversity realization under budget,
- and target/oracle quality for hard close-branch decisions.

This repository is **not** currently centered on the older binary revise-routing framing.

## Fast start

- Start here: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Then read: [`CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`](CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md)
- Then read: [`PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md`](PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md)
- Then read: [`CURRENT_EXPERIMENT_RULE_2026_04_18.md`](CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- Then use: [`REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](REPOSITORY_MASTER_DASHBOARD_2026_04_18.md) for the shortest dashboard.
- Then use: [`REPOSITORY_START_PATHS.md`](REPOSITORY_START_PATHS.md) for goal-based navigation.
- Then use: [`REPOSITORY_POLISH_AND_ORGANIZATION_2026_04_19.md`](REPOSITORY_POLISH_AND_ORGANIZATION_2026_04_19.md) for the front-door organization and maintenance rule.
- Then use: [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md) for runnable entry points.

## Directory map

- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `docs/`: canonical status/planning notes plus grouped method/evaluation indexes, exploratory notes, and historical guidance.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy/readme assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: preserved historical / provenance-only material.

## Canonical docs now

Read these first for current project interpretation:
1. `docs/CANONICAL_START_HERE.md`
2. `docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`
3. `docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md`
4. `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
5. `docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`
6. `docs/CURRENT_PROJECT_STATUS.md`
7. `docs/CURRENT_BOTTLENECKS.md`
8. `docs/CURRENT_SAFE_CLAIMS.md`
9. `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
10. `docs/WHAT_IS_NOT_WORKING_NOW.md`
11. `docs/PAPER_POSITIONING_NOTE.md`
12. `docs/REPO_MAP.md`
13. `docs/REPOSITORY_POLISH_AND_ORGANIZATION_2026_04_19.md`

## Current highest-value diagnostic / evaluation docs

Use these when you want to understand current evidence:
- `docs/FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`
- `docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`
- `docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`
- `docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`
- `docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`
- `docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`
- `docs/DATASET_ADDITION_PRIORITIES_2026_04_19.md`
- `experiments/value_aware_target_regime_status_note_2026_04_19.md`

## Grouped navigation pages

- `docs/METHOD_STATUS_INDEX.md`
- `docs/EVALUATION_AND_BASELINES_INDEX.md`
- `docs/REPOSITORY_START_PATHS.md`
- `docs/EXPLORATORY_INDEX.md`
- `scripts/HISTORICAL_INDEX.md`

## Canonical scripts now

### Current paper / controller path
- `scripts/run_cross_strategy_frontier_allocation.py`
- `scripts/evaluate_branch_scorer_controller.py`
- `scripts/evaluate_branch_scorer_robustness.py`
- `scripts/run_new_paper_frontier_matrix.py`
- `scripts/run_comparative_frontier_audit.py`
- `scripts/run_imported_methodology_frontier_eval.py`

### Current target-definition / semantic-diagnosis path
- `scripts/build_bruteforce_target_regimes.py`
- `scripts/run_multistep_branch_utility_target_experiment.py`
- `scripts/run_completion_aware_decision_experiment.py`
- `scripts/run_oracle_mismatch_study.py`
- `scripts/run_worst_real_failure_casebook_with_reasoning.py`
- `scripts/run_branch_observability_smoke.py`
- `scripts/run_value_aware_target_regime_comparison.py`

### Current data / evaluation quality path
- dataset registry / loader scripts under the current dataset layer,
- target-construction data paths,
- strict validation and comparison builders,
- method-comparison status builders and supporting evaluators.

## Classification labels

### Canonical
- frontier/controller allocation scaffold,
- branch-priority / next-step allocation framing,
- canonical status / planning docs,
- current comparison, oracle-mismatch, and answer-recovery notes,
- current experiment rule and dashboard notes,
- the current learner-side project-state note,
- and the current consolidated current-state / next-work note.

### Exploratory
- one-off target-family notes,
- narrower controller tweaks,
- bounded ablation reports,
- idea-specific status notes,
- narrower reliability / ambiguity / fallback variants not currently treated as default project interpretation.

### Historical
- old manuscript / binary revise-routing material,
- dated memos superseded by the current canonical docs,
- archived historical script entry points,
- provenance-only assets that should not define the current project.

## Practical collaborator start path

1. Read the canonical docs in order from `docs/CANONICAL_START_HERE.md`.
2. Use `docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md` to understand the current whole-repo situation and the next strongest work.
3. Use `docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md` to understand what changed in the learner-side hardening passes.
4. Use `docs/REPOSITORY_START_PATHS.md` for the shortest path matching your goal.
5. Use `docs/METHOD_STATUS_INDEX.md` or `docs/EVALUATION_AND_BASELINES_INDEX.md` depending on your question.
6. Use `scripts/CANONICAL_START_HERE.md` to find current runnable entry points.
7. Treat exploratory notes as evidence traces, not as the default project interpretation.
8. When writing the paper, use `CURRENT_SAFE_CLAIMS.md` and `PAPER_POSITIONING_NOTE.md` as first constraints.

## Practical maintenance rule

When the project phase changes materially, update these together:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`
- `docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md`
- `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- `docs/REPO_MAP.md`
- `docs/REPOSITORY_POLISH_AND_ORGANIZATION_2026_04_19.md`
- the most relevant current dashboard/comparison/evaluation summary note

This keeps the front door of the repo aligned with the actual state of the project.
