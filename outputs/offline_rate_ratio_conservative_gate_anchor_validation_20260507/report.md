# Conservative Rate/Ratio Gate Anchor Validation

## Validation Setup
- Offline/simulator-only anchor replay (no API calls).
- Anchor source: `outputs/offline_pal_discovery_deficit_atlas_20260506/anchor_cases.csv`.
- Filter: `operation_hint=rate_ratio` and `quantity_bucket in {qnum_4_5, qnum_6p}`.
- Compared methods:
  - incumbent: `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`
  - candidate (reverted): `direct_reserve_diverse_root_frontier_v1_guarded_rate_ratio_conservative_gate_v1`

- Anchor cases: 12
- Trigger count/rate: 12 / 1.0000
- Frozen count: 0
- Added candidates: 10
- Duplicate skips: 2
- Override allowed count: 0
- Exact (incumbent -> conservative): 4/12 -> 3/12
- Improved cases: 2
- Worsened cases: 3
- Regressions on previously-correct incumbent: 3
- Keep criteria passed: False

## Keep Criteria
- trigger_rate<=0.40: False
- worsened_cases==0: False
- improved_cases>=1: True
- non_duplicate_adds>0: True
- regressions_on_prev_correct==0: False

## Conclusion
- Conservative rate/ratio gate should remain reverted.
- Keep criteria failed (trigger too broad and exact regressed).

## Key Lesson
- Even with `override_allowed=0`, candidate/pool injection can still perturb downstream selector behavior and harm pass@1.

## Next Direction
- Abandon rate/ratio candidate injection for now.
- Focus on diagnosing:
  - why triggering remains too broad on anchors,
  - why selector outcome shifts after pool additions despite no direct override.

## API Calls
- None.

## Regressions
- openai_gsm8k_1025: 23 -> 21
- openai_gsm8k_780: 1 -> -2
- openai_gsm8k_979: 3 -> 4

## Improvements
- openai_gsm8k_819: 65 -> 68
- openai_gsm8k_929:  -> 18
