# L1 loss decomposition (best DR-v2 selector lane)

- Timestamp: `20260502T004638Z`
- Selected method: `direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1`
- Paired cases (usable): **100**
- Target: **100**
- L1 accuracy: **0.7600**
- Selected accuracy: **0.6700**
- Δ (selected − L1): **-0.0900**

## Loss buckets among L1-correct / selected-wrong

| Bucket | Count |
|---|---:|
| gold_absent_from_candidate_tree | 5 |
| gold_present_but_not_selected | 1 |
| parse_or_canonicalization_failure | 7 |
| selector_missing_score_or_cache_limited | 0 |
| trace_or_candidate_artifact_missing | 0 |
| unknown | 0 |

- Bottleneck conclusion: **discovery_coverage_dominant**
- Claim safety status: **evidence_complete_100case**

