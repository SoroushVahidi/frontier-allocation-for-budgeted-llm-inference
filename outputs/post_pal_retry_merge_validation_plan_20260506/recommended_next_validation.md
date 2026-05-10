# Post-merge PAL retry validation plan (no API)

## Current best method
- `direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal`

## PAL retry patch status
- Merged (PR #360).

## Evidence
- External-only 31-case audit: `L1_P1_code_absent = 14`.
- Retry-eligible: `16/31`.
- Live targeted retry evaluation: `6/16` fixed, `0` breaks.

## Claim boundary
- Targeted evidence only.
- No global superiority claim over `external_l1_max` yet.

## Recommended next API experiment (after explicit approval)
- Fresh paired PAL+retry vs `external_l1_max` validation.
- Suggested run: 100 fresh paired cases.
- Suggested logical call cap: 1000 or 1500.

## Risks
- Cap saturation.
- Repeated cases.
- Metric consistency.
- Retry prompt brittleness.

## API policy
- API remains paused until explicit approval.
