# Fairness report: TALE baseline integration

## Problem-space mismatch statement
- TALE performs per-instance token budget allocation; our primary method is a sequential frontier stop-vs-act allocator.
- We therefore report matched-compute comparisons and avoid claiming strict control-equivalence.

## Primary comparison protocol
- Compare `adaptive_min_expand_1` vs `external_tale_prompt_budgeting` at fixed budget grid and matched-average-compute rows.

## MODE B import guardrails
- MODE B is a strict official/full import path requiring schema + provenance + variant identity validation.
- Imports are rejected if metadata is incomplete/inconsistent or if TALE and TALE-PT variants are mixed/blurred.

## Caveats
- Prompt-level TALE adapter here does not include TALE-PT post-training.
- MODE B does not claim local full TALE/TALE-PT reproduction.
