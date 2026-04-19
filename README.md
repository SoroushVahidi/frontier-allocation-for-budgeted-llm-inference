# adaptive-reasoning-budget-allocation

Repository for the **current NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Canonical project question

> **Which active branch should receive the next unit of compute, and when should the system continue versus commit?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending on this branch relative to spending it elsewhere, given the current answer-group evidence?**

## Current repository identity

This repository is currently centered on:
- fixed-budget adaptive test-time compute allocation,
- branch-priority / next-step allocation over active branches,
- answer-group-level final selection and commit control,
- useful diversity realization under budget,
- answer-support aggregation,
- real-model confirmation of branch-allocation policies.

This repository is **not** currently centered on the old binary revise-routing paper.

## Current repository state

The current strongest repository-backed picture is:
- earlier local target/oracle refinements were useful diagnostics but not the final broad answer,
- the leading serious broad family remains **broad diversity-aware branch allocation with answer-support aggregation**,
- the refreshed comparative failure re-audit showed that the dominant bottleneck shifted away from insufficient diversity and toward **wrong commit timing**,
- bounded incumbent-vs-challenger commit control is now the leading serious next method line,
- stronger matched validation showed the **dependence-aware** incumbent-vs-challenger variant improves accuracy and reduces wrong_commit_timing more than both the base controller and the raw-support variant,
- recent dataset work broadened and clarified the evaluation surface, with exact-answer math expansions now cleaner and more experiment-ready,
- and the current biggest challenges are now best separated into:
  - **repo-wide**: answer-group-level commit timing, challenger control, and stronger real-model confirmation,
  - **method-line**: refining dependence-aware ICC by wrong-commit subtype and reducing harmed cases,
  - **evaluation-surface**: keeping partial integrations honest and experiment-readiness explicit.

The current best broad baseline to beat is:
- `self_consistency_3`

## Current best repository stance

The current bounded repository stance is:

> **Keep the broad diversity/aggregation family as the main line, treat dependence-aware incumbent-vs-challenger commit control as the leading serious next method line, refine it by wrong-commit subtype rather than opening a new controller family, and prioritize stronger but still controlled validation and real-model confirmation over broad new method search.**

## Read this first

If you want the shortest current synthesis, read:
- [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
- [`docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`](docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md)
- [`docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md`](docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md)
- [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/DATASET_ADDITION_PRIORITIES_2026_04_19.md`](docs/DATASET_ADDITION_PRIORITIES_2026_04_19.md)
- [`docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md`](docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md)
- [`docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md)
- [`experiments/value_aware_target_regime_status_note_2026_04_19.md`](experiments/value_aware_target_regime_status_note_2026_04_19.md)

## Fastest reliable start

If you only read a few files, use this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`](docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md)
3. [`docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md`](docs/PROJECT_STATE_AFTER_VALUE_TARGET_HARDENING_2026_04_19.md)
4. [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
5. [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
6. [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
7. [`docs/DATASET_ADDITION_PRIORITIES_2026_04_19.md`](docs/DATASET_ADDITION_PRIORITIES_2026_04_19.md)
8. [`docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md`](docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md)
9. [`docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md)
10. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)
11. [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)
12. [`scripts/README.md`](scripts/README.md)

## What to avoid at first

Do **not** start by reading arbitrary experiment notes, historical memos, or one-off outputs in isolation.

Do **not** assume the next best move is another nearby local tweak or another new method family.

Use these interpretation rules instead:
- **Canonical** docs/scripts define the current project identity.
- **Exploratory** materials are useful active branches, but not the default summary.
- **Historical** materials are provenance-only and should not define the current paper story.

For the formal interpretation rules, see:
- [`docs/README.md`](docs/README.md)
- [`docs/EXPLORATORY_INDEX.md`](docs/EXPLORATORY_INDEX.md)
- [`docs/HISTORICAL_AND_ARCHIVE_POLICY.md`](docs/HISTORICAL_AND_ARCHIVE_POLICY.md)

## Current state at a glance

### What is already strong
- frontier/controller experimentation scaffold,
- broad diversity-aware controller mechanisms,
- answer-support aggregation infrastructure,
- observability-enabled semantic failure analysis,
- comparative mistake auditing against the best baseline,
- provenance-aware experiment bundles and status notes,
- bounded real-model confirmation paths,
- a materially stronger learner-side supervision stack than before,
- a broader and cleaner dataset surface than before,
- and a leading incumbent-vs-challenger commit-control method line with stronger matched validation support.

### What is not solved yet
- wrong commit timing at the answer-group level,
- challenger control under realistic noise,
- dependence-aware support calibration,
- stable real-model leadership among close variants,
- broader paper-grade real-model evidence,
- and honest experiment-readiness closure for partially integrated datasets such as LiveCodeBench.

### Main bottleneck
The current bottleneck is best described as:

**wrong commit timing at the answer-group level: deciding whether the incumbent is already safe to commit to, whether a challenger still deserves compute, and how to avoid harmful late-stage instability.**

The repository is **not** primarily blocked by:
- missing infrastructure,
- lack of datasets,
- lack of new family ideas,
- or the old dominant insufficient-diversity story.

### Best near-term direction
The current best near-term direction is:
- keep the broad diversity/aggregation family,
- keep dependence-aware incumbent-vs-challenger commit control as the leading method line,
- refine ICC by wrong-commit subtype rather than by broad heuristic search,
- understand and reduce harmed cases,
- and prioritize stronger controlled validation followed by stronger real-model confirmation.

## Repository layout

- `docs/`: canonical interpretation, planning notes, grouped navigation pages, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget branch allocation for LLM reasoning, where the key remaining challenge is not mainly creating more branches, but deciding when the current best answer group is already strong and stable enough to commit to, how to compare it against challengers under correlated support, and how to allocate remaining compute only when a challenger still has plausible upside.**

Current manuscript positioning is intentionally honest:

**the repository now has a strong leading broad family, a stronger learner-side target stack, a broader evaluation surface, and a leading incumbent-vs-challenger commit-control refinement, but it is not yet in final broad-best-claim shape because the ICC line still needs subtype-driven refinement and stronger real-model confirmation.**
