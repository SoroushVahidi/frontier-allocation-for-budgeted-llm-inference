# PAL-only final-target mismatch deep audit

Input: `outputs/pal_vs_production_multibatch_relaxed_live_20260509T010509Z/cumulative_with_previous_casebook.csv`

## PAL-only final-target cases

Count: 9

All PAL-only cases in the cumulative bank are labeled `final_target_mismatch`.

## Candidate no-gold selector rule

Rule:
PAL executed cleanly + PAL and production disagree + production surface is structural commit + relative numeric gap > 0.25.

Coverage on PAL-only: 8/9
Risk on contrast: 0/120

## Decision

whether_selector_designable_now: True

recommended_next_step: design_no_api_pal_hybrid_selector_v1

## Caveats

This audit uses heuristic features and existing metadata only. It does not call APIs and does not integrate a new method.
