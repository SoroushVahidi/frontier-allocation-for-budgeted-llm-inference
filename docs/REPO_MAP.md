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

Read these first:
1. [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
2. [`CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`](CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md)
3. [`CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`](CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md)
4. [`FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`](FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md)
5. [`CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md)
6. [`CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`](CURRENT_EXPERIMENTS_INDEX_2026_04_21.md)
7. [`CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`](CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md)
8. [`../scripts/CANONICAL_START_HERE.md`](../scripts/CANONICAL_START_HERE.md)

## Directory map

- `docs/`: canonical status notes, navigation pages, planning notes, reference/baseline indexes, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: reusable implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: preserved historical and provenance-only material.

## Current highest-value reading set

### Project state
- `docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`
- `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`
- `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`
- `docs/CURRENT_SAFE_CLAIMS.md`
- `docs/CURRENT_BOTTLENECKS.md`

### Evaluation and evidence
- `docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`
- `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`
- `docs/EVALUATION_AND_BASELINES_INDEX.md`
- `outputs/README.md`

### Code entry points
- `docs/CANONICAL_INSTALL_AND_DEV.md`
- `scripts/CANONICAL_START_HERE.md`
- `scripts/README.md`

## Current canonical scripts

### Default-decision and failure-analysis path
- `scripts/run_broader_strict_phased_default_decision_eval.py`
- `scripts/build_new_hundred_newest_vs_best_failure_statistics.py`
- `scripts/run_hard_max_family_expansions_eval.py`
- `scripts/run_hundred_three_gate_design_eval_strict_phased.py`
- `scripts/run_learned_f2_to_f3_gate_v1_eval.py`

### Baseline and broader comparison support path
- `scripts/run_full_method_comparison_bundle.py`
- `scripts/build_twenty_exact_current_full_vs_best_fresh.py`
- `scripts/run_s1_budget_forcing_baseline.py`
- `scripts/run_tale_baseline.py`
- `scripts/run_l1_baseline.py`

## Practical collaborator path

1. Read the canonical docs in order from `docs/CANONICAL_START_HERE.md`.
2. Use `docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md` to understand the current strict-phased method state.
3. Use `docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md` to see the decisive default-model result.
4. Use `docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md` to understand which experiment families are active.
5. Use `docs/CANONICAL_INSTALL_AND_DEV.md` and `scripts/CANONICAL_START_HERE.md` to start running code.
6. Treat exploratory notes as evidence traces, not as the default project interpretation.

## Maintenance rule

When the project phase changes materially, update these together:
- `README.md`
- `QUICKSTART.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/REPO_MAP.md`
- `docs/CANONICAL_INSTALL_AND_DEV.md`
- `scripts/README.md`
- `outputs/README.md`

This keeps the repository front door aligned with the actual state of the project.
