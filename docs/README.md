# Documentation index

This index defines the **canonical**, **exploratory**, and **historical** documentation for the current project.

## Fast start

- New collaborators: start with [`CANONICAL_START_HERE.md`](CANONICAL_START_HERE.md)
- Active but non-default method lines: see [`EXPLORATORY_INDEX.md`](EXPLORATORY_INDEX.md)
- Historical/provenance interpretation: see [`HISTORICAL_AND_ARCHIVE_POLICY.md`](HISTORICAL_AND_ARCHIVE_POLICY.md)

## Canonical docs (read in this order)

1. [`PROJECT_MASTER_PLAN.md`](PROJECT_MASTER_PLAN.md)
2. [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
3. [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
4. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
5. [`CURRENT_METHOD_SUMMARY_AND_GAPS.md`](CURRENT_METHOD_SUMMARY_AND_GAPS.md)
6. [`WHAT_IS_NOT_WORKING_NOW.md`](WHAT_IS_NOT_WORKING_NOW.md)
7. [`RESEARCH_UPGRADE_NOTE_2026_04_17.md`](RESEARCH_UPGRADE_NOTE_2026_04_17.md)
8. [`STOP_VS_ACT_DIRECTION.md`](STOP_VS_ACT_DIRECTION.md)
9. [`NEXT_LIGHTWEIGHT_STEPS.md`](NEXT_LIGHTWEIGHT_STEPS.md)
10. [`LATER_HEAVIER_STEPS.md`](LATER_HEAVIER_STEPS.md)
11. [`EXPERIMENT_STATUS.md`](EXPERIMENT_STATUS.md)
12. [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md)
13. [`REPO_MAP.md`](REPO_MAP.md)
14. [`BRUTEFORCE_LABEL_DATA_STATUS.md`](BRUTEFORCE_LABEL_DATA_STATUS.md)
15. [`BRUTEFORCE_LABEL_SCALING_STATUS.md`](BRUTEFORCE_LABEL_SCALING_STATUS.md)

## Canonical supporting references

- [`cross_controller_frontier.md`](cross_controller_frontier.md)
- [`main_datasets.md`](main_datasets.md)
- [`main_baselines.md`](main_baselines.md)
- [`cascade_routing_integration.md`](cascade_routing_integration.md)
- [`mob_majority_of_bests_integration.md`](mob_majority_of_bests_integration.md)
- [`rest_mcts_integration.md`](rest_mcts_integration.md)
- [`openr_integration.md`](openr_integration.md)
- [`l1_baseline_integration.md`](l1_baseline_integration.md)
- [`datasets_access.md`](datasets_access.md)
- [`DATASET_STATUS.md`](DATASET_STATUS.md)
- [`CURRENT_DATASET_AUDIT_STATUS.md`](CURRENT_DATASET_AUDIT_STATUS.md)
- [`CURRENT_BRANCH_LEARNING_DATASET_READINESS.md`](CURRENT_BRANCH_LEARNING_DATASET_READINESS.md)
- [`CANONICAL_BRANCH_LEARNING_PASS_2026_04_16.md`](CANONICAL_BRANCH_LEARNING_PASS_2026_04_16.md)
- [`CANONICAL_BRANCH_LEARNING_INTERVENTION_PASS_2026_04_16.md`](CANONICAL_BRANCH_LEARNING_INTERVENTION_PASS_2026_04_16.md)
- [`EXTERNAL_DATASET_PRM_MATHSHEPHERD_APPS_STATUS_2026_04_16.md`](EXTERNAL_DATASET_PRM_MATHSHEPHERD_APPS_STATUS_2026_04_16.md)
- [`CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`](CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md)

## How to interpret the canonical docs

- `PROJECT_MASTER_PLAN.md` gives the full project identity, final goal, and roadmap.
- `CURRENT_PROJECT_STATUS.md` says what is genuinely built and what is still unresolved.
- `CURRENT_BOTTLENECKS.md` explains the main obstacle.
- `CURRENT_SAFE_CLAIMS.md` tells you what is manuscript-safe to say now.
- `CURRENT_METHOD_SUMMARY_AND_GAPS.md` is the shortest current method-state summary.
- `WHAT_IS_NOT_WORKING_NOW.md` records directions that are currently weak or explicitly not validated enough.
- `RESEARCH_UPGRADE_NOTE_2026_04_17.md` records the strongest current outside-research upgrade directions.
- `STOP_VS_ACT_DIRECTION.md` defines one important near-term controller direction, but it is no longer the whole project identity.
- `PAPER_POSITIONING_NOTE.md` translates the project state into a paper story.
- `REPO_MAP.md` tells collaborators where to start in code and docs.

## Exploratory / active-branch notes

These notes are useful, but they are **not** the default interpretation of the project.

Examples include:
- oracle generator interface / productionization / pilot protocols,
- oracle selective distillation and oracle-distilled student notes,
- branch-scorer line status and method-specific result notes,
- tie-aware, reliability-aware, warm-start, and ambiguity-targeted experimental notes,
- stricter hard-case / near-tie controller refinements.

Use these when you need traceability for a specific experiment line, not as the first summary of the repo.

## Historical / provenance notes

These remain valuable for traceability but are not canonical:
- old-track separation notes,
- dated memo snapshots,
- earlier summaries superseded by the current canonical docs.

For historical interpretation rules, see [`HISTORICAL_AND_ARCHIVE_POLICY.md`](HISTORICAL_AND_ARCHIVE_POLICY.md).

## Interpretation rule

- Use the **canonical docs** for current project interpretation and paper planning.
- Use **exploratory notes** for experiment-specific context.
- Use **historical notes** only for provenance or comparison with older directions.
