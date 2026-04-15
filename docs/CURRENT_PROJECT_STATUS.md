# Current project status (canonical)

## Scope

This is the canonical status note for the current NeurIPS-oriented project on:
- fixed-budget adaptive test-time compute allocation,
- cross-controller frontier allocation,
- action-conditional branch/controller decisions under a global compute budget.

## Core project goal

Learn and evaluate allocation policies that decide where the next unit of compute should go, while respecting a fixed budget and avoiding allocation collapse.

## What has been built (established)

- Runnable frontier/controller experimentation scaffold.
- Anti-collapse controller mechanisms and corresponding audits.
- Branch-scorer experimentation stack (pointwise, pairwise BT, tie-aware/reliability variants).
- Dataset and baseline integration/readiness tooling.
- Oracle/frontier comparative audit pathways.

## What has been learned so far

1. The framing is sound: cross-controller frontier allocation is a distinct and useful problem framing.
2. Anti-collapse controller design matters for realized budget use.
3. Pairwise BT branch scoring is one of the strongest active learned directions.
4. External warm-start and reliability-aware variants are promising but mixed.
5. Robustness remains uneven across seeds/budgets/datasets; no settled universal winner.

## Main unresolved issue

The main unresolved issue is supervision target quality:
- proxy-label mismatch,
- label noise/alignment problems,
- insufficient calibration of decision-time allocation signal.

## Canonical methodological interpretation

The project should now be framed around:

> **Is the next unit of compute worth spending here?**

rather than only generic branch ranking.

Ideal target is expected marginal utility of the next compute action, but for first implementation stability the preferred approximation is a budget-conditioned binary stop-vs-act decision.

## Current best next implementation direction

- Implement a lightweight budget-conditioned stop-vs-act controller.
- Use uncertainty both as:
  - input features for decisions,
  - and training-example filtering/reweighting signal.
- Keep pairwise BT branch scoring as an active baseline/companion line, not the sole canonical next controller.

## Practical implication before heavy scaling

Before large-scale label generation or heavier neural models, prioritize bounded supervision-target design and label-quality experiments.
