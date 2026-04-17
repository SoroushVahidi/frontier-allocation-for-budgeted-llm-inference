# Continuation plan (2026-04-18)

## Purpose

This note answers the practical question:

> **What should we do next, in what order, and what should we not waste time on?**

It is meant to turn the current repository state into a clean continuation path.

## The main rule

The highest-leverage next work should strengthen:
- supervision target quality,
- opportunity-cost-aware comparator semantics,
- and selective ambiguity handling,

before broadening again into many more controller variants or large-scale expansions.

## Immediate next priorities

### Priority 1: improve target semantics
Focus on:
- branch-level value or penalized marginal continuation targets,
- uncertainty-aware compare/defer derivation,
- provenance-aware target design,
- and softer or structured treatment for hard ambiguous pairs.

### Priority 2: tighten defer / unresolved behavior
Focus on:
- less diffuse defer regions,
- better calibration or error-aware gating,
- and better alignment between defer triggers and true hard ambiguous cases.

### Priority 3: improve data use before broad expansion
Focus on:
- selective exact relabeling of disagreement / near-tie / top-action-flip cases,
- provenance-aware weighting,
- and stronger use of current branch-level / frontier-level artifacts.

## Secondary priorities

### Priority 4: stronger branch-level value experiments
Test whether branch-level value supervision with derived compare/defer decisions outperforms brittle pairwise target paths on the hardest slices.

### Priority 5: fair comparison against current strong scaffold
Every promising new target design should be compared against:
- current pairwise default,
- tie-aware post-hoc deferral,
- specialist pointwise fallback,
- and the most relevant bounded target-fidelity baselines.

### Priority 6: only then broaden external evidence and datasets
After target semantics sharpen, then:
- add datasets with new ambiguity regimes,
- broaden external baseline comparisons,
- and expand real-model evidence.

## What not to prioritize now

Do not spend the next main pass on:
- another broad model-class sweep,
- another generic fallback variant,
- broad hard-label replacement,
- or large-scale dataset growth without better target design.

These are not the highest-value next moves according to the current repository state.

## Suggested bounded next experiment sequence

### Sequence A: target-design tightening
1. branch-specific penalized marginal continuation targets,
2. better compare/defer derivation from value + uncertainty,
3. bounded validation on accepted/coverage and hard slices.

### Sequence B: branch-level value supervision
1. build branch-level value target path,
2. derive pairwise and defer decisions from value gaps,
3. compare to current strong scaffold.

### Sequence C: structured ambiguity refinement
1. unresolved / partial-order treatment on hardest slices,
2. provenance-aware weighting,
3. exact relabeling only on highest decision-value states.

## Paper-facing continuation logic

The paper should continue to emphasize:
- fixed-budget allocation as the core framing,
- branch-priority / next-step allocation as the conceptual center,
- supervision-target diagnosis as the main challenge,
- and ambiguity-aware selective control as the crucial unresolved region.

Avoid drifting back into:
- generic “more reasoning helps”,
- generic controller proliferation,
- or old binary revise-routing framing.

## Safe next-step summary

A safe summary is:

> The next efficient progress is expected to come from better target semantics and cleaner selective ambiguity handling, not from broader scale or more controller families.
