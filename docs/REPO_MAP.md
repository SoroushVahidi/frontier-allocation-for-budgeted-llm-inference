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
- Then read: [`CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`](CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md)
- Then read: [`CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`](CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md)
- Then read: [`FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`](FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md)
- Then use: [`CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md) for artifact navigation.
- Then use: [`CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`](CURRENT_EXPERIMENTS_INDEX_2026_04_21.md) for experiment-family navigation.
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
2. `docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
3. `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
4. `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
5. `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
6. `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
7. `docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
8. `docs/CURRENT_SAFE_CLAIMS.md`
9. `docs/REPO_MAP.md`

## Current highest-value diagnostic / evaluation docs

Use these when you want to understand current evidence:
- `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `docs/NEW_HUNDRED_NEWEST_VS_BEST_FAILURE_STATISTICS_20260421T032711Z.md`
- `docs/HARD_MAX_FAMILY_EXPANSIONS_K456_EVAL_20260421T041916Z.md`
- `docs/HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_20260421T022459Z.md`
- `docs/STRICT_PHASED_HARD_EARLY_COVERAGE_REPORT_20260421T020917Z.md`

## Grouped navigation pages

- `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
- `docs/EVALUATION_AND_BASELINES_INDEX.md`
- `docs/REPOSITORY_START_PATHS.md`
- `docs/EXPLORATORY_INDEX.md`
- `scripts/HISTORICAL_INDEX.md`

## Canonical scripts now

### Current default-decision and failure-analysis path
- `scripts/run_broader_strict_phased_default_decision_eval.py`
- `scripts/build_new_hundred_newest_vs_best_failure_statistics.py`
- `scripts/run_hard_max_family_expansions_eval.py`
- `scripts/run_hundred_three_gate_design_eval_strict_phased.py`
- `scripts/run_learned_f2_to_f3_gate_v1_eval.py`

### Current baseline / broader comparison support path
- `scripts/run_full_method_comparison_bundle.py`
- `scripts/build_twenty_exact_current_full_vs_best_fresh.py`
- `scripts/run_s1_budget_forcing_baseline.py`
- `scripts/run_tale_baseline.py`
- `scripts/run_l1_baseline.py`

## Practical collaborator start path

1. Read the canonical docs in order from `docs/CANONICAL_START_HERE.md`.
2. Use `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md` to understand the current strict-phased method state.
3. Use `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md` to see the decisive default-model result.
4. Use `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md` to understand which experiment families are now active.
5. Use `scripts/CANONICAL_START_HERE.md` to find current runnable entry points.
6. Treat exploratory notes as evidence traces, not as the default project interpretation.

## Practical maintenance rule

When the project phase changes materially, update these together:
- `README.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
- `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
- `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
- `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
- `docs/REPO_MAP.md`
- `scripts/CANONICAL_START_HERE.md`
- `outputs/README.md`

This keeps the front door of the repo aligned with the actual state of the project.
