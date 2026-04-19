# adaptive-reasoning-budget-allocation

Repository for the current **NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

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
- the leading serious broad family remains **broad diversity-aware branch allocation with answer-support aggregation**,
- bounded diagnostic work now points more specifically to **early-to-mid tree-growth control** as a major weakness,
- the strongest current promoted refinement line is **anti-collapse answer-group-aware allocation** inside the same broad family,
- and the current best diagnostic stack now includes:
  - full method comparison bundles,
  - 20-case defeat casebooks,
  - branch-reasoning recovery on selected defeat cases,
  - and discovered-tree reconstructions for the same cases.

The current best broad baseline to beat is:
- `self_consistency_3`

## Current best repository stance

The current bounded repository stance is:

> **Keep the broad diversity/aggregation family as the main line, treat anti-collapse answer-group-aware allocation as the current promoted next bounded refinement, and use stronger but still controlled validation plus real-model confirmation before making broad superiority claims.**

## Fastest reliable start

If you want the shortest trustworthy entry path, read in this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`](docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md)
3. [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
4. [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
5. [`docs/TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md`](docs/TWENTY_DEFEAT_CASES_WITH_BRANCH_REASONING_2026_04_19.md)
6. [`docs/TWENTY_DEFEAT_CASES_WITH_DISCOVERED_TREES_2026_04_19.md`](docs/TWENTY_DEFEAT_CASES_WITH_DISCOVERED_TREES_2026_04_19.md)
7. [`docs/REPOSITORY_POLISH_AND_ORGANIZATION_2026_04_19.md`](docs/REPOSITORY_POLISH_AND_ORGANIZATION_2026_04_19.md)

Then use:
- [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the canonical map,
- [`docs/README.md`](docs/README.md) for grouped navigation,
- [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md) for runnable entry points.

## What to avoid at first

Do **not** start by reading arbitrary experiment notes, historical memos, or one-off outputs in isolation.

Do **not** assume the next best move is another nearby threshold tweak or another unrelated new family.

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
- bounded real-model confirmation paths,
- 20-case defeat analysis with branch-level recovery,
- 20-case discovered-tree / frontier-evolution reconstruction,
- and a materially stronger learner-side supervision stack than before.

### What is not solved yet
- robust early-to-mid anti-collapse tree control under budget,
- challenger maturation without harming too many cases,
- dependence-aware support calibration,
- stable real-model leadership among close variants,
- broader paper-grade real-model evidence,
- and honest experiment-readiness closure for partially integrated datasets such as LiveCodeBench.

### Main bottleneck
The current bottleneck is best described as:

**under fixed budget, the controller still tends to over-expand one early-favored branch and does not yet reliably preserve and mature answer-distinct alternatives strongly enough.**

### Best near-term direction
The current best near-term direction is:
- keep the broad diversity/aggregation family,
- continue the anti-collapse answer-group-aware line as the promoted next bounded refinement,
- reduce harmed cases without losing the current gains,
- and strengthen controlled validation before broad paper claims.

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

**fixed-budget branch allocation for LLM reasoning, where a key remaining challenge is not just whether to commit late, but how to keep answer-distinct alternatives alive and competitive early enough for the budget to be spent on the right tree shape.**

Current manuscript positioning is intentionally honest:

**the repository now has a strong leading broad family, a promoted anti-collapse refinement line, and a much better defeat-analysis stack, but it is not yet in final broad-best-claim shape because harmed-case reduction and stronger real-model confirmation still need more evidence.**
