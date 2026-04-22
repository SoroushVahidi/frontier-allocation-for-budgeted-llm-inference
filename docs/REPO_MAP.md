# Repository map and canonical path

## Project scope (current)

Canonical scope is the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- next-step branch allocation over active branches,
- answer-group-level commit control,
- answer-group preservation and maturation under budget,
- anti-collapse branch-family control,
- and target/oracle quality for hard close-branch decisions.

This repository is **not** currently centered on the older binary revise-routing framing.

## Fast start

- Start here: [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Then read: [`CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md`](CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md)
- Then read: [`FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md`](FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md)
- Then read: [`PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`](PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md)
- Then read: [`FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`](FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md)
- Then read: [`SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md`](SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md)
- Then use: [`CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md) for artifact navigation.
- Then use: [`CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`](CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md) and [`main_baselines.md`](main_baselines.md) for comparison navigation.
- Then use: [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md) for runnable entry points.

## Directory map

- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `docs/`: canonical status/planning notes, grouped method/evaluation indexes, baseline/reference docs, exploratory notes, and historical guidance.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy/readme assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: preserved historical / provenance-only material.

## Canonical docs now

Read these first for current project interpretation:
1. `docs/CANONICAL_START_HERE.md`
2. `docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md`
3. `docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md`
4. `docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`
5. `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
6. `docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md`
7. `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
8. `docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
9. `docs/main_baselines.md`
10. `docs/CURRENT_SAFE_CLAIMS.md`
11. `docs/REPO_MAP.md`

## Current highest-value diagnostic / evaluation docs

Use these when you want to understand current evidence:
- `docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md`
- `docs/FULL_OUR_METHOD_VS_EXTERNAL_BASELINES_COMPARISON_20260422T230000Z.md`
- `docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`
- `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
- `docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md`

## Grouped navigation pages

- `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
- `docs/EVALUATION_AND_BASELINES_INDEX.md`
- `docs/REPOSITORY_START_PATHS.md`
- `docs/EXPLORATORY_INDEX.md`
- `scripts/HISTORICAL_INDEX.md`

## Canonical scripts now

### Current in-house decision and comparison path
- `scripts/run_broader_strict_phased_default_decision_eval.py`
- `scripts/run_full_our_method_vs_external_baselines_comparison.py`
- `scripts/build_paper_facing_baseline_tables.py`
- `scripts/build_fairness_audit_for_direct_baselines.py`
- `scripts/build_simple_scaling_baseline_coverage_audit.py`

### Current baseline / broader comparison support path
- `scripts/run_s1_budget_forcing_baseline.py`
- `scripts/run_tale_baseline.py`
- `scripts/run_l1_baseline.py`
- `scripts/run_rest_mcts_adjacent_integration.py`
- `scripts/run_lets_verify_step_by_step_adjacent_integration.py`
- `scripts/run_tree_plv_adjacent_integration.py`

## Practical collaborator start path

1. Read the canonical docs in order from `docs/CANONICAL_START_HERE.md`.
2. Use `docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md` and `docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md` to understand what “our method” means.
3. Use `docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md` and `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md` to understand the current paper-facing comparison and safe claim boundaries.
4. Use `docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md` to understand why no extra direct simple-scaling baseline was added.
5. Use `scripts/CANONICAL_START_HERE.md` to find current runnable entry points.
6. Treat exploratory notes as evidence traces, not as the default project interpretation.

## Practical maintenance rule

When the project phase changes materially, update these together:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md`
- `docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md`
- `docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`
- `docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`
- `docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md`
- `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
- `docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
- `docs/main_baselines.md`
- `docs/REPO_MAP.md`
- `scripts/CANONICAL_START_HERE.md`
- `outputs/README.md`

This keeps the front door of the repo aligned with the actual state of the project.
