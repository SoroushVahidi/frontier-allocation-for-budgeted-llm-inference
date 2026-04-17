# Repository audit and next step (2026-04-18)

## Purpose

This note records a compact repository-facing audit after the recent hard-pair cleanup, Cohere adjudication, Davidson-style tie-aware, and soft probabilistic tie-aware passes.

The goal is to keep the repo continuation-oriented: what is clean, what is noisy, what is now clearly historical, and what should happen next.

## High-level audit

### What is in good shape

- The repository now has a clearer canonical identity around **fixed-budget next-step branch allocation**.
- The core working-set docs are easier to navigate than before.
- Historical script entry points have been physically separated into `archive/`.
- Method notes now cover several bounded hard-case intervention passes instead of leaving them implicit.
- The dataset-expansion plan is documented and no longer mixed with the immediate supervision bottleneck.

### What is still the central bottleneck

The central bottleneck is still:

> **hard ambiguous branch-comparison supervision**

In the simplest repo-facing interpretation:
- easy pairs are mostly usable,
- the hardest near-tie / adjacent-rank pairs are still the most fragile part of the pipeline,
- and stronger reasoning about ambiguity has helped more than generic model-class expansion.

## What the recent method passes changed

### 1. Cohere adjudication is no longer an unknown

A bounded Cohere adjudication path was tested, then re-tested with a stricter policy.

Conservative interpretation:
- loose hard replacement was harmful,
- very strict gating became safe but weak,
- so bounded Cohere relabeling is **not** currently the best default fix for the bottleneck.

### 2. Hard ties were a meaningful structural improvement

The Davidson-style close-call tie pass improved the honesty of hard-case treatment relative to forcing binary labels everywhere.

Conservative interpretation:
- allowing a real tie region is more natural than forcing every hard pair into a winner label,
- but hard ternary treatment alone does not close the global performance gap.

### 3. Soft tie-aware supervision helped more than hard ternary alone

The soft probabilistic tie-aware pass improved some accepted/coverage-style behavior relative to hard ternary treatment.

Conservative interpretation:
- graded supervision is more plausible than hard labels on the hardest close calls,
- but the current soft regime still did not produce a robust headline win over the strongest binary/top-1 anchor.

## Current best method interpretation

The strongest current interpretation is now:

> **the hardest pairs should probably be treated as structured ambiguity objects, not as ordinary binary classification examples.**

That means the repo should now lean more toward:
- tie-aware structure,
- soft/graded supervision,
- abstention / unresolved regions,
- and reliability-aware hard-pair cleanup,

and less toward:
- generic controller-family expansion,
- generic model-class swaps,
- or broad hard-label replacement.

## Current practical next step

The best next step is now:

> **a bounded partial-order / unresolved comparison pass, or a similarly explicit abstention-aware structured treatment for the hardest branch pairs.**

This is a stronger fit than another broad relabeling pass because the recent evidence suggests the hardest pairs are not merely mislabeled—they are often genuinely too close to force cleanly.

## Organization recommendation

When continuing from this repo, prefer this reading path:
1. `CURRENT_METHOD_SUMMARY_AND_GAPS.md`
2. `WHAT_IS_NOT_WORKING_NOW.md`
3. `HARD_PAIR_SUPERVISION_CLEANUP_NEXT_STEP.md`
4. `STRUCTURED_AMBIGUITY_STATUS_2026_04_18.md`
5. the most relevant method-status note from `METHOD_STATUS_INDEX.md`

## Canonical writing rule

For manuscript-facing summaries, avoid saying that the bottleneck is simply “better models” or “more data”.

The safer current wording is:

> the bottleneck is principled treatment of hard ambiguous pairwise branch comparisons under budgeted reasoning.
