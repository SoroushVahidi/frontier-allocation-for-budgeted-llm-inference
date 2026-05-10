# External-only loss pattern audit (cumulative 20)

- Output path: `/home/soroush/research-next-wt/outputs/external_only_loss_pattern_audit_20_20260506`
- Unique external-only losses: **20** (expected 20: yes)
- Source counts: {'previous_100pair_external_only_losses': 5, 'round1_collection_external_only_loss_casebook': 10, 'round2_collection_external_only_loss_casebook': 5}

## Category table
- L1_P9_external_trace_advantage_unknown: **10**
- L1_P5_correct_candidate_not_selected: **4**
- L1_P1_code_absent: **3**
- L1_P2_unsafe_code: **1**
- L1_P3_exec_failed: **1**
- L1_P4_exec_succeeded_wrong: **1**

## Top precise patterns
- gold absent from PAL candidate pool while external found correct target path: **7**
- code omitted final executable snippet/answer payload: **3**
- Gold-equivalent answer absent from PAL candidate pool while external path reached correct answer.: **3**

- Prompt/executor/selection/retry-fixable: **7/20**
- Enough to choose a patch: **no**
- More API collection needed before patching: **yes**
- Recommended next step: **C. collect more external-only losses**
- API should remain paused: **yes**
