# External L1-only Fix Failure Patch Plan

## What worked (5/7)
- Successful cases: openai_gsm8k_674, openai_gsm8k_746, openai_gsm8k_752, openai_gsm8k_758, openai_gsm8k_765.
- Effective scaffolds were `final_target_verifier_retry`, `state_composition_v2`, `l1_style_concise_decomposition`, and one `ratio_partition_v2` case.
- These worked by better target alignment, state-ordering discipline, and concise decomposition for average/target problems.

## What failed (2/7)
- `openai_gsm8k_683` (`percent_base_denominator_v2`): base-denominator drift; model switched to updated base though statement says percent of total capacity.
- `openai_gsm8k_769` (`ratio_partition_v2`): arithmetic part-count slip (used 6 parts instead of 8).

## Patch recommendation before Stage 2
- Patch percent-base prompt now (low risk, high specificity).
- Do not patch ratio template broadly in this step; treat as arithmetic slip and optionally add sanity guard later.

## Micro-pilot recommendation
- Run one micro-pilot on the two failed IDs after percent-base patch (and optional ratio sanity line) before full Stage-2 rerun.

## Stage-2 integration recommendation
- Integrate successful 5 now as guarded path.
- Include patched percent-base candidate after micro-pilot confirmation.

## Caveats
- Evidence is from a focused 7-case slice, not a full-distribution evaluation.
- One remaining ratio miss may reflect stochastic arithmetic rather than routing/template coverage.
