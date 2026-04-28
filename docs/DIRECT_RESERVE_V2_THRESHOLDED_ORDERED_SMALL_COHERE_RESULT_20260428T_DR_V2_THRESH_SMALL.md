# Direct-Reserve v2 Thresholded Ordered Small Cohere Diagnostic Result (20260428T_DR_V2_THRESH_SMALL)

## A) Run status
- Cohere readiness pass: yes (`COHERE_API_KEY: present`; readiness=`passed`).
- Selected slots: 0.
- Unique example IDs: 0.
- Duplicate fallback rows used: 0.
- Issue files created: none.
- Output directory: `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_THRESH_SMALL`.
- Analyzer command status: failed (`per_case_results.csv` missing because zero slots were selected).

## B) Accuracy/action table
No evaluable rows were produced because selected slots = 0. The requested method set was:
- `external_l1_max`
- `strict_f3`
- `direct_reserve_semantic_frontier_v1`
- `direct_reserve_semantic_frontier_v2_thresholded_ordered`

| method | n | accuracy | average actions | average cost/token proxy |
|---|---:|---:|---:|---:|
| external_l1_max | 0 | N/A | N/A | N/A |
| strict_f3 | 0 | N/A | N/A | N/A |
| direct_reserve_semantic_frontier_v1 | 0 | N/A | N/A | N/A |
| direct_reserve_semantic_frontier_v2_thresholded_ordered | 0 | N/A | N/A | N/A |

## C) v2 vs v1
- accuracy delta: N/A
- action delta: N/A
- did v2 reduce actions? cannot determine (no rows)
- did v2 preserve most of v1 accuracy? cannot determine (no rows)
- did v2 regress on cases where v1 was correct? cannot determine (no rows)

## D) v2 vs strict_f3
- accuracy delta: N/A
- action delta: N/A
- does v2 still clearly beat strict_f3? cannot determine (no rows)

## E) v2 vs external_l1_max
- accuracy delta: N/A
- action delta: N/A
- is v2 closer to external_l1_max in cost? cannot determine (no rows)
- is v2 Pareto-better than external_l1_max? cannot determine (no rows)

## F) Threshold behavior (v2)
No route-level traces were produced because no slots were selected.
- route_decision.stop_with_incumbent: 0
- route_decision.one_more_direct_continuation: 0
- route_decision.limited_frontier_challenge: 0
- final_source.incumbent: 0
- final_source.challenger: 0
- final_source.fallback: 0
- continuation_threshold blocked frontier expansion: 0 observed rows (no rows)
- average frontier_actions_used: N/A
- average direct_actions_used: N/A
- thresholding reduced compute relative to v1: cannot determine (no rows)

## G) Recommendation
- Ready for larger Wulver run: **No**, until the selection profile yields nonzero eligible GSM8K cases.
- Threshold tuning (loosen/tighten): no recommendation from this run (insufficient data).
- Manuscript impact: **No change** (diagnostic produced zero evaluable cases).
