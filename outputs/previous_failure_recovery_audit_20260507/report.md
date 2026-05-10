# Previous Failure Recovery Audit (Local Artifacts Only)

## Corpus Definition
- external_only: external exact, PAL wrong (from 300-case paired casebook)
- both_wrong: both external and PAL wrong (from 300-case paired casebook)
- gold_absent_everywhere_detectable: from offline path-coverage counterfactual
- rate_ratio_anchors: union of broad/conservative/selector-isolated anchor example IDs
- previously_correct_regressed_validation_anchors: incumbent exact -> variant wrong

## Current Output Used
- Preferred: `offline_selector_isolated_exploration_log_anchor_validation_20260507/per_case.csv`
- Fallback: `cohere_paired_pal_retry_vs_external_l1_300case_20260506T194114Z/paired_casebook.csv`
- Important: no fresh rerun after latest code state; this is latest-available-artifact based.

## Results
- total unique previous failure/loss cases: 48
- corrected now: 7
- still failing: 41
- missing/no-current-output: 0

## Breakdown by bucket
- both_wrong: corrected=6, still_failing=21, missing=0
- external_only: corrected=1, still_failing=20, missing=0
- gold_absent_everywhere_detectable: corrected=7, still_failing=27, missing=0
- previously_correct_regressed_validation_anchors: corrected=1, still_failing=4, missing=0
- rate_ratio_anchors: corrected=7, still_failing=5, missing=0
