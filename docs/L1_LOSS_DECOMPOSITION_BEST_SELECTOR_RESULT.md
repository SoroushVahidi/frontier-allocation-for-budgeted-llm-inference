# L1 Loss Decomposition vs Best Selector/Reranker (Cohere)

Run: `20260501T023500Z` (real Cohere calls, paired cases: 1).

1. **Selected method compared to L1:** `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`.
2. **100-case real Cohere or diagnostic-only?** Diagnostic-only (1 paired case, not 100).
3. **How many cases did selected method lose to L1?** 0.
4. **Among those losses, how many had gold absent from the tree?** 0.
5. **How many had gold present but not selected?** 0.
6. **How many were parse/canonicalization failures?** 0.
7. **How many were selector-score/cache-limited?** 0.
8. **How many were unknown because traces/candidates were missing?** 0.
9. **Main bottleneck suggestion?** No conclusion from this 1-case slice.
10. **Safe for manuscript use?** No; this is diagnostic only.

Safe wording:
- “This is diagnostic unless the run is completed, real-Cohere, paired, and full-coverage.”
