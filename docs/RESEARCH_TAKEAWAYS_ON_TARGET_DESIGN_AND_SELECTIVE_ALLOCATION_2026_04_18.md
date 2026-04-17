# Research takeaways on target design and selective allocation (2026-04-18)

## Purpose

This note preserves the most important research takeaways from recent literature-oriented analysis about the current repository bottleneck.

The goal is to avoid losing the central ideas behind the current target-design discussion, especially around:
- supervision-target redesign,
- value-style targets,
- selective abstain / defer control,
- and better use of existing supervision artifacts.

## Main high-level conclusion

The strongest current research takeaway is:

> **the bottleneck should be framed as a selective marginal-allocation problem, not as ordinary routing or plain binary pair classification.**

In repository terms:
- the deployed decision is not simply “is branch A better than branch B?”,
- it is closer to “which active branch should receive the next unit of compute under the current remaining budget, and when should the system explicitly avoid forced commitment?”

## Most important supervision takeaway

The highest-leverage shift is:

> **move away from brittle binary pairwise winner labels and toward budget-conditioned marginal continuation value with an explicit unresolved / defer region.**

This can still use pairwise comparisons, but pairwise comparison should increasingly be treated as a *derived decision layer* rather than the primary supervision object.

## Key ideas worth keeping

### 1. Budget-conditioned branch value is more faithful than forced pairwise wins
A more faithful target is something like:
- per-branch residual / marginal continuation value,
- conditioned on remaining budget,
- optionally penalized by compute price.

This is closer to the deployed action than a raw binary pair label.

### 2. Pairwise labels should increasingly be derived from value separation
Rather than supervising only:
- `A beats B`
- `B beats A`

a stronger supervision path is:
- predict branch-level value or marginal continuation value,
- derive pairwise direction from value difference,
- and derive defer / unresolved from interval overlap or insufficient value separation.

### 3. The hardest pairs should not always be forced into a total order
Near-ties, exact-vs-approx disagreement cases, and low-margin pairs should increasingly be treated as:
- tie-aware,
- relaxed / soft,
- partial-order,
- or explicitly unresolved supervision objects.

### 4. Raw score magnitude is not automatically confidence
If value targets are used, predicted magnitude should not be interpreted as confidence without additional calibration or reliability modeling.

Safer interpretation:
- value gap is a decision signal,
- confidence should come from calibration, uncertainty estimation, residual/error prediction, provenance, or explicit defer training.

### 5. Existing data should be reused more intelligently before broad new data expansion
The literature-backed recommendation is to get more value from the current label pool by:
- keeping provenance explicit,
- mixing exact and approximate supervision more carefully,
- spending exact relabeling budget on near-ties and disagreement states,
- and converting current pair pools into candidate-set / frontier-level supervision where possible.

## Most promising target-design directions

### Direction A: penalized marginal continuation value
A strong target family is:
- estimate one-step or residual continuation gain,
- subtract a compute-price term,
- compare branches under budget-aware marginal utility.

This is the cleanest value-style extension of the current penalized-marginal line.

### Direction B: soft / relaxed pairwise supervision
If pairwise training remains primary, hard winner labels should increasingly be replaced with:
- relaxed probabilities,
- interval targets,
- or tie-aware set-valued supervision,
especially in low-margin or disagreement regions.

### Direction C: partial-order / unresolved supervision
For the hardest branch comparisons, the model should be allowed to represent:
- no confident edge,
- incomparability,
- or unresolved status,
instead of being forced into full total-order supervision.

### Direction D: branch-level value + defer
A particularly promising combined design is:
- branch-level value head,
- uncertainty or error head,
- and explicit defer decision when value separation is not reliable enough.

## Best immediate research implication for this repository

The strongest next-step methodological interpretation is:

> **the next method should probably learn budget-conditioned branch-level marginal continuation value, keep explicit uncertainty/provenance, and derive compare-or-defer decisions from value separation rather than from brittle hard pair labels.**

This is stronger than merely softening binary labels.

## Why this matters for the repo's current bottleneck

The current repository bottleneck is already documented as supervision-target quality / proxy-label mismatch for the next-step branch-allocation decision.

The literature takeaways here strengthen the interpretation that:
- the bottleneck is semantic,
- the current hardest region is structurally ambiguous,
- and the training target should look more like selective budget-aware continuation-value estimation than like ordinary classification.

## Practical experiment ideas worth preserving

### 1. Budget-conditioned value-head experiment
Train a branch-level value model for marginal continuation gain under remaining budget, then derive pairwise/defer decisions from predicted value differences.

### 2. Relaxed pairwise labels on current artifacts
Keep the current pairwise pipeline, but replace hard wins on low-margin or disagreement pairs with soft or interval-valued targets.

### 3. Partial-order supervision on hardest slices
Treat only confident relations as true edges and let near-tie pairs remain unresolved.

### 4. Provenance-aware weighting
Assign different trust levels to:
- exact labels,
- bounded-exact labels,
- approximate proxy labels,
- and disagreement-prone rows.

### 5. Selective relabeling by decision value
Use bounded exact relabeling budget primarily on:
- exact-vs-approx disagreement,
- near-ties,
- adjacent-rank states,
- and top-action-flip cases.

## Current safe repository-facing wording

A safe summary to reuse later is:

> The most promising target-design direction is to model next-step branch allocation as budget-conditioned selective marginal allocation, using branch-level continuation-value signals, softer or structured supervision on ambiguous pairs, and explicit defer/unresolved handling rather than forcing all hard comparisons into binary winner labels.

## What not to overclaim yet

Do not claim yet that:
- branch-level value supervision is already the settled canonical winner,
- partial-order / abstention formulations are already empirically closed,
- or raw predicted value magnitude can already be trusted as confidence.

These remain strong research directions, not finished conclusions.

## Recommended next repository step

The next good implementation/evaluation step is to test one of these in a bounded, auditable way:
1. branch-level budget-conditioned value prediction with derived compare/defer,
2. relaxed pairwise targets tied to provenance and disagreement,
3. or a partial-order / unresolved treatment on the hardest branch-comparison slices.
