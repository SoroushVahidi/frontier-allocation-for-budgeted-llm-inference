# Canonical Project State and Next Steps (2026-04-29)

## Top-level conclusion
Current 100-case real-model evidence does not support DR-v2 over external_l1_max; DR-v2 failure is primarily final-selection quality when correct traces exist.

## Do-not-repeat list
- Do not treat 10-case DR-v2 positive preflight as canonical.
- Do not run `direct_reserve_semantic_frontier_v2_thresholded_ordered` as a live comparison method.
- Do not claim improvements without 100-case confirmation.

## Evidence summary
- DR-v2 (100-case) underperformed external_l1_max.
- DR-v2 selection-fix still underperformed.
- strict_f3 matched DR-v2 range in same 100-case slices.
- strict_gate1_cap_k6 losses were mostly absent-from-tree.
- DR-v2 losses were mostly present-not-selected.

## Next recommended method
`direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`

Rationale: preserve DR-v2 candidate generation but improve final answer selection via grouped outcome verification.

Current status: implemented and live-runnable with mock verifier default; canonical judgment still pending completed paired 100-case Cohere run.

Run tracking note:
- `20260429T_OV_RERANK_100CASE` is mock-backed diagnostic provenance (OV backend env unset) and is not claim-safe for real outcome-verifier-backend conclusions.
- `20260429T_OV_RERANK_100CASE_COHERE_BACKEND` is the clean real Cohere-backend selector run (new timestamp to avoid mixing mock/cohere-backed OV rows).
