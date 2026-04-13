# Paper Direction Notes

## Why this note exists

This repository already supports the manuscript:

**When to Revise: Cost-Aware Adaptive Routing for LLM Reasoning**

That manuscript is centered on **query-level binary adaptive routing** between a cheap reasoning route and a revise-based route under a budget.

We may reuse repository infrastructure, some datasets, and some prior results as background or supporting context, but the next manuscript must be **materially different in its main problem, main method, and main experimental story**.

## Scope of the current manuscript

The current manuscript is centered on:

- query-level inference control
- binary cheap-vs-revise routing
- selective escalation / deciding when to revise
- fixed vs adaptive vs oracle comparisons
- v5 / v6 / v7 style adaptive routing policies
- the matched manuscript regimes
- regime-dependent routing headroom and answer-error signals

## What the next paper should NOT be

The next paper should not be framed as:

- a better learned router for the same binary cheap-vs-revise setup
- an improved v5 / v6 / v7 paper
- the same four-regime routing paper with stronger classifiers
- another manuscript whose main question is still when to revise

If the new paper keeps the same main problem statement, same action space, same main figures/tables, and same headline claims, it is too close.

## Recommended framing for the next paper

The next paper should focus on:

**adaptive branch-level compute allocation for LLM reasoning under budget**

Recommended emphasis:

- partial reasoning branches or states
- deciding where the next unit of compute should go
- actions such as expand, verify, prune, or stop
- branch scoring or branch ranking
- marginal utility of additional compute
- controller decisions over a frontier of branches

## Clean distinction

- Current manuscript: **When to revise?**
- Next paper: **Where should the next unit of reasoning compute go?**

## Allowed reuse

Allowed as infrastructure or background:

- repository codebase
- dataset loaders
- evaluation utilities
- stored outputs
- generic budgeted-inference motivation
- selected older results only as supporting context

The new paper must have a different main problem statement, main method, and main experimental story.

## Writing rule

Do not reuse the old manuscript's main:

- title framing
- abstract framing
- problem statement wording
- main figures/tables
- central empirical section structure

## Repo guidance

For artifacts related to the next paper, prefer names involving:

- branch
- controller
- allocation
- frontier
- marginal_utility

Avoid organizing the new work as just another variant of the old revise-routing policy stack.
