# Best Methods on 100 External-Loss Cases

- Selected cases: 88
- Included existing trace-complete cases: 22 (target reference: 47)
- Included final-row-only backfill: 66
- Evaluated methods: direct_reserve_semantic_frontier_v2, external_l1_max, strict_f3, strict_gate1_cap_k6
- Does current/default beat external_l1_max on this subset: no
- Selector-recoverable count: 22
- Discovery-failure count: 66
- Recommendation: keep oracle as diagnostic ceiling only; promote only if deployable method exceeds L1 on this subset.