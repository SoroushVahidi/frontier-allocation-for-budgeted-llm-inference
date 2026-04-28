# Direct Reserve v2 Thresholded+Ordered Implementation Note

## What was implemented

- Added a new **diagnostic-only** registry method:
  - `direct_reserve_semantic_frontier_v2_thresholded_ordered`
- Implemented via `DirectReserveGateRerankControllerV2ThresholdedOrdered` in `experiments/controllers.py`.
- Wired into `build_semantic_diversity_diagnostic_strategies(...)` only.
- Canonical methods (`strict_f3`, `strict_f2`, `strict_gate1_cap_k6`, `external_l1_max`) were not modified.

## How it differs from v1

Compared with `direct_reserve_semantic_frontier_v1`, this version is cost-oriented:

- Direct incumbent is produced first and protected by default.
- Adds route selection:
  - `stop_with_incumbent`
  - `one_more_direct_continuation`
  - `limited_frontier_challenge`
- Uses lower frontier challenger caps (small=1, large=2; only allows up to 3 in high-uncertainty weak-incumbent cases).
- Uses thresholded continuation and thresholded replacement logic.
- Logs ordering-policy metadata and route decisions for post-hoc diagnostics.

## Thresholds and ordering rules used

- `continuation_threshold = 0.42`
- `commit_threshold = 0.62`
- `replacement_threshold = 0.55`

Continuation proxy:

- `continuation_value = quality + novelty + challenge_value - redundancy - cost (+ uncertainty bonus)`
- all terms use label-free proxies from incumbent/frontier metadata.

Ordering policy (logged as policy labels):

1. Stage 0: direct incumbent first.
2. Layer 1: semantic novelty/setup diversity.
3. Layers 2–3: uncertainty-adjusted continuation value.
4. After layer 3: answer support, challenger value, available proxy score.

## Metadata logged

The new method logs the requested route and source fields, including:

- `route_decision`, `route_reason`
- `incumbent_parseable`, `incumbent_confidence_proxy`
- `frontier_opened`, `direct_actions_used`, `frontier_actions_used`
- `semantic_family_count`, `family_redundancy_ratio`, `families_matured_count`
- `continuation_threshold`, `commit_threshold`, `replacement_threshold`
- `top_challenger_answer`
- `final_source`
- `incumbent_replacement_reason`
- `actions_used`

## Local smoke checks passed

- Python compile check over `experiments` and `scripts`.
- Registry inspection confirms method presence.
- Offline synthetic tests confirm:
  - route/final-source metadata present,
  - robustness to empty/`None` direct answers,
  - planned challenger cap is lower than v1 settings,
  - canonical config fields remained unchanged.

## What remains for later Wulver evaluation

- Run on real Cohere diagnostics (separate Wulver stage) to verify:
  - action reduction vs v1,
  - retention of v1 accuracy gains,
  - paired deltas vs `strict_f3` and `external_l1_max`,
  - replacement/route behavior on real uncertainty slices.
