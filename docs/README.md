# Documentation index

This index separates the repository documentation into **canonical**, **supporting**, **exploratory**, and **historical** material.

## Read this first

If you want the current interpretation of the project, start here:

1. [`PROJECT_MASTER_PLAN.md`](PROJECT_MASTER_PLAN.md)
2. [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
3. [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
4. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
5. [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md)
6. [`REPO_MAP.md`](REPO_MAP.md)

## Canonical docs

These define the current project identity, current status, and manuscript-safe interpretation.

- [`PROJECT_MASTER_PLAN.md`](PROJECT_MASTER_PLAN.md)
- [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
- [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
- [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
- [`STOP_VS_ACT_DIRECTION.md`](STOP_VS_ACT_DIRECTION.md)
- [`NEXT_LIGHTWEIGHT_STEPS.md`](NEXT_LIGHTWEIGHT_STEPS.md)
- [`LATER_HEAVIER_STEPS.md`](LATER_HEAVIER_STEPS.md)
- [`EXPERIMENT_STATUS.md`](EXPERIMENT_STATUS.md)
- [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md)
- [`REPO_MAP.md`](REPO_MAP.md)
- [`BRUTEFORCE_LABEL_DATA_STATUS.md`](BRUTEFORCE_LABEL_DATA_STATUS.md)
- [`BRUTEFORCE_LABEL_SCALING_STATUS.md`](BRUTEFORCE_LABEL_SCALING_STATUS.md)
- [`CURRENT_DATASET_AUDIT_STATUS.md`](CURRENT_DATASET_AUDIT_STATUS.md)
- [`CURRENT_BRANCH_LEARNING_DATASET_READINESS.md`](CURRENT_BRANCH_LEARNING_DATASET_READINESS.md)

## Canonical supporting references

These are useful once you already understand the main project interpretation.

- [`cross_controller_frontier.md`](cross_controller_frontier.md)
- [`main_datasets.md`](main_datasets.md)
- [`main_baselines.md`](main_baselines.md)
- [`datasets_access.md`](datasets_access.md)
- [`DATASET_STATUS.md`](DATASET_STATUS.md)
- [`EXTERNAL_DATASET_PRM_MATHSHEPHERD_APPS_STATUS_2026_04_16.md`](EXTERNAL_DATASET_PRM_MATHSHEPHERD_APPS_STATUS_2026_04_16.md)
- [`CANONICAL_BRANCH_LEARNING_PASS_2026_04_16.md`](CANONICAL_BRANCH_LEARNING_PASS_2026_04_16.md)
- [`CANONICAL_BRANCH_LEARNING_INTERVENTION_PASS_2026_04_16.md`](CANONICAL_BRANCH_LEARNING_INTERVENTION_PASS_2026_04_16.md)
- [`CANONICAL_EXTERNAL_SUPERVISION_PRM800K_ROBUSTNESS_PASS_2026_04_16.md`](CANONICAL_EXTERNAL_SUPERVISION_PRM800K_ROBUSTNESS_PASS_2026_04_16.md)
- [`CANONICAL_EXTERNAL_SUPERVISION_PRM800K_HARD_SLICE_COVERAGE_PASS_2026_04_16.md`](CANONICAL_EXTERNAL_SUPERVISION_PRM800K_HARD_SLICE_COVERAGE_PASS_2026_04_16.md)
- [`CANONICAL_EXTERNAL_SUPERVISION_PRM800K_COMPARATOR_BOUNDARY_RECOVERY_EXECUTION_PASS_2026_04_16.md`](CANONICAL_EXTERNAL_SUPERVISION_PRM800K_COMPARATOR_BOUNDARY_RECOVERY_EXECUTION_PASS_2026_04_16.md)
- [`CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`](CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md)
- [`cascade_routing_integration.md`](cascade_routing_integration.md)
- [`mob_majority_of_bests_integration.md`](mob_majority_of_bests_integration.md)
- [`rest_mcts_integration.md`](rest_mcts_integration.md)
- [`openr_integration.md`](openr_integration.md)
- [`l1_baseline_integration.md`](l1_baseline_integration.md)

## Current interpretation in one paragraph

The repository is now best understood as a strong research platform for **fixed-budget branch-priority / next-step allocation** in LLM reasoning. Internal supervision, canonical corpora, and matched evaluation are now substantially more mature than before. The main unresolved issue is not infrastructure but **decision-aligned supervision quality and hard-slice evidence**, including near-tie, adjacent-rank, exact-promoted, and external-to-internal transfer alignment.

## Exploratory docs

These are useful for specific method lines, but they are **not** the default interpretation of the repository.

Typical examples include:
- oracle generator productionization notes,
- oracle selective-distillation notes,
- branch-scorer line status notes,
- tie-aware and ambiguity-aware experiment notes,
- reliability-aware and warm-start variants,
- narrower method-specific diagnostics.

## Historical docs

These are kept for provenance rather than as the current project view.

Typical examples include:
- old-track separation notes,
- superseded memo snapshots,
- older summaries replaced by the current canonical docs.

## Interpretation rule

- Use the **canonical docs** to understand the project and write about it.
- Use the **supporting references** when you need dataset, baseline, or evaluation context.
- Use **exploratory docs** for a specific experiment line only.
- Use **historical docs** only for provenance.
