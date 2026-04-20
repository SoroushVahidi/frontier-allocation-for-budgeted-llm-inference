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
- real-model confirmation of branch-allocation policies,
- and now a more explicit distinction between **tree-generation quality** and **final output-layer correctness**.

This repository is **not** currently centered on the old binary revise-routing paper.

## Current repository state

The current strongest repository-backed picture is:
- the leading serious broad family remains **broad diversity-aware branch allocation with answer-support aggregation**,
- bounded diagnostic work points more specifically to **early-to-mid tree-growth control** as a major weakness of earlier variants,
- the strongest promoted line now combines:
  - anti-collapse answer-group-aware allocation,
  - soft repeat-expansion control,
  - and a deterministic output-layer repair stage,
- and the current best diagnostic stack now includes:
  - full method comparison bundles,
  - exact old-vs-current tree comparisons,
  - a fresh current-failure set against the strongest adversary baseline,
  - and output-layer repair diagnostics on the targeted remaining failures.

The current best broad baseline to beat is still:
- `self_consistency_3`

## Current best repository stance

The current repository stance is:

> **Keep the broad diversity/aggregation family as the main line, treat anti-collapse + repeat-expansion control + deterministic output-layer repair as the promoted integrated path, and use stronger controlled validation before broad superiority claims.**

## Fastest reliable start

If you want the shortest trustworthy entry path, read in this order:
1. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
2. [`docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`](docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md)
3. [`docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md`](docs/CURRENT_STATE_AND_NEXT_WORK_2026_04_19.md)
4. [`docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md`](docs/CURRENT_EXPERIMENT_RULE_2026_04_18.md)
5. [`docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md`](docs/REPOSITORY_MASTER_DASHBOARD_2026_04_18.md)
6. [`docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md)
7. [`docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`](docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md)

Then use:
- [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the canonical map,
- [`docs/README.md`](docs/README.md) for grouped navigation,
- [`scripts/CANONICAL_START_HERE.md`](scripts/CANONICAL_START_HERE.md) for runnable entry points.

## What to avoid at first

Do **not** start by reading arbitrary experiment notes, historical memos, or one-off outputs in isolation.

Do **not** assume the next best move is another unrelated new family.

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
- exact old-vs-current tree comparison artifacts,
- fresh exact current-failure bundles,
- output-layer repair diagnostics,
- and a materially stronger learner-side supervision stack than before.

### What is not solved yet
- robust broad-best ranking confirmation for the latest integrated method,
- stronger independent validation beyond targeted repaired subsets,
- honest external-baseline completeness closure,
- stable real-model leadership among close variants,
- broader paper-grade real-model evidence,
- and final current-state comparison closure after the newest integrated updates.

### Main bottleneck
The current bottleneck is now best understood as **split**:

1. in some cases, the correct answer is still absent from our tree;
2. in many targeted current-failure cases, the tree already contains the correct answer but the surfaced/evaluated output layer still needed repair.

### Best near-term direction
The current best near-term direction is:
- keep the broad diversity/aggregation family,
- preserve the current integrated promoted line,
- validate the output-layer repair beyond the targeted 16-case subset,
- and run a fresh broad comparison bundle that includes the latest integrated method fairly.

## Repository layout

- `docs/`: canonical interpretation, planning notes, grouped navigation pages, reference/baseline indexes, result/artifact indexes, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget branch allocation for LLM reasoning, where early tree shape matters, but the latest repository evidence also shows that some remaining errors are no longer pure search failures and instead live in the final output layer after correct internal reasoning has already been found.**

Current manuscript positioning is intentionally honest:

**the repository now has a strong integrated promoted line, a much better exact-failure stack, and a promising deterministic output repair layer, but it is not yet in final broad-best-claim shape because fresh independent validation and a new current full comparison bundle are still needed.**
