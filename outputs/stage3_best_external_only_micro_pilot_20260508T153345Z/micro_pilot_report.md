# Stage-3 Best-External-Only Micro Pilot

- Tested 3 best_external-only cases with 2 variants each (cap 6). Actual calls: 6.
- Exact variant hits: 4; cases fixed: 2/3.

## Variant outcomes
- final_target_extraction_repair: calls=3, exact=2, improved=2, closes_gap=0
- tale_style_decomposition: calls=3, exact=2, improved=2, closes_gap=0

## Decision
- Gap fixability signal: promising.
- Patch Stage-3 before 245 if improvements are repeatable.
- Production frontier-runtime equivalence remains next priority after patch verification.

## Caveats
- Prompt-level only; no runtime logic changes.
- Very small sample (3 cases).