# Hard-pair supervision cleanup next step

## Purpose

This note records the current best next supervision-oriented method step after the recent hard-case relabeling, learned-deferral, and Cohere adjudication passes.

It is intended to prevent the repository from drifting back into generic model/controller changes when the more immediate issue is still hard-pair supervision quality.

## Current problem

The strongest current evidence suggests that the hardest near-tie and adjacent-rank pair labels are still not reliable enough to be treated as ordinary binary supervision.

This is consistent with:
- exact-vs-approx disagreement concentration on hard slices,
- mixed or negative results from direct hard-region relabeling,
- mixed learned-deferral results,
- and a negative bounded Cohere adjudication pass under a loose replacement policy.

## What the recent Cohere pass teaches

The recent bounded Cohere hard-pair adjudication pass did **not** improve the current bottleneck under the tested replacement policy.

Conservative interpretation:
- the problem is probably not solved by broad label overrides on hard pairs,
- and stronger relabel sources do not automatically help unless the acceptance policy is very conservative.

This does **not** prove that all external adjudication is useless.
It does suggest that naive or moderately loose replacement logic is not a good current default.

## Best current literature-grounded direction

The strongest next direction is a **hard-pair supervision cleanup pipeline** based on:
- suspicious-pair scoring,
- selective cleanup,
- reliability-aware weighting,
- and possibly later exact-budget prioritization.

The current best paper-inspired ingredients are:
- Confident Learning style error ranking,
- Active Label Cleaning style budget prioritization,
- and later, if feasible, Crowd-BT style multi-judge reliability aggregation.

## Recommended next implementation interpretation

The next step should be interpreted as:

> **make the hard suspicious pairs less trusted before trying to make the controller more complex.**

This means the first move is likely one of:
- downweighting top suspicious hard pairs,
- excluding only the worst suspicious hard pairs,
- or turning the most suspicious hard pairs into softer/reliability-weighted supervision.

It does **not** mean:
- broad new controller-family expansion,
- broad new dataset expansion before cleanup,
- or broad external adjudication replacement.

## Current preferred sequence

### Step 1
Build a suspicious-pair ranking over the current pairwise corpus.

### Step 2
Create one conservative cleaned target regime using that ranking.

### Step 3
Run one matched learner comparison against the current baseline regime.

### Step 4
Only if that helps, consider budgeted exact review or multi-judge aggregation on the top suspicious pairs.

## Practical rule

For the next bounded data pass:
- preserve easy/high-confidence coverage,
- focus cleanup on near-tie / adjacent-rank / low-margin / high-uncertainty slices,
- and prefer weighting/filtering over hard label replacement unless the replacement evidence is unusually strong.

## Neighbor docs

- `CURRENT_METHOD_SUMMARY_AND_GAPS.md`
- `WHAT_IS_NOT_WORKING_NOW.md`
- `TARGET_FIDELITY_BRANCH_COMPARISON_STATUS.md`
- `HARD_REGION_EXACT_SUPERVISION_STATUS.md`
- `DATASET_EXPANSION_PRIORITIES_2026_04_17.md`
