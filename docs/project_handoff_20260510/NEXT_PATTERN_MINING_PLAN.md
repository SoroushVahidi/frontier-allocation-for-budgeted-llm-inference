# Next Pattern Mining Plan — 2026-05-10

## Primary Objective
Inspect the **42 FULL evidence failure cases** to identify the root cause of commitment-layer overrides.

## Key Pattern to Mine
**Commitment / Target-Alignment Failure**
We need to distinguish between:
1. **Structural Commit Wrong**: The system correctly identifies a structural pattern but the pattern itself is flawed or misapplied to the specific problem.
2. **Final Target Mismatch**: The system has the correct answer in its candidate pool but selects a different one during the final reasoning/extraction pass.

## Methodology
1. **Manual Inspection**: Review the `problem_text`, `gold_answer`, and `selected_answer` for the 42 FULL cases.
2. **Trace Analysis**: For cases with `trace_or_candidate_metadata_available`, look at the intermediate reasoning steps to see where the divergence occurs.
3. **Hypothesis Generation**: Formulate a rule or patch to prevent the most common override types.

## Success Metric
A proposed patch that reduces the `final_target_mismatch` rate in a counterfactual replay on these 42 cases without regressing on correct ones.
