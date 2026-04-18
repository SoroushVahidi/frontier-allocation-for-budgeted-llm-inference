# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- next-step branch allocation over active branches,
- oracle frontier headroom,
- anti-collapse design,
- and target/oracle quality for hard close-branch decisions.

This repository is **not** currently centered on the older binary revise-routing framing.

## Fast start

- Start here: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Then read: [`LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- Then read: [`CURRENT_EXPERIMENT_RULE_2026_04_18.md`](CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- Then use: [`REPOSITORY_START_PATHS.md`](REPOSITORY_START_PATHS.md) for goal-based navigation.
- Then use: [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md) for runnable entry points.
- For grouped method notes, see [`METHOD_STATUS_INDEX.md`](METHOD_STATUS_INDEX.md).
- For grouped evaluation/baseline notes, see [`EVALUATION_AND_BASELINES_INDEX.md`](EVALUATION_AND_BASELINES_INDEX.md).
- For non-default active lines, see [`EXPLORATORY_INDEX.md`](EXPLORATORY_INDEX.md).
- For provenance-only interpretation, see [`HISTORICAL_AND_ARCHIVE_POLICY.md`](HISTORICAL_AND_ARCHIVE_POLICY.md).

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
2. `docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
3. `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
4. `docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`
5. `docs/REPOSITORY_CLEANUP_STATUS_2026_04_18.md`
6. `docs/PROJECT_SITUATION_REPORT_2026_04_18.md`
7. `docs/CURRENT_PROJECT_STATUS.md`
8. `docs/CURRENT_BOTTLENECKS.md`
9. `docs/CURRENT_SAFE_CLAIMS.md`
10. `docs/CURRENT_METHOD_SUMMARY_AND_GAPS.md`
11. `docs/WHAT_IS_NOT_WORKING_NOW.md`
12. `docs/PAPER_POSITIONING_NOTE.md`
13. `docs/REPO_MAP.md`

## Current highest-value diagnostic / evaluation docs

Use these when you want to understand current evidence:
- `docs/FULL_METHOD_COMPARISON_STATUS_2026_04_18.md`
- `docs/ORACLE_MISMATCH_STUDY_2026_04_18.md`
- `docs/FINAL_ANSWER_RECOVERY_STATUS_2026_04_18.md`
- `docs/WORST_REAL_FAILURE_CASEBOOK_WITH_REASONING_20260418.md`
- `docs/RESEARCH_IDEAS_AND_NEXT_STEPS_2026_04_18.md`
- `docs/WORKSTREAM_STATUS_AND_OPERATING_PLAN_2026_04_18.md`

## Grouped navigation pages

- `docs/METHOD_STATUS_INDEX.md`
- `docs/EVALUATION_AND_BASELINES_INDEX.md`
- `docs/REPOSITORY_START_PATHS.md`
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
- current experiment rule and cleanup-status notes.

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
2. Use `docs/REPOSITORY_START_PATHS.md` for the shortest path matching your goal.
3. Use `docs/METHOD_STATUS_INDEX.md` or `docs/EVALUATION_AND_BASELINES_INDEX.md` depending on your question.
4. Use `scripts/CANONICAL_START_HERE.md` to find current runnable entry points.
5. Treat exploratory notes as evidence traces, not as the default project interpretation.
6. When writing the paper, use `CURRENT_SAFE_CLAIMS.md` and `PAPER_POSITIONING_NOTE.md` as first constraints.

## Practical maintenance rule

When the project phase changes materially, update these together:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`
- `docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`
- `docs/REPO_MAP.md`
- the most relevant current dashboard/comparison/evaluation summary note

This keeps the front door of the repo aligned with the actual state of the project.
