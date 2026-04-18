# Current experiment rule (2026-04-18)

## Purpose

This note freezes the current repository rule for what should and should not count as a valid next experiment.

It exists to prevent the project from drifting into repeated bounded tweaks without answering the current scientific question.

## Current scientific question

The current question is:

> **For fixed-budget next-step branch allocation, should the target/controller optimize continuation value alone, or continuation value with a bounded completion-aware correction in near-tie disagreement states?**

Equivalently:

> when visible branch-semantic quality and immediate continuation value diverge on a hard close state, what should the system optimize?

## What the repository has already established

The repository has already pressure-tested many nearby target/control ideas around the same local family.

The current bounded evidence supports all of the following:
- recent nearby refinements did not clearly displace the multistep-k3 line as a broad successor,
- fresh observability-enabled runs now permit real semantic branch diagnosis,
- bounded worst-failure casebooks show that method and oracle branches can diverge in visible completion/answer-completeness,
- bounded completion-aware decision logic revealed a real signal,
- and the bounded oracle-mismatch study supports **augmenting** the continuation-value oracle rather than replacing it globally.

## Admissible next experiments

A next experiment is admissible only if it directly helps answer the current question above.

That means it should do at least one of these:
1. improve answer/final-state observability on contested branch-allocation states,
2. compare continuation-only, completion-aware, and hybrid target/oracle definitions on fresh observability-enabled runs,
3. manually or automatically adjudicate disagreement states where visible semantic branch quality and continuation value diverge,
4. test a bounded hybrid target/controller that keeps continuation value as the default and applies a completion-aware correction only in hard disagreement slices,
5. validate whether the disagreement region is genuinely localized (for example near-ties only) or broader than currently estimated.

## What is not admissible right now

The following should not be the default next move unless new evidence specifically justifies them:
- another nearby target-weighting tweak,
- another generic defer-policy sweep,
- another auxiliary target family in the same bounded neighborhood,
- another broad controller-variant pass without new target-definition content,
- another attempt to mine old non-instrumented artifacts for semantics,
- or broad dataset expansion before the target-definition question is clarified.

These are not banned forever. They are just not currently the highest-leverage default work.

## Required evidence before introducing a new target/controller family

Before adding a new target/controller family, require at least one of these:
- a clear pattern in fresh semantic failure cases that the current hybrid-oracle question cannot express,
- a documented reason why the current continuation-plus-bounded-completion framing is inadequate,
- or strong external theoretical support that changes the target object more fundamentally than current nearby variants.

If that evidence is absent, do not introduce a new family.

## Why observability-enabled semantic diagnosis is currently mandatory

The repository now has enough evidence that proxy-only diagnosis is not sufficient.

Fresh observability-enabled runs and bounded answer recovery now allow contested cases to be inspected semantically. That means the right next step is to understand those cases and use them to settle the target-definition question, rather than continuing broad bounded tweaks.

## Practical rule

Use this rule of thumb:

> **No new method family unless it directly answers the oracle-mismatch / semantic-completion question. No new broad sweep unless the target-definition memo changes first.**

## Current recommended target stance

Until stronger evidence arrives, the repository should operate under this stance:

> **keep continuation value as the core target, and study bounded completion-aware correction only in disagreement slices, especially near-ties.**
