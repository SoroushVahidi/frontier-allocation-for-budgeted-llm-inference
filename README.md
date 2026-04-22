# adaptive-reasoning-budget-allocation

Repository for the current **NeurIPS-oriented project** on **fixed-budget adaptive test-time compute allocation for LLM reasoning**.

## Canonical project question

> **Which active branch should receive the next unit of compute, and when should the system continue versus commit?**

Equivalent local phrasing:

> **Is the next unit of compute worth spending on this branch relative to spending it elsewhere, given the current answer-group evidence?**

## Current repository identity

This repository is currently centered on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- next-step branch allocation over active branches,
- answer-group-level commit control,
- useful diversity realization under budget,
- answer-support aggregation,
- anti-collapse branch-family control,
- and reviewer-defensible comparison against both near-direct and adjacent external baselines.

This repository is **not** currently centered on the older binary revise-routing paper.

## Current state in one paragraph

The strongest current repository-backed line remains the **broad diversity-aware branch-allocation family with answer-support aggregation** under the strict-phased hard early-coverage discipline. The current broad default promoted model on the evaluated surface is **`strict_gate1_cap_k6`**. At the same time, the repository has now materially strengthened its paper-facing external baseline stack: near-direct matched-substrate baselines (`s1`, `TALE`, `L1`), official adjacent lanes such as BEST-Route, when_solve_when_verify, ReST-MCTS*, and Let's Verify Step by Step, plus a clearly caveated unofficial Q*-style adapter lane for reviewer-defense coverage.

## Fastest reliable reading path

Read these first:
1. [`QUICKSTART.md`](QUICKSTART.md)
2. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
3. [`docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md`](docs/CURRENT_DEFAULT_MODEL_AND_STRICT_PHASED_STATUS_2026_04_21.md)
4. [`docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md)
5. [`docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`](docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md)
6. [`docs/CURRENT_BASELINE_NEXT_STEPS_2026_04_21.md`](docs/CURRENT_BASELINE_NEXT_STEPS_2026_04_21.md)
7. [`docs/main_baselines.md`](docs/main_baselines.md)
8. [`docs/EXTERNAL_ADJACENT_BASELINE_BUNDLE_20260422T011400Z.md`](docs/EXTERNAL_ADJACENT_BASELINE_BUNDLE_20260422T011400Z.md)

Then use:
- [`docs/README.md`](docs/README.md) for grouped navigation,
- [`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the canonical map,
- [`scripts/README.md`](scripts/README.md) for runnable entry points,
- [`outputs/README.md`](outputs/README.md) for output-family interpretation,
- [`docs/REPOSITORY_AUDIT_AND_CLEANUP_2026_04_20.md`](docs/REPOSITORY_AUDIT_AND_CLEANUP_2026_04_20.md) for the repo audit/cleanup rationale.

## What to avoid at first

Do **not** start by reading arbitrary one-off status notes or isolated `outputs/` artifacts in isolation.

Use this interpretation rule instead:
- **Canonical** docs define the current project identity.
- **Exploratory** docs preserve active side branches and narrower ideas.
- **Historical** materials are provenance-only and should not define the current paper story.
- **Derived bounded plot folders** such as `outputs/paper_plot_data/` should not be treated as the default current broad ranking source unless the scope is stated explicitly.

For the full interpretation policy, see:
- [`docs/README.md`](docs/README.md)
- [`docs/EXPLORATORY_INDEX.md`](docs/EXPLORATORY_INDEX.md)
- [`docs/HISTORICAL_AND_ARCHIVE_POLICY.md`](docs/HISTORICAL_AND_ARCHIVE_POLICY.md)
- [`docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md`](docs/ARTIFACT_STATUS_AND_PLOT_POLICY_2026_04_20.md)

## What is already strong

- frontier/controller experimentation scaffold,
- diversity-aware controller mechanisms,
- answer-support aggregation infrastructure,
- observability-enabled semantic failure analysis,
- comparative mistake auditing against the strongest baseline,
- bounded real-model confirmation,
- strict-phased hard-coverage experiments,
- stabilized adjacent external baseline lanes,
- paper-facing external baseline documentation and aggregate bundles,
- and a stronger learner-side supervision stack than before.

## What is not solved yet

- broader independent confirmation beyond the current finalized broader pass,
- stable real-model leadership among close variants under wider conditions,
- broader paper-grade real-model evidence,
- and final manuscript-facing consolidation of the newest strict-phased default into all comparison and claim layers.

## Main bottleneck

The current broad bottleneck is still concentrated upstream in tree generation and branch-family control:
1. the correct answer is still absent from our tree too often on hard cases;
2. repeated same-family expansion still monopolizes compute too often;
3. a smaller but still important slice consists of present-but-not-selected cases once the right answer is already in the tree.

Output-layer repair remains useful, but it is no longer the dominant broad bottleneck on the current exact-failure surface.

## Repository layout

- `docs/`: canonical interpretation, baseline/reference indexes, result/artifact indexes, exploratory notes, and historical guidance.
- `scripts/`: runnable entry points and orchestration wrappers.
- `experiments/`: implementation modules and compact result notes.
- `configs/`: dataset, baseline, and experiment configuration files.
- `datasets/`: dataset policy and dataset-readiness assets.
- `external/`: external baseline references and integration notes.
- `outputs/`: generated artifacts and paper-support outputs.
- `archive/`: provenance-only historical material.

## Paper-level interpretation

The strongest current paper story is:

**fixed-budget branch allocation for LLM reasoning, where the dominant remaining problem is not just final answer repair but early tree-shape control under budget: preventing one family from monopolizing compute, getting plausible alternatives into the tree, and then selecting correctly among them.**

The current repository-wide methodological refinement is that this question is now studied under a strict phased shallow-coverage discipline, with **`strict_gate1_cap_k6`** as the current broad default promoted model on the evaluated surface. The repo is also now in a materially stronger baseline-comparison state than before, because the external comparison stack is organized into near-direct, official adjacent, and clearly caveated unofficial comparator lanes rather than a single undifferentiated baseline bucket.
