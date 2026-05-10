# External-only loss collection report

- Run dir: `outputs/external_only_loss_collection_pal_vs_l1_completed_20260506T125123Z`
- Methods: external_l1_max vs direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal
- Paired completed: **140**
- External exact: **109**; PAL exact: **120**
- external_correct_pal_wrong: **10**; pal_correct_external_wrong: **21**; both_correct: **99**; both_wrong: **10**
- Calls used (row-sum / cap-consumed-est / cap): **1123 / 1500 / 1500**
- Failed/skipped: **100**
- Stop reason: **B_hit_cap**
- Yield: **0.0714** external-only losses per paired case
- Cumulative external-only losses incl previous 100-pair run: **15**

## Top precise external-only patterns
- L1_P4_exec_succeeded_wrong: **8**
- L1_P1_code_absent: **1**
- L1_P5_correct_candidate_not_selected: **1**

## Recommendation
- This batch is useful for initial targeted audit, but still below the 20-case target for robust pattern mining.
- Next step: **A. no-API pattern audit** on collected external-only losses; run larger collection only after approval.
