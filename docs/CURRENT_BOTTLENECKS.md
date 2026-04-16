# Current bottlenecks (canonical)

## Primary bottleneck

The primary bottleneck is **decision-aligned supervision quality** for the **next-step branch-allocation decision**.

That is slightly narrower and more accurate than simply saying “more data” or “better models.”

## Why this dominates now

The repo is no longer blocked mainly by infrastructure. It already contains:
- branch-allocation target construction,
- brute-force / near-brute-force label generation,
- merged corpora,
- canonical processed corpora,
- matched learning passes,
- hard-slice and ambiguity diagnostics,
- conservative external-supervision ingestion,
- and baseline-integration/readiness tooling.

The harder problem is that current supervision and comparator semantics still do not capture the real decision with enough fidelity:

> **Which active branch should receive the next unit of compute under the remaining budget?**

## How the bottleneck appears in practice

- noisy branch-comparison targets,
- weak opportunity-cost awareness,
- incomplete modeling of budget-feasible payoff versus slower high-ceiling branches,
- unstable near-threshold local decisions,
- limited held-out support on exact-promoted and related hard slices,
- external process-supervision signals that can shift candidate scores without reliably changing the right pairwise decisions,
- controller wins that are promising but not yet decisively robust.

## Explicit non-bottlenecks for the current phase

The main problem is **not** primarily:
- infrastructure completeness,
- lack of additional controller variants,
- lack of heavier models,
- inability to run broader sweeps,
- or inability to ingest external supervision at all.

These may matter later, but they are not the highest-leverage next fix.

## Canonical near-term response

1. Improve branch-comparison and next-step allocation target design.
2. Make comparator semantics more opportunity-cost-aware and budget-aware.
3. Preserve strong hard-slice diagnostics, especially near-tie, adjacent-rank, and exact-promoted support.
4. Continue matched comparisons against strong internal anchors and careful PRM-assisted variants.
5. Expand evidence quality on the slices that still prevent clear broad-vs-aligned separation.

## Practical consequence

The next efficient progress is expected to come from **better decision-aligned supervision, better hard-slice evidence, and cleaner comparator semantics**, not from immediately scaling compute or model size.

## Evidence summary from internal supervision work

- Medium-scale and multi-dataset brute-force label runs materially reduced the original lack-of-data problem.
- Exact-vs-approx agreement is strong enough to justify approximate-mode use as bounded supervision, but still not strong enough to declare the supervision bottleneck solved.
- Target-construction regime changes often moved results more than model-class swaps, which is strong evidence that supervision-target design remains central.
- Hard-region exact promotion improved instrumentation and localization but did not clearly solve the hardest slices.
- Hard-case richer features helped in bounded settings, showing that representation quality is part of the bottleneck but not the whole story.

## Evidence summary from ambiguity and hard-case passes

- Ternary / abstention / calibration / near-tie routing passes all improved the repo’s diagnostic sharpness.
- Some policy or fallback choices helped certain hard slices, but none closed the hardest-slice reliability gap robustly.
- Near-tie and adjacent-rank behavior remain the clearest examples of unresolved comparator difficulty.

## Evidence summary from external supervision work

- PRM800K ingestion was repaired from a degenerate mapping to a real non-degenerate external prior.
- Broad and aligned PRM variants can improve over the internal anchor in rebuilt corpus families.
- However, broad vs aligned PRM usage still does not separate clearly in the main evidence.
- Comparator-boundary PRM use produces real pair flips and is diagnostically useful, but has not clearly emerged as a superior aggregate method.
- Latest harder internal regime improved near-tie / adjacent-rank / small-margin coverage, but exact-promoted held-out support remained missing.

## Refined bottleneck statement

The best current statement is:

> **The repository is bottlenecked by decision-aligned supervision and evaluation coverage for budget-aware branch comparison, especially on the hard slices where opportunity cost actually matters.**

## What should not be overinterpreted

Do **not** interpret the repo as primarily blocked by:
- inability to build more datasets,
- inability to fit more complex learners,
- or inability to access external process supervision.

The repo’s own evidence now points to a narrower challenge: **making the supervision and evaluation reflect the actual next-step allocation decision on the slices that matter most.**
