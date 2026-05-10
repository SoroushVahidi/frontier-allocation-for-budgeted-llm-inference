# Offline PAL vs external paired failure mine

## Inputs
- casebook: `/home/soroush/research-next-wt/outputs/cohere_paired_pal_retry_vs_external_l1_300case_BASELINE_REMAT_20260506/paired_casebook.csv`
- pal_results: `/home/soroush/research-next-wt/outputs/cohere_paired_pal_retry_vs_external_l1_300case_BASELINE_REMAT_20260506/pal_results.jsonl`

## Bucket counts
- **both_correct**: 223
- **both_wrong**: 27
- **external_only**: 21
- **pal_only**: 29

## Retry recompute (raw `pal_execution`, not casebook `retry_enabled`)
- Rows: **300**
- Truth retry enabled (sum): **300**
- Truth retry ran (sum): **16**
- Selected source `pal_empty_code_retry` rows: **12**
- Inferable retry helped (exact & retry selected): **8**
- Inferable retry hurt (not exact & retry selected): **4**
- Casebook `retry_enabled`=0 but raw enabled: **300** rows
- Missing `pal_results` join rows: **0**

## Top composite signatures
### external_only
- `discovery3_cb|overlay_cb|present_not_selected_cb` — **8**
- `gold_absent_cb|overlay_cb` — **7**
- `code_absent_cb|exec_fail_cb|gold_absent_cb|parse_fail_cb|retry_ran_raw|safety_fail_cb` — **2**
- `exec_fail_cb|gold_absent_cb|retry_ran_raw` — **1**
- `gold_absent_cb` — **1**
- `discovery3_cb|overlay_cb` — **1**
- `gold_absent_cb|retry_ran_raw|retry_selected_raw` — **1**

### both_wrong
- `gold_absent_cb|overlay_cb` — **19**
- `discovery3_cb|overlay_cb|present_not_selected_cb` — **2**
- `gold_absent_cb|overlay_cb|retry_ran_raw|retry_selected_raw` — **2**
- `exec_fail_cb|gold_absent_cb|retry_ran_raw|safety_fail_cb` — **1**
- `discovery3_cb|present_not_selected_cb` — **1**
- `discovery3_cb|overlay_cb` — **1**
- `discovery3_cb|overlay_cb|retry_ran_raw|retry_selected_raw` — **1**

## Fix-target hints (interpretive)
- **`gold_absent_cb` heavy in `external_only`:** widen/improve candidate discovery / frontier surfacing so gold enters the selector pool.
- **`present_not_selected_cb`:** selector / tie-break / verification policies failing despite executable candidates.
- **`exec_fail_cb` / `parse_fail_cb` / `safety_fail_cb`:** executor / sandbox / parsing brittleness.
- **Retry rare (`truth_retry_ran` mostly 0):** empty-code retry policy will not address gold-absent / discovery gaps.

