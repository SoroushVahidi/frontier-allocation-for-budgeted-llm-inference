# Failure Pattern Mining Report — 2026-05-10

## Executive Summary
Analysis of initial failure cases from the 42 FULL evidence failure bank reveals a recurring pattern of **commitment regressions**. In several cases, both PAL and the Frontier correctly identified the gold answer, but the `track_b_gate` (structural commitment layer) overrode these correct answers in favor of an incorrect `direct_reserve` incumbent or an incorrect `frontier` candidate, often due to tie-breaking rules that over-privilege the initial direct response or ignore PAL execution strength.

**CRITICAL UPDATE**: A code sync from the `research-next-wt` archive revealed that the canonical repository was missing the latest implementation of `decide_track_b_overlay_commitment_gate` and `decide_structural_commitment_v1`. These have now been restored, allowing for a precise diagnosis of the faulty rules.

## Detailed Case Analysis

### Case 1: `openai_gsm8k_30`
- **Question**: Darrell and Allen's ages are in the ratio of 7:11. If their total age now is 162, calculate Allen's age 10 years from now.
- **Gold Answer**: 109
- **Results**:
    - **PAL**: 109 (Correct)
    - **Frontier**: 121 (Wrong)
    - **Direct Reserve**: null (Parse failure)
    - **Final Selection**: 121 (Wrong)
- **Diagnosis**: The `track_b_gate` chose to override the correct PAL answer with the incorrect frontier answer. The reason cited was `override_overlay_prior_matches_tiebreak_conflicts_with_pal_stdout`. This suggests the tiebreak logic is not properly weighing PAL execution strength against weak frontier evidence.

### Case 2: `openai_gsm8k_59`
- **Question**: A raspberry bush has 6 clusters of 20 fruit each and 67 individual fruit scattered across the bush. How many raspberries are there total?
- **Gold Answer**: 187
- **Results**:
    - **PAL**: 187 (Correct)
    - **Frontier**: 187 (Correct)
    - **Direct Reserve**: 287 (Wrong)
    - **Final Selection**: 287 (Wrong)
- **Diagnosis**: A clear **structural commitment regression**. Both PAL and Frontier found the correct answer (187). However, because `direct_reserve` also had 1 support (itself), the system saw a tie in support counts (`187: 1, 287: 1`). The `decide_structural_commitment_v1` Rule B (`structural_v1_frontier_realign_dr_equal_support`) then "realigned" the answer back to the incorrect `direct_reserve` incumbent.

### Case 3: `openai_gsm8k_1177`
- **Question**: Mr. Maxim restaurant guests calculation.
- **Gold Answer**: 320
- **Results**:
    - **PAL**: 320 (Correct)
    - **Frontier**: 150 (Wrong)
    - **Direct Reserve**: 320 (Correct)
    - **Final Selection**: 150 (Wrong)
- **Diagnosis**: Extremely aggressive override. Both PAL and Direct Reserve agreed on 320, but the `track_b_gate` overrode them with the incorrect Frontier answer (150) because the Frontier tie-break selected 150 and it had equal support (1) to the PAL answer.

## Identified Faulty Rules in `experiments/output_layer_repair.py`

1.  **`decide_track_b_overlay_commitment_gate` (Lines 319-326)**:
    ```python
    return _out(
        should_override=True,
        recommended_answer=str(op_prev).strip(),
        recommended_normalized_group=tb_n,
        recommended_source="overlay_prior_matches_tiebreak",
        reason="override_overlay_prior_matches_tiebreak_conflicts_with_pal_stdout",
        abstain=None,
    )
    ```
    *   **Fault**: Overrides PAL stdout even when PAL has equal histogram support to the overlay, and even when PAL is "strong".

2.  **`decide_structural_commitment_v1` Rule B (Lines 481-496)**:
    ```python
    if sup_dr >= 1 and sup_tb == sup_dr:
        out.update({
            "should_override": True,
            "recommended_answer": str(dr_raw).strip(),
            "recommended_source": "structural_v1_frontier_realign_dr_equal_support",
            ...
        })
    ```
    *   **Fault**: Realigns to Direct Reserve on a tie (`sup_tb == sup_dr`), even if PAL already matches the tie-break group (`sup_tb`). This effectively privileges the DR incumbent over a PAL/Frontier consensus.

## Identified Patterns
1. **Over-privileging the Incumbent**: The commitment layer frequently reverts to the `direct_reserve` answer in tie-break situations, even when PAL and Frontier provide a consistent alternative.
2. **PAL Execution Strength Ignored**: PAL execution success (`pal_exec_ok: true`) and candidate strength (`pal_candidate_is_strong: 1`) are not sufficiently weighted when they conflict with the `direct_reserve` incumbent or Frontier tie-break.
3. **Aggressive Override on Ties**: The system overrides PAL results on 1-vs-1 ties without requiring a margin of evidence.

## Next Steps
1.  **Apply Patch**: Modify `experiments/output_layer_repair.py` to:
    *   Require `sup_tb > sup_pal_stdout` (not just `>=`) in `decide_track_b_overlay_commitment_gate`.
    *   Require `sup_dr > sup_tb` (not just `==`) in `decide_structural_commitment_v1` Rule B.
    *   Add a "strong PAL" guard that prevents overrides if PAL is strong and has non-zero support.
2.  **Verify**: Run `pytest` and create a reproduction script for `openai_gsm8k_59` and `openai_gsm8k_1177`.
