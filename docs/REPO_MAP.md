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
- Then use: [`CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md) for the current evidence path.
- Then use: [`CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`](CURRENT_EXPERIMENTS_INDEX_2026_04_21.md) for current experiment-family navigation.
- Then use: [`REPOSITORY_START_PATHS.md`](REPOSITORY_START_PATHS.md) for goal-based navigation.
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
4. `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
5. `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
6. `docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`
7. `docs/CURRENT_SAFE_CLAIMS.md`
8. `docs/CURRENT_BOTTLENECKS.md`
9. `docs/REPO_MAP.md`

## Current highest-value diagnostic / evaluation docs

Use these when you want to understand current evidence:
- `docs/TWENTY_EXACT_CURRENT_FULL_VS_BEST_FRESH_2026_04_20.md`
- `docs/HUNDRED_CURRENT_FULL_VS_BEST_FAILURE_STATISTICS_20260420T220416Z.md`
- `docs/NEW_HUNDRED_NEWEST_VS_BEST_FAILURE_STATISTICS_20260421T032711Z.md`
- `docs/STRICT_PHASED_HARD_EARLY_COVERAGE_REPORT_20260421T020917Z.md`
- `docs/HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_20260421T022459Z.md`
- `docs/HARD_MAX_FAMILY_EXPANSIONS_EVAL_20260421T040333Z.md`
- `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`

## Grouped navigation pages

- `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
- `docs/METHOD_STATUS_INDEX.md`
- `docs/EVALUATION_AND_BASELINES_INDEX.md`
- `docs/REPOSITORY_START_PATHS.md`
- `docs/EXPLORATORY_INDEX.md`
- `scripts/HISTORICAL_INDEX.md`

## Canonical scripts now

### Current strict-phased default-decision path
- `scripts/run_hundred_hard_early_coverage_depth2_vs_depth3_eval_20260421.py`
- `scripts/run_hundred_three_gate_design_eval_strict_phased.py`
- `scripts/build_new_hundred_newest_vs_best_failure_statistics.py`
- `scripts/run_learned_f2_to_f3_gate_v1_eval.py`
- `scripts/run_hard_max_family_expansions_eval.py`

### Current baseline / broader comparison support path
- `scripts/run_full_method_comparison_bundle.py`
- `scripts/build_twenty_exact_current_full_vs_best_fresh.py`
- `scripts/run_s1_budget_forcing_baseline.py`
- `scripts/run_tale_baseline.py`
- `scripts/run_l1_baseline.py`

## Classification labels

### Canonical
- frontier/controller allocation scaffold,
- branch-priority / next-step allocation framing,
- strict-phased F1 → F2 → F3 early-coverage experiments,
- current exact-loss and hundred-case failure-statistics reports,
- current default-model status note,
- and the current consolidated evidence/experiments indexes.

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
2. Use `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md` to understand the current strict-phased method state.
3. Use `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md` to understand which experiment families are now active.
4. Use `docs/NEW_HUNDRED_NEWEST_VS_BEST_FAILURE_STATISTICS_20260421T032711Z.md` and `docs/HUNDRED_THREE_GATE_DESIGN_COMPARISON_STRICT_PHASED_20260421T022459Z.md` to understand the current concrete failure structure and the current gate/force comparisons.
5. Use `scripts/CANONICAL_START_HERE.md` to find current runnable entry points.
6. Treat exploratory notes as evidence traces, not as the default project interpretation.
7. When writing the paper, use `CURRENT_SAFE_CLAIMS.md` and `PAPER_POSITIONING_NOTE.md` as first constraints.

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
