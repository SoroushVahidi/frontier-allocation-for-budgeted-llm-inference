# External-only Loss Pattern Mining (cumulative 31)

## Category table

- `L1_P1_code_absent`: **14**
- `L1_P9_external_trace_advantage_unknown`: **10**
- `L1_P5_correct_candidate_not_selected`: **4**
- `L1_P2_unsafe_code`: **1**
- `L1_P3_exec_failed`: **1**
- `L1_P4_exec_succeeded_wrong`: **1**

## Top precise patterns

- code omitted final executable snippet/answer payload: **9**
- gold absent from PAL candidate pool while external found correct target path: **7**
- no PAL code block emitted despite PAL seed running: **5**
- gold-equivalent answer absent from PAL candidate pool while external path reached correct answer: **3**
- gold-equivalent candidate exists but selector/tiebreak picked another answer: **2**

Conclusion: **code-absence is the dominant actionable bottleneck** in external-only losses.
