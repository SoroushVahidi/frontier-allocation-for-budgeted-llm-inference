# External-only loss pattern audit (cumulative 15)

- Output path: `outputs/external_only_loss_pattern_audit_15_20260506`
- Unique external-only losses: **15**

## Category table
- L1_P9_external_trace_advantage_unknown: **7**
- L1_P1_code_absent: **3**
- L1_P5_correct_candidate_not_selected: **2**
- L1_P3_exec_failed: **1**
- L1_P4_exec_succeeded_wrong: **1**
- L1_P2_unsafe_code: **1**

## Top precise patterns
- gold absent from PAL candidate pool while external found correct target path: **7**
- code omitted final executable snippet/answer payload: **3**
- gold-equivalent candidate exists but selector/tiebreak picked another answer: **2**

## Fixability view
- Prompt-fixable: **1**
- Executor/sandbox-fixable: **2**
- Selection-fixable: **2**
- Retry-on-empty-code candidates: **3**

- Recommended next step: **C_collect_more_external_only_losses**
- API should remain paused: **Yes**
