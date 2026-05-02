# L1 Loss Decomposition (Best Selector) — Salvage from Partial Local Cohere Run

Primary salvage source: `outputs/l1_loss_decomposition_best_selector_20260502T040119Z/real_cohere_run/cohere_real_model_cost_normalized_validation_20260502T040119Z/per_example_records.jsonl`.
Salvage output: `outputs/l1_loss_decomposition_best_selector_20260502T040119Z/salvaged_decomposition/`.

## Result status
- Status: **incomplete_not_evidence** (salvaged package is valid but has 0 complete paired cases).
- Full 100-case evidence: **No**.
- Diagnostic partial (>=25 paired): **No**.

## Direct answers
1. Selected method lane: `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1` by priority policy, but no complete paired cases were available.
2. Run type: **incomplete**.
3. Total paired cases: **0**.
4. L1-correct / ours-wrong count: **0**.
5. Gold absent from tree: **0**.
6. Gold present but not selected: **0**.
7. Parse/canonicalization failures: **0**.
8. Selector-score/cache-limited: **0**.
9. Trace/candidate missing or unknown among L1-correct/ours-wrong: **0**.
10. Bottleneck conclusion: `inconclusive_due_to_small_n`.
11. Manuscript-safe claim enabled: **No**.

Safe conclusion: On this paired Cohere slice, the salvage shows incomplete evidence only; no manuscript claim is enabled until a sufficiently powered paired run is completed.
