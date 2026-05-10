# External-only loss pattern audit (cumulative 31)

- Output path: `outputs/external_only_loss_pattern_audit_31_20260506`
- Unique external-only losses: **31** (expected 31: yes)
- Source counts: {'cumulative_20_casebook_rows': 20, 'round3_external_only_rows': 11, '100pair_external_only_from_paired': 5, 'round1_external_only_casebook': 10, 'round2_external_only_casebook': 5}

## Category table
- L1_P1_code_absent: **14**
- L1_P9_external_trace_advantage_unknown: **10**
- L1_P5_correct_candidate_not_selected: **4**
- L1_P2_unsafe_code: **1**
- L1_P3_exec_failed: **1**
- L1_P4_exec_succeeded_wrong: **1**

## Top precise patterns
- code omitted final executable snippet/answer payload: **9**
- gold absent from PAL candidate pool while external found correct target path: **7**
- no PAL code block emitted despite PAL seed running: **5**
- Gold-equivalent answer absent from PAL candidate pool while external path reached correct answer.: **3**
- gold-equivalent candidate exists but selector/tiebreak picked another answer: **2**

## Fixability table
- retry-on-empty-code: **11**
- collecting more evidence: **7**
- PAL selection/integration patch: **4**
- adding retry-on-empty-code: **3**
- collect more evidence: **3**
- executor allowlist/sandbox patch: **2**
- PAL prompt tightening: **1**

- Prompt/executor/selection/retry-fixable: **21/31**
- Enough to choose a patch: **yes**
- More API collection needed before patching: **no**
- Recommended next step: **B. add retry-on-empty-code**
- API should remain paused: **yes**
