# Reverted Rate/Ratio Gate Offline Validation (Anchor Slice)

## Setup
- Scope: offline simulator-only replay on atlas anchor cases from `outputs/offline_pal_discovery_deficit_atlas_20260506/anchor_cases.csv`.
- Filter: `operation_hint=rate_ratio` and `quantity_bucket in {qnum_4_5, qnum_6p}`.
- Compared methods:
  - Incumbent: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`
  - Candidate (reverted): `direct_reserve_diverse_root_frontier_v1_guarded_rate_ratio_gate_v1`
- API calls: none.

## Results
- Anchor cases: 12
- Gate trigger: 12/12
- Added candidates: 11
- Duplicate skip: 1
- Gold-present pool: incumbent 9/12 -> new 10/12
- Exact: incumbent 4/12 -> new 3/12
- Improved exact: 2
- Worsened exact: 3

## Worsened Cases
- `openai_gsm8k_1025`: `23 -> 21`
- `openai_gsm8k_780`: `1 -> -2`
- `openai_gsm8k_979`: `3 -> 4`

## Improved Cases
- `openai_gsm8k_819`: `65 -> 68`
- `openai_gsm8k_929`: ` -> 18`

## Conclusion
- Broad rate/ratio gate should remain reverted.
- Despite modest pool coverage gain, exact accuracy regressed on this anchor slice.

## Next Direction
- Only pursue a selection-safe / conservative gate:
  - stricter trigger,
  - no override when incumbent support is strong,
  - protect known-correct/stable incumbent behavior.
