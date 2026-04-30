# Selector Surface Smoke Results (2026-04-29)

## Compared runs
- **V1:** `20260429T_SELECTOR_SURFACE_SMOKE_COHERE`
- **V2:** `20260429T_SELECTOR_SURFACE_SMOKE_COHERE_V2` (after DR-v2 selector-candidate-pool exposure fix)

## V1 summary (inert selector surface)
- candidate_count distribution: `{1: 6}`
- answer_group_count distribution: `{1: 6}`
- extraction sources: `final_answer_fallback` only
- fallback reasons: `single_candidate_only` only
- rerank applied: OV `false` all rows, PRM `false` all rows
- verifier calls: `{0: 6}`
- backend values: `cohere` but no verifier activity
- gold present in candidates: OV=0, PRM=3
- recovered present-not-selected: OV=0, PRM=0

## V2 summary (post-fix)
- candidate_count distribution: `{2: 6}`
- answer_group_count distribution: `{2: 4, 1: 2}`
- extraction sources: `selector_candidate_pool` (all rows)
- fallback reasons: empty (no fallback reason)
- rerank applied:
  - OV: `true` on 3/3 OV rows
  - PRM: `true` on 3/3 PRM rows
- verifier calls distribution: `{2: 4, 4: 2}`
- backend values: `cohere` (all rows)
- gold present in candidates: OV=3, PRM=3
- recovered present-not-selected: OV=0, PRM=1

## Interpretation
- V1 proved selectors were inert due to missing candidate-pool exposure.
- V2 shows selectors now receive multi-candidate pools directly from DR-v2 metadata and actively rerank with real verifier calls.
- Some rows still have `answer_group_count=1` despite multiple candidates; this is expected when candidates collapse to the same normalized answer and is now explicitly diagnosable.

## Decision
A full 100-case selector run is now **meaningful** from a selector-surface perspective because V2 meets the required gating criteria:
- candidate_count > 1,
- extraction source includes `selector_candidate_pool`,
- rerank applied in OV and PRM rows,
- verifier_calls > 0.

No accuracy claim is made from this smoke (surface validation only).


Update: V2 smoke unlocked bounded 30-case selector diagnostic; see `docs/SELECTOR_COMPARISON_30CASE_COHERE_20260429.md`.
