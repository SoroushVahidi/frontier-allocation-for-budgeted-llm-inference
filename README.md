# adaptive-reasoning-budget-allocation

Research repository for the current **NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Canonical project question

> **Which active branch should receive the next unit of compute, and when should the system continue versus commit?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending on this branch relative to spending it elsewhere, given the current answer-group evidence?**

## Current repository identity

The current repository is centered on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- next-step branch allocation over active branches,
- answer-group-level commit control,
- useful diversity realization under budget,
- answer-support aggregation,
- anti-collapse branch-family control,
- and real-model confirmation of branch-allocation policies.

This repository is **not** currently centered on the older binary revise-routing paper.

## Current promoted line

The strongest current repository-backed line remains the **broad diversity-aware branch-allocation family with answer-support aggregation**.

The current integrated path adds:
- anti-collapse allocation,
- soft repeat-expansion control,
- deterministic output-layer repair,
- and a strict phased early-coverage discipline.

On the currently promoted broad surface, the current default promoted model is:

- **`strict_gate1_cap_k6`**

## Fastest reliable reading path

Read these first, in order:
1. [`QUICKSTART.md`](QUICKSTART.md)
2. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
3. [`docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md`](docs/CURRENT_PROMOTED_METHOD_LINE_2026_04_20.md)
4. [`docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`](docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md)
5. [`docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md`](docs/FINAL_STRICT_PHASED_DEFAULT_DECISION_EVAL_20260421T042913Z.md)
6. [`docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md)
7. [`docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md`](docs/CURRENT_EXPERIMENTS_INDEX_2026_04_21.md)
8. [`docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`](docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md)

Then use:
- [`docs/README.md`](docs/README.md) for grouped navigation,
- [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the canonical repo map,
- [`docs/CANONICAL_INSTALL_AND_DEV.md`](docs/CANONICAL_INSTALL_AND_DEV.md) for setup and development commands,
- [`scripts/README.md`](scripts/README.md) for runnable entry points,
- [`outputs/README.md`](outputs/README.md) for output-family interpretation.

## What to avoid at first

Do **not** start by reading arbitrary one-off status notes or isolated `outputs/` artifacts in isolation.

Use this rule instead:
- **Canonical** docs define the current project identity.
- **Exploratory** docs preserve active side branches and narrower ideas.
- **Historical** materials are provenance-only and should not define the current paper story.
- **Derived bounded plot folders** such as `outputs/paper_plot_data/` should not be treated as the default broad ranking source unless the scope is stated explicitly.

## What is already strong

- frontier/controller experimentation scaffold,
- diversity-aware controller mechanisms,
- answer-support aggregation infrastructure,
- observability-enabled semantic failure analysis,
- comparative mistake auditing against the strongest baseline,
- bounded real-model confirmation,
- exact old-vs-current tree comparison artifacts,
- targeted current-failure bundles,
- output-layer repair diagnostics,
- strict-phased hard-coverage experiments,
- strict force/gate comparison bundles,
- capped-family anti-collapse experiments,
- and a stronger learner-side supervision stack than before.

## What is not solved yet

- broader independent confirmation beyond the current finalized broader pass,
- honest external-baseline completeness closure,
- stable real-model leadership among close variants under wider conditions,
- broader paper-grade real-model evidence,
- and full manuscript-facing consolidation of the newest strict-phased default into all comparison and claim layers.

## Main bottleneck

The current broad bottleneck is still concentrated upstream in tree generation and branch-family control:
1. the correct answer is still absent from our tree too often on hard cases;
2. repeated same-family expansion still monopolizes compute too often;
3. a smaller but still important slice consists of present-but-not-selected cases once the right answer is already in the tree.

Output-layer repair remains useful, but it is no longer the dominant broad bottleneck on the current exact-failure surface.

## Repository layout

- `docs/`: canonical interpretation, navigation pages, planning notes, reference/baseline indexes, result indexes, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Maintenance rule

When the current project phase changes materially, update these together:
- `README.md`
- `QUICKSTART.md`
- `docs/README.md`
- `docs/CANONICAL_START_HERE.md`
- `docs/REPO_MAP.md`
- `docs/CANONICAL_INSTALL_AND_DEV.md`
- `scripts/README.md`
- `outputs/README.md`

That keeps the repository front door aligned with the actual project state.
