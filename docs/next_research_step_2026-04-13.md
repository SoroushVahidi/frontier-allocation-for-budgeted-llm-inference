# Next research step (2026-04-13)

This note captures the most useful immediate research direction after the current learned-scorer experiments.

## Main conclusion so far

The project has learned that:
- simple heuristics are strong,
- better local targets help,
- but compact tabular features and lightweight linear/logistic models still do not robustly beat the best internal heuristics.

## Most likely next step

The next promising direction is a stronger **path/state representation**, not only another weak proxy target on the same feature backbone.

A particularly plausible direction is:
- path-history-aware representation,
- budget-aware continuation scoring,
- and explicit use of the ordered recent branch history.

## Candidate representation idea

A practical next representation may use:
- remaining budget,
- ordered last few node summaries,
- ordered last few edge/action types,
- and a learned path-aware scorer built on top of that representation.

## Why this is the next step

Recent experiments suggest that improving target construction alone is not enough if the branch-state representation remains too weak.

## Status

This note is only a near-term planning memo. It should be revised when a stronger representation family is actually implemented and evaluated.