# DIRECT_RESERVE_ROUTE_REFINE_COHERE_DIAGNOSTIC_20260427T182300Z

- Prototype status: diagnostic only; not paper-ready.
- Cohere readiness: passed (`COHERE_API_KEY` present, smoke test ok).
- Output directory: `outputs/direct_reserve_route_refine_cohere_diagnostic_20260427T182300Z`

## Required answers
1. Preserve cases solved by external/direct reasoning: **partially** (preserve_rate=0.250).
2. Reduce immediate_miss absent-from-tree failures: **yes**.
3. Beat strict_f3: **yes** (route_refine=0.250, strict_f3=0.000).
4. Beat or approach external_l1_max: **no** (external_l1_max=1.000).
5. Token/cost/latency tradeoff: see `token_cost_latency_summary.csv` (hybrid adds challenger cost only on routed cases).
6. Run 30-case version next: **yes**.

## Controller behavior
- Route decisions: {'longer_direct_continuation': 2, 'frontier_search_challenger': 2}
- Failure modes: {'immediate_miss': 3, 'resolved': 1}
- Completed trace-bearing challenger runs: 0/4
