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
- useful diversity realization under budget,
- answer-support aggregation,
- commit-vs-continue decisions under noisy generation,
- real-model confirmation of branch-allocation policies.

This repository is **not** currently centered on the old binary revise-routing paper.

## Current repository state

The current strongest repository-backed picture is:
- earlier local target/oracle refinements were useful diagnostics but not the final broad answer,
- the leading serious method family is now **broad diversity-aware branch allocation with answer-support aggregation**,
- the strongest simulator-side refinement so far is **marginal coverage + semantic overlap** inside that family,
- and the current biggest challenges are:
  - reliable diversity realization,
  - ranking/aggregation quality after diversity exists,
  - and stronger real-model confirmation.

The current best broad baseline to beat is:
- `self_consistency_3`

## Current best repository stance

The current bounded repository stance is:

> **Keep the broad diversity/aggregation family as the main line, improve the quality of realized diversity and downstream branch scoring/aggregation, and prioritize larger but still controlled real-model confirmation over opening a new method family.**

## Read this first

If you want the shortest current synthesis, read:
- [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
- [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md`](docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md)
- [`docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md`](docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md)
- [`docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md)
- [`docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md)

## Fastest reliable start

If you only read a few files, use this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
3. [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
4. [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
5. [`docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md`](docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md)
6. [`docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md`](docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md)
7. [`docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md)
8. [`docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md)
9. [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)
10. [`scripts/README.md`](scripts/README.md)

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

## Start here by goal

### Fastest correct overview
Read in this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
3. [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
4. [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
5. [`docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md`](docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md)
6. [`docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md`](docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md)
7. [`docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md)
8. [`docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md)
9. [`docs/REPO_MAP.md`](docs/REPO_MAP.md)

### Current method and bottleneck path
Read next:
- [`docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md`](docs/LATEST_STATUS_AFTER_RECENT_PASSES_2026_04_18.md)
- [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
- [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
- [`docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md`](docs/MARGINAL_COVERAGE_DIVERSITY_STATUS_2026_04_18.md)
- [`docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md`](docs/FULL_COMPARATIVE_MISTAKE_AUDIT_VS_BEST_METHOD_2026_04_18.md)
- [`docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_REAL_MODEL_CONFIRMATION_2026_04_18.md)
- [`docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md`](docs/BROAD_DIVERSITY_AGGREGATION_COHERE_GEMINI_CONFIRMATION_2026_04_18.md)

### Runnable code entry path
Start with:
- [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md)
- [`scripts/README.md`](scripts/README.md)

## Current state at a glance

### What is already strong
- frontier/controller experimentation scaffold,
- broad diversity-aware controller mechanisms,
- answer-support aggregation infrastructure,
- observability-enabled semantic failure analysis,
- comparative mistake auditing against the best baseline,
- provenance-aware experiment bundles and status notes,
- bounded real-model confirmation paths.

### What is not solved yet
- reliable useful diversity under real provider noise,
- ranking and aggregation quality after diversity exists,
- stable real-model leadership among close family variants,
- broader paper-grade real-model evidence.

### Main bottleneck
The current bottleneck is best described as:

**reliable diversity realization plus stronger post-diversity scoring/aggregation under real-model noise.**

The repository is **not** primarily blocked by:
- missing infrastructure,
- lack of new family ideas,
- or lack of simulator experimentation.

### Best near-term direction
The current best near-term direction is:
- keep the broad diversity/aggregation family,
- strengthen useful diversity rather than raw novelty,
- improve answer-group scoring and commit logic only when they solve a diagnosed residual,
- and prioritize stronger real-model confirmation with available providers.

## Repository layout

- `docs/`: canonical interpretation, planning notes, grouped navigation pages, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Interpretation rules

- **Canonical**: the current broad diversity/aggregation path and the docs/scripts that define it.
- **Exploratory**: active method branches and diagnostics that are useful but not the default summary.
- **Historical**: superseded or provenance-only materials that should not be read as the current project identity.

For interpretation rules and grouped navigation, see:
- [`docs/README.md`](docs/README.md)
- [`docs/REPOSITORY_START_PATHS.md`](docs/REPOSITORY_START_PATHS.md)
- [`docs/EXPLORATORY_INDEX.md`](docs/EXPLORATORY_INDEX.md)
- [`docs/HISTORICAL_AND_ARCHIVE_POLICY.md`](docs/HISTORICAL_AND_ARCHIVE_POLICY.md)

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget branch allocation for LLM reasoning, where the main challenge is how to allocate the next unit of compute across active branches while realizing useful diversity, aggregating answer-level evidence robustly, and deciding when to continue versus commit under uncertainty and limited budget.**

Current manuscript positioning is intentionally honest:

**the repository has a strong leading family and strong diagnostics, but it is not yet in final broad-best-claim shape because real-model confirmation is still limited and useful diversity still does not materialize reliably enough under noisy generation.**
