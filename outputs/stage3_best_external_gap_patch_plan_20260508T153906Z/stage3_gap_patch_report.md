# Stage-3 Best-External Gap Patch Plan

## Recap
- Micro-pilot: 3 cases, 6 calls, 4/6 exact variants, 2/3 fixed cases.

## Flag audit
- closes_best_external_gap issue rows: 4/6.
- Original flag is stricter than needed for case-level gap closure and undercounts successful closures.

## Variant effectiveness
- openai_gsm8k_1078: success=[final_target_extraction_repair;tale_style_decomposition], recommendation=use_either_best_of_two.
- openai_gsm8k_1155: success=[none], recommendation=leave_unfixed.
- openai_gsm8k_1198: success=[final_target_extraction_repair;tale_style_decomposition], recommendation=use_either_best_of_two.

## Recommended policy
- Run a 3-case patch checkpoint first using the recommended per-case variant policy.
- If checkpoint confirms repeatability, integrate patch into Stage-3 50-case rerun before any 245-case expansion.
- Keep production-runtime equivalence as the next priority after patch checkpoint confirmation.

## Caveats
- Very small sample and prompt-level intervention only.
- No runtime-controller changes included in this patch plan.