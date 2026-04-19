# Current experiment rule (2026-04-18)

## Purpose

This note freezes the current repository rule for what should and should not count as a valid next experiment.

It exists to prevent the project from drifting into repeated local tweaks or unrelated new families without strengthening the current leading method line.

## Current scientific question

The current question is:

> **Can the broad diversity/aggregation family become a stable, real-model-confirmed broad winner under fixed-budget next-step branch allocation?**

Equivalently:

> given that global diversity-aware allocation and answer-support aggregation are now the leading serious method direction, how do we make diversity reliably materialize, rank diverse evidence correctly, and confirm the win under real generation noise?

## What the repository has already established

The repository has already established all of the following:
- many earlier nearby target/control refinements did not clearly produce a broad successor,
- observability-enabled runs now support real semantic failure diagnosis,
- self-consistency’s broad advantage was diagnosed mainly as broader search/diversity plus answer aggregation and reduced premature commitment,
- bounded local self-consistency-style rescue was useful but not enough,
- a **broad diversity/aggregation family** became the first branch-allocation family to look like a serious broad competitor,
- stricter simulator confirmation held up for that family,
- and bounded real-model confirmation kept the family alive as promising, while showing that real-model evidence is still too small and exact broad-variant leadership is not yet fully settled.

## Admissible next experiments

A next experiment is admissible only if it directly strengthens or tests the current leading broad diversity/aggregation family.

That means it should do at least one of these:
1. confirm the broad family under larger but still cost-controlled real-model runs,
2. improve **realized diversity** so explored branches become more genuinely answer-distinct under budget,
3. improve ranking/selection when diversity already exists,
4. improve answer-support aggregation so wrong concentration happens less often,
5. study commit/selection instability under real generation noise,
6. compare the currently frozen broad variants (`strong_v1` main tracked candidate, `v1` ablation/context sibling) under stronger realism or robustness settings,
7. build residual-loss casebooks showing why self-consistency or other strong baselines still beat the broad family.

## What is not admissible right now

The following should not be the default next move unless new evidence specifically justifies them:
- another unrelated target-weighting tweak,
- another generic defer-policy sweep,
- another local hard-case rescue that does not affect the broad family,
- another new controller family,
- another simulator-only campaign that postpones realism confirmation,
- or broad dataset expansion unrelated to validating the current main family.

These are not banned forever. They are just not currently the highest-leverage default work.

## Required evidence before opening a new method family

Before adding a new method family, require at least one of these:
- clear evidence that the broad diversity/aggregation family fails fundamentally under larger real-model confirmation,
- a documented reason why diversity-aware allocation plus answer-support aggregation cannot be repaired into a strong broad competitor,
- or strong external theoretical/empirical support that the current family is pointed at the wrong object entirely.

If that evidence is absent, do not introduce a new family.

## Why real-model confirmation is currently mandatory

The repository is past the point where another simulator-only success is enough.

The leading family already looks strong in simulator confirmation. What is missing is reliable confirmation under actual provider-backed generation, where diversity realization and commit stability become noisier and more important.

That means the right next step is to increase real-model trustworthiness and residual-loss understanding, not to continue broad simulator-only method exploration.

## Practical rule

Use this rule of thumb:

> **No new method family unless larger real-model confirmation undermines the current one. No new broad sweep unless it strengthens the broad diversity/aggregation family or explains why it still loses.**

## Current recommended method stance

Until stronger evidence arrives, the repository should operate under this stance:

> **treat broad diversity-aware allocation with answer-support aggregation as the current main method family, with `broad_diversity_aggregation_strong_v1` as the main tracked candidate and `broad_diversity_aggregation_v1` as the main ablation/context sibling, while prioritizing Cohere/Gemini realism confirmation and diversity-realization hardening.**
