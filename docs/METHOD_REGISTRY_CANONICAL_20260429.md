# Method Registry Canonical (2026-04-29)

| method ID | description | live-runnable? yes/no | diagnostic-only? yes/no | obsolete/superseded? yes/no | proposed/not implemented? yes/no | where implemented | where tested | best known result | known failure mode | test again? | exact next action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| external_l1_max | External L1 max baseline | yes | no | no | no | runtime strategy registry | validation scripts | 0.72/0.75 references | baseline can miss deep branch signals | no | keep as comparator |
| strict_f3 | Strong internal matched-surface method | yes | no | no | no | runtime strategy registry | real-model validation logs | 0.56 vs external_l1_max 0.72 | not clearly superior | yes | rerun only with fixed protocol |
| strict_gate1_cap_k6 | capped gate variant | yes | no | no | no | runtime strategy registry | real-model validation logs | 0.48 vs external_l1_max 0.75 | absent-from-tree losses | no | keep as diagnostic comparator |
| strict_f2 | strict depth-2 variant | yes | no | no | no | runtime strategy registry | real-model validation logs | below external_l1_max | similar selection brittleness | no | keep as secondary comparator |
| direct_reserve_semantic_frontier_v1 | DR semantic v1 | yes | no | no | no | runtime strategy registry | validation scripts | below external_l1_max | candidate quality gap | no | legacy reference only |
| direct_reserve_semantic_frontier_v2 | DR semantic v2 | yes | no | no | no | runtime strategy registry | validation scripts | 0.56 vs external_l1_max 0.72 | present-not-selected failures | yes | keep as generator base |
| direct_reserve_semantic_frontier_v2_selection_fix_v1 | DR-v2 selection fix | yes | no | no | no | runtime strategy registry | validation scripts | 0.55 vs external_l1_max 0.72 | selection still weak | yes | supersede with OV rerank |
| direct_reserve_semantic_frontier_v2_thresholded_ordered | thresholded ordered diagnostic | no | yes | no | no | diagnostic controller only; not runtime-present | diagnostic runs | none canonical | not live-runnable in strategy builder | no | keep excluded from live runs |
| near_direct_reserve_frontier_gate_v1 | near-direct reserve gate | yes | no | no | no | runtime strategy registry | validation scripts | mixed | near-tie instability | maybe | small targeted rerun only |
| calibrated_near_direct_frontier_gate_v1 | calibrated near-direct gate | yes | no | no | no | runtime strategy registry | validation scripts | mixed | calibration drift | maybe | targeted sanity check |
| direct_reserve_semantic_frontier_v2_outcome_verifier_rerank_v1 | DR-v2 + answer-grouped outcome verifier rerank | no | no | no | yes | experiments/answer_grouped_outcome_verifier.py (module scaffolding) | tests/test_answer_grouped_outcome_verifier.py | not yet run live | live integration pending | yes | integrate runtime hook, then validate-methods-only |
| Cobbe-style outcome verifier diagnostics | outcome verifier diagnostics only | no | yes | no | yes | planned diagnostics scripts | none | none | no live backend yet | yes | add verifier backend mock/live adapter |
| PRM partial-scoring variants | PRM-based branch scoring variants | no | yes | no | no | runtime/diagnostic mixed | PRM tests | mixed | early reject risk | maybe | keep diagnostic |
| BT/tie-aware branch-scorer variants | learned BT/tie-aware scoring | no | yes | no | no | runtime when model available | scorer tests | mixed | model-dependence | maybe | evaluate only with model artifact |
