# Documentation index

This index defines the **canonical**, **exploratory**, and **historical** documentation for the current project.

## Canonical docs (read in this order)

1. [`PROJECT_MASTER_PLAN.md`](PROJECT_MASTER_PLAN.md)
2. [`CURRENT_PROJECT_STATUS.md`](CURRENT_PROJECT_STATUS.md)
3. [`CURRENT_BOTTLENECKS.md`](CURRENT_BOTTLENECKS.md)
4. [`CURRENT_SAFE_CLAIMS.md`](CURRENT_SAFE_CLAIMS.md)
5. [`STOP_VS_ACT_DIRECTION.md`](STOP_VS_ACT_DIRECTION.md)
6. [`NEXT_LIGHTWEIGHT_STEPS.md`](NEXT_LIGHTWEIGHT_STEPS.md)
7. [`LATER_HEAVIER_STEPS.md`](LATER_HEAVIER_STEPS.md)
8. [`EXPERIMENT_STATUS.md`](EXPERIMENT_STATUS.md)
9. [`PAPER_POSITIONING_NOTE.md`](PAPER_POSITIONING_NOTE.md)
10. [`REPO_MAP.md`](REPO_MAP.md)
11. [`BRUTEFORCE_LABEL_DATA_STATUS.md`](BRUTEFORCE_LABEL_DATA_STATUS.md)

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
- [`CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md`](CURRENT_REFERENCES_SUPPLEMENT_2026_04_16.md)

## How to interpret the canonical docs

- `PROJECT_MASTER_PLAN.md` gives the full project identity, final goal, and roadmap.
- `CURRENT_PROJECT_STATUS.md` says what is genuinely built and what is still unresolved.
- `CURRENT_BOTTLENECKS.md` explains the main obstacle.
- `CURRENT_SAFE_CLAIMS.md` tells you what is manuscript-safe to say now.
- `STOP_VS_ACT_DIRECTION.md` defines the main near-term controller direction.
- `NEXT_LIGHTWEIGHT_STEPS.md` and `LATER_HEAVIER_STEPS.md` describe what to do next.
- `PAPER_POSITIONING_NOTE.md` translates the project state into a paper story.
- `REPO_MAP.md` tells collaborators where to start in code and docs.

## Exploratory / active-branch notes

These notes are useful, but they are **not** the default interpretation of the project.

- Oracle generator interface / productionization / pilot protocols.
- Oracle selective distillation and oracle-distilled student notes.
- Branch-scorer line status and method-specific result notes.
- Tie-aware, reliability-aware, warm-start, and ambiguity-targeted experimental notes.

Use these when you need traceability for a specific experiment line, not as the first summary of the repo.

## Historical / provenance notes

These remain valuable for traceability but are not canonical:
- old-track separation notes,
- dated memo snapshots,
- earlier summaries superseded by the current canonical docs.

## Interpretation rule

- Use the **canonical docs** for current project interpretation and paper planning.
- Use **exploratory notes** for experiment-specific context.
- Use **historical notes** only for provenance or comparison with older directions.
