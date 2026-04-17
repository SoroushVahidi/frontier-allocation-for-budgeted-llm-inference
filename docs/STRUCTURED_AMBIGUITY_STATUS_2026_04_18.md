# Structured ambiguity status (2026-04-18)

## Purpose

This note summarizes the repository’s current understanding of ambiguity handling after the recent sequence of bounded hard-case passes.

The goal is to clarify what we now believe about the hardest close-call pairs.

## Main conclusion

The strongest current conclusion is:

> **the hardest branch-comparison pairs are better understood as structured ambiguity cases than as ordinary noisy binary labels.**

## Why this conclusion is now stronger

Several bounded passes point in the same direction:

### Binary-forced treatment
Binary-forced comparison remains strong on some headline metrics, but it is likely too harsh on the hardest close-call region.

### Hard tie-aware treatment
A Davidson-style close-call tie rule improved the honesty of ambiguity treatment and gave meaningful ternary coverage, but hard ternary labels alone did not close the overall gap.

### Soft tie-aware treatment
Soft probabilistic tie-aware supervision improved some accepted/coverage behavior over hard ternary treatment, which suggests graded supervision is closer to the right inductive bias for hard pairs.

### Strict Cohere adjudication
Strict external adjudication gating avoided the prior degradation but did not move the main metrics, which weakens the idea that stronger one-off relabeling alone will solve the ambiguity region.

## What this means conceptually

The repository should increasingly treat the hardest pairs as belonging to one of these categories:
- close directional preference,
- legitimate tie / no-preference,
- unresolved / incomparable because evidence is insufficient,
- or supervision objects whose trust should be weighted rather than forced.

This is a more faithful picture than treating every pair as a clean binary winner/loser label.

## Most plausible next structured step

The current best next structured step is:

> **a bounded unresolved / incomparability pass or another abstention-aware structured objective.**

Reason:
- binary was too rigid,
- hard tie was better but too coarse,
- soft tie was better than hard tie but still not enough,
- so the next reasonable question is whether some pairs should remain explicitly unresolved.

## What not to conclude

Do not conclude yet that:
- tie-aware supervision is a full solution,
- soft probabilistic targets are already enough,
- or external adjudication is the key missing ingredient.

The evidence is more modest:
- structured ambiguity treatment is more realistic,
- but the final winning structured formulation is still unresolved.

## Practical repo rule

For future bounded passes on hard pairs, prefer designs that:
- preserve easy-case sharpness,
- explicitly isolate the hardest ambiguity region,
- and avoid broad hard-label overrides unless the evidence is unusually strong.

## Neighbor docs

- `CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `WHAT_IS_NOT_WORKING_NOW.md`
- `HARD_PAIR_SUPERVISION_CLEANUP_NEXT_STEP.md`
- `REPOSITORY_AUDIT_AND_NEXT_STEP_2026_04_18.md`
