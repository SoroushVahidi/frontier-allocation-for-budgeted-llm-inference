# Structured Ambiguity Features Status

## Why this pass exists

Generic confidence is too coarse for the repo's hardest allocation decisions.
Hard slices are structured ambiguous states where frontier geometry, budget context, outside-option competitiveness, and instability signals interact.

## What v3 adds over v2

Feature set `v3` keeps all `v2` features and adds bounded ambiguity-focused families:
- frontier-relative ambiguity features (top-k gaps, local density/crowding, viable-count, compact gap summaries, rank-instability proxy)
- dynamic/instability proxies (time-since-improvement proxy, widening-vs-shrinking proxy)
- budget-conditioned and outside-aware proxies (expected-gain-per-cost proxy, outside-gap x budget, stop/defer proxy)
- pairwise relational ambiguity features (`pair_relational_v3`) merged with `x_diff` into `x_pair_v3` for defer modeling

## 3-way defer target

Added first-class target:
- `0`: allocate_to_branch_j
- `1`: defer_or_outside_option
- `2`: allocate_to_branch_i

This is derived from ambiguity signals (absolute/relative margin, uncertainty, existing ambiguity flags) and optional outside-option competitiveness thresholds.

## True signals vs bounded proxies

Implemented from existing artifacts/signals:
- margins, relative margins, rank adjacency, uncertainty summaries, branch-vs-outside gaps, budget-conditioned interactions

Bounded approximations (explicit proxies, not solved latent variables):
- `pair_shadow_price_adjusted_margin_proxy`
- `expected_gain_per_cost_proxy`
- `stop_or_defer_proxy_score`
- instability proxies derived from local frontier gaps and branch local dynamics

## Why this is experimental

This is a bounded structured-ambiguity extension, not a final solved method.
It is intended to test whether ambiguity-aware representation + defer-aware supervision improves accepted-case quality on hard slices.

## Safe interpretation

- Positive results suggest ambiguity is better modeled as frontier/budget/outside-aware state structure.
- Mixed or negative results still inform the current bottleneck diagnosis (supervision/confidence design remains central).
- Do not treat this as evidence that model-class swaps alone solve the canonical allocation bottleneck.
