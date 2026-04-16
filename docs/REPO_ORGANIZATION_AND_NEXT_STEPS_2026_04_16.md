# Repository organization and next steps — 2026-04-16

This note is a canonical cleanup/orientation snapshot for the current state of the repository.

## What this repository is now

This repository is now best understood as a research platform for:
- fixed-budget adaptive test-time compute allocation for LLM reasoning,
- cross-controller frontier allocation,
- next-step branch allocation over active frontier states,
- and careful cost-aware comparison against strong adjacent baselines.

The central project question remains:

> Which active branch should receive the next unit of compute?

A useful equivalent wording is:

> Is spending the next unit of compute on this branch better than the best alternative use of that unit?

## What has been accomplished

The repo now has several major strengths:

### 1) Stronger surrounding infrastructure
- Canonical project/status/safe-claim docs are in place.
- Dataset coverage is stronger, including math, science, planning-style, and new supervision-source preparation layers.
- Adjacent baseline coverage is materially stronger via import-validated adjacent protocols.

### 2) Much stronger external-baseline story
Adjacent baseline integration now includes strong neighboring methods through validated or bounded protocols, including routing/cascading, best-of-N / MoB, solve-vs-verify, ReST-MCTS, and OpenR style comparisons.

This means the project is no longer mainly weak because of missing neighboring baselines.

### 3) Label-data infrastructure is now real
The repo now includes:
- a brute-force / near-brute-force branch-comparison label generator,
- exact-vs-approx comparison capability on tiny feasible states,
- pilot learner training on generated labels,
- and a bounded real medium-scale GSM8K-backed label-data report.

So the label-data problem has moved from “missing machinery” to “improving target quality and scaling evidence.”

## What is still not solved

The main unresolved issue is still:

> supervision-target quality for next-step branch allocation.

That includes:
- proxy-label mismatch,
- near-tie / low-margin ambiguity,
- imperfect opportunity-cost modeling,
- calibration drift across budgets / seeds / datasets,
- and only moderate downstream learner performance even after a real medium-scale label run.

So the right interpretation is:
- infrastructure is much better,
- baseline coverage is much better,
- label generation exists and has been demonstrated,
- but target quality is still the scientific bottleneck.

## Current positive points

The strongest positive points right now are:
- the project framing is clear and distinct,
- the repo is no longer mainly blocked by missing adjacent baselines,
- there is now a real auditable supervision-data path,
- the exact-vs-approx check gives bounded evidence that approximate labels are useful,
- and the repo is in a serious paper-development state rather than a vague exploratory state.

## Current shortcomings

The most important shortcomings are:
- safe-claim wording is still slightly uneven across some docs,
- a few older notes still lean too much toward stop-vs-act wording,
- the learned allocation results are still promising-but-moderate rather than decisive,
- and evidence is not yet broad enough across datasets / seeds / budgets to claim closure of the target-quality bottleneck.

## Organization rule for the repo

Interpret the repository in three layers:

### Canonical
Use these first when understanding the project:
- `README.md`
- `docs/CURRENT_PROJECT_STATUS.md`
- `docs/CURRENT_BOTTLENECKS.md`
- `docs/CURRENT_SAFE_CLAIMS.md`
- `docs/CURRENT_STRATEGIC_UPDATE_2026_04_16.md`
- `docs/BRUTEFORCE_LABEL_DATA_STATUS.md`
- this note

### Supporting but still current
Use these for detailed operational context:
- dataset integration and dataset status docs,
- external baseline integration notes,
- brute-force label-generator docs,
- script readmes and run recipes.

### Exploratory / historical
Use these only when needed for provenance or specific experiment lines:
- old-track binary revise-routing material,
- superseded memo-style notes,
- method-specific exploratory branches that are not canonical project interpretation.

## What we should do next

The best next major research step is not more ruleware.

The right next direction is:
1. scale the branch-allocation supervision corpus across more datasets / budgets / seeds,
2. train learned allocators on the larger merged corpus,
3. analyze where the remaining target noise comes from,
4. strengthen uncertainty-aware / low-margin-aware learning,
5. and only then decide whether additional deterministic structure is needed.

## Practical planning advice

When deciding what to prioritize:
- prefer tasks that improve branch-comparison supervision,
- prefer tasks that produce auditable evidence,
- prefer multi-dataset label scaling and learning over more ad hoc heuristic rules,
- and keep stop-vs-act as a helper view rather than the full conceptual center.

## Bottom-line repo summary

The repository is now:
- well past the initial scaffolding stage,
- strong enough for serious paper development,
- materially stronger on datasets, baselines, and supervision-data infrastructure,
- but still scientifically bottlenecked by supervision-target quality for next-step branch allocation.
