# Current leading direction (2026-04-17)

## Purpose

This note gives the shortest current answer to three questions:

1. What direction currently looks strongest?
2. What recent directions were tested and did not clear the continuation bar?
3. What should collaborators and future implementation passes focus on next?

## Current leading direction

The current leading direction is:

> **bounded multi-step branch-utility targets for next-step branch allocation**

More specifically:
- the repo has repeatedly struggled with one-step / local target semantics on hard close-branch states,
- several downstream and upstream fixes around the same local target family were negative,
- the first recent direction to show a meaningful positive signal is the **multi-step target horizon** line,
- but the current evidence should still be treated as **promising, not yet trustworthy**.

## What recent negative results now mean

Recent bounded artifact-backed passes did **not** clear the continuation bar for:
- conditional near-tie information expansion,
- probabilistic branch-value allocation,
- opportunity-intensity-weighted upstream supervision,
- statewise supervision-object reformulation,
- and allocation-regret target reformulation.

The common interpretation is:

> the repo was likely near the limit of what it could extract from the current one-step / local target family.

That does **not** mean representation no longer matters. It means that changing chooser logic, weighting, or supervision format around the same local signal was not enough.

## Current best interpretation of the bottleneck

The best current interpretation is now:

> **hard close-branch cases may require a longer-horizon utility signal, not only a one-step utility signal.**

This is the strongest currently supported explanation for why many recent bounded fixes were negative while the multi-step horizon line looks more promising.

## What to trust right now

Trust as current working interpretation:
- multi-step target direction is the best current lead,
- the signal is positive enough to keep validating,
- but support is still too small for a strong paper-level claim.

Do **not** trust yet:
- a solved-claim about close-branch discrimination,
- a claim that the multi-step path is already robust across conditions,
- or a claim that the rest of the repo should be reorganized around this as final truth.

## Recommended next near-term work

1. Continue validating the multi-step direction under matched settings.
2. Extract concrete failure cases for the current leading method.
3. Inspect where one-step and multi-step targets disagree.
4. Use those failure cases to decide whether the next step should be:
   - better multi-step target construction,
   - trajectory-shape signals,
   - or distributional rather than single-value supervision.

## Recommended reading path after this note

After reading this note, use:
1. `CURRENT_METHOD_SUMMARY_AND_GAPS.md`
2. `WHAT_IS_NOT_WORKING_NOW.md`
3. `CURRENT_BOTTLENECKS.md`
4. `../scripts/CANONICAL_START_HERE.md`

## Conservative conclusion

The repository is no longer best summarized as “many ideas failed.”

The better summary is:

> many ideas that reused the same local signal failed, and the first currently plausible break in that pattern is the multi-step target direction.
