# Current bottlenecks (canonical)

## Primary bottleneck

The primary bottleneck is now:

> **getting the correct answer into our tree reliably enough under fixed budget while avoiding repeated same-family monopolization.**

This is now a more accurate current bottleneck description than the older learner-side framing alone.

## Why this dominates now

The project is no longer blocked mainly by infrastructure.
The repo already contains:
- frontier/controller mechanisms,
- anti-collapse and repeat-expansion control,
- exact current-failure bundles,
- broad comparison bundles,
- and a deterministic output-layer repair stage.

The current broad comparison evidence instead says that the latest integrated method still loses too often because:
- the correct answer is absent from our tree on too many hard cases,
- repeated same-family expansion is still common,
- and only a smaller remaining slice is about final selection once the right answer is already present.

## How the bottleneck appears in practice

- repeated same-family expansion on hard cases,
- weak entry of answer-distinct alternatives into the tree,
- insufficient early alternative maturation,
- absent-from-tree failures against the strongest current competitor,
- a smaller but still real present-but-not-selected slice,
- and broad matched-bundle underperformance relative to the strongest current broad-family variant.

## Explicit non-bottlenecks for the current phase

The main problem is **not** primarily:
- missing infrastructure,
- lack of output-layer instrumentation,
- inability to compare methods,
- or inability to run broader sweeps.

Those are now strong enough for serious current-state diagnosis.

## Canonical near-term response

1. Reduce absent-from-tree failures on the strongest current failure slices.
2. Reduce repeated same-family expansion without pushing generic diversity blindly.
3. Preserve answer-group-aware anti-collapse logic rather than replacing it with a generic diversity bonus.
4. Treat output-layer repair as a preserved stage, but not as the dominant broad bottleneck anymore.
5. Re-run matched comparisons after targeted hard-slice repairs rather than broad new family search.

## Practical consequence

The next efficient progress is expected to come from **better early tree-shape control and better entry/maturation of plausible alternatives**, not from immediately adding more scale or more unrelated controller families.

## Current evidence hierarchy

### 1. Targeted output-layer repair result
A targeted 16-case subset where the correct answer was already in our tree was fully repaired by a deterministic output-layer fix.

Interpretation:
- output-layer mismatch is real and important,
- but it is no longer the main broad bottleneck once that stage is repaired.

### 2. Fresh exact current full-method failure set vs best direct adversary
The fresh exact 20-case set for the latest integrated full method shows:
- correct answer absent from our tree: **11**,
- correct answer present in our tree but not selected: **9**,
- repeated same-family expansion still present: **18**,
- output-layer mismatch: **0** in that fresh exact set.

Interpretation:
- the broad remaining bottleneck has shifted back upstream into tree-generation and branch-family control.

### 3. Current full comparison bundle
The latest matched broad comparison bundle places the latest integrated full method at **#3**, not #1.

Interpretation:
- the current integrated line is promising,
- but not yet the strongest overall method.

## Best current bottleneck phrasing

The best current phrasing is:

> **the bottleneck is now concentrated in early tree-shape control under budget: preventing one branch family from monopolizing compute, getting the right answer into the tree more often, and only then improving present-but-not-selected cases.**

## Best current secondary bottleneck

A secondary bottleneck remains:

> **once the right answer is already in the tree, some cases still require better final branch selection or local answer consolidation.**

But this is no longer the first thing to fix on the broad current competitive surface.
