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

The repository now has a clearer paper-facing separation than before. The broader strict-phased default-decision pass still identifies **`strict_gate1_cap_k6`** as the current broad promoted default on its own evaluated surface, but the explicit in-house winner artifact defines **`strict_f3`** as the repository’s single canonical **our method**. The paper-facing comparison layer is now also materially stronger: a fair near-direct ranking, a separate published adjacent-baseline table, a discussion-only recent-paper layer, a direct-baseline fairness audit, and an explicit simple-scaling coverage audit that states no extra direct baseline was needed.

## Fastest reliable reading path

Read these first:
1. [`QUICKSTART.md`](QUICKSTART.md)
2. [`docs/CANONICAL_START_HERE.md`](docs/CANONICAL_START_HERE.md)
3. [`docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md`](docs/CURRENT_OUR_METHOD_STATUS_20260422T001521Z.md)
4. [`docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md`](docs/FINAL_INHOUSE_METHOD_DECISION_20260422T001521Z.md)
5. [`docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md`](docs/PAPER_FACING_BASELINE_COMPARISON_PACKAGE_20260422T231500Z.md)
6. [`docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md`](docs/FINAL_EVALUATION_FAIRNESS_AND_CLAIM_BOUNDARIES_20260422T235900Z.md)
7. [`docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md`](docs/SIMPLE_SCALING_BASELINE_COVERAGE_DECISION_20260422T235959Z.md)
8. [`docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md`](docs/CURRENT_RESULTS_AND_ARTIFACTS_INDEX_2026_04_20.md)
9. [`docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md`](docs/CURRENT_REFERENCES_AND_BASELINES_INDEX_2026_04_20.md)

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
- bounded real-model confirmation,
- strict-phased hard-coverage experiments,
- stabilized adjacent external baseline lanes,
- explicit in-house winner selection,
- paper-facing baseline separation and claim-boundary artifacts,
- and a stronger learner-side supervision stack than before.

## What is not solved yet

- broader independent confirmation beyond the current finalized broader pass,
- stronger budget-sweep / stability / failure-mechanism robustness coverage,
- broader paper-grade non-math dataset breadth in the final reported results,
- and final manuscript-facing consolidation of the latest comparison and fairness artifacts into the paper text.

## Main bottleneck

The current broad bottleneck is still concentrated upstream in tree generation and branch-family control:
1. the correct answer is still absent from our tree too often on hard cases;
2. repeated same-family expansion still monopolizes compute too often;
3. a smaller but still important slice consists of present-but-not-selected cases once the right answer is already in the tree.

Output-layer repair remains useful, but it is no longer the dominant broad bottleneck on the current exact-failure surface.

## Repository layout

- `docs/`: canonical interpretation, planning notes, navigation pages, baseline/reference indexes, result/artifact indexes, exploratory notes, and historical guidance.
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

Current front-door naming rule:
- **our method** = `strict_f3`
- **current broad promoted strict-phased default on its evaluated surface** = `strict_gate1_cap_k6`

This separation keeps the repo’s paper-facing interpretation cleaner and more honest.
