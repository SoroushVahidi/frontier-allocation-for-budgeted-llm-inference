# L1 Loss Decomposition vs Best Selector/Reranker (Cohere)

Status date: 2026-05-01.

## Direct answers
1. **Selected method compared to L1:** no method could be selected for final paired analysis because no complete local 100-case paired real-Cohere artifact with required per-case trace evidence was available.
2. **100-case real Cohere or diagnostic-only?** Diagnostic/blocker-only.
3. **How many cases did selected method lose to L1?** Not computable from real paired execution in this environment.
4. **Gold absent from tree losses?** Not computable.
5. **Gold present but not selected losses?** Not computable.
6. **Parse/canonicalization failures?** Not computable.
7. **Selector-score/cache-limited failures?** Not computable.
8. **Unknown because traces/candidates missing?** Not computable.
9. **Main bottleneck suggestion?** Cannot conclude from blocked run; this remains unresolved pending real Cohere execution.
10. **Safe for manuscript use?** No. This is blocker evidence only.

## Safe conclusion wording
- “This is diagnostic unless the run is completed, real-Cohere, paired, and full-coverage.”
- “No model-performance conclusion can be drawn because Cohere execution did not run.”

## How to rerun after environment fix
Run the command written in:
- `outputs/l1_loss_decomposition_best_selector_<STAMP>/cohere_readiness_failure_report.json`
