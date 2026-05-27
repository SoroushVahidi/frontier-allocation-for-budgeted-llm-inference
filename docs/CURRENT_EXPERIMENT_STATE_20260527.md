# Current Experiment State (2026-05-27)

## Canonical Main Result (FTA)
- Method: Failure-Trace Allocator (FIX-2 + FIX-4)
- Final-300: 86.67% (260/300), seed=71, Cohere × GSM8K, budget=6
- Aggregate-720: 80.69% (581/720), seeds 41+61+71
- Leakage audit: PASS; post-generation model calls: 0
- Verification artifacts: `outputs/fta_independent_verification_20260527/run_20260527T003000Z/`

## Supporting Multi-Provider Evidence (D9)
- D9 CV: 50.18% ± 2.52% vs frontier 34.36% (+15.82pp)
- 550 D6 pools, 3 providers, 0 false overrides
- D6 standalone remains negative overall; D9 gate is required

## D6 Status
- D6 is diagnostic/frontier-expansion context, not standalone headline evidence.
- Use D6 as motivation/context and as input to D9-style gated usage.

## Critical Path (Current)
1. Monitor/complete Mistral D6 resume artifacts and checks
2. Evaluate Mistral outputs in the same evidence contract
3. Retrain/refresh D9 with Cohere + Mistral data
4. Fix Cloudrift extraction/prompt contract before new generation
5. Maintain FTA verification/audit trail for paper finalization

## What Not To Trust Without Verification
- Claims based only on plans or expected outcomes
- Claims without raw row counts, logs, and run artifacts
- Claims that ignore the pooled-ensemble CI-zero disclosure

## Scope and Claim Boundary
- Canonical paper claim scope remains Cohere × GSM8K.
- Do not claim broader benchmark/provider generalization without independent verification.
