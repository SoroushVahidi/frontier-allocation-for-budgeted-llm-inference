# Selector decision snapshot

- partial cache coverage: 60/94
- cases fully scored: 28
- cases partially scored: 1
- missing/unscored candidates: 34

| selector | coverage | overrides | fixes | breaks | net | precision | acc |
|---|---:|---:|---:|---:|---:|---:|---:|
| conservative_trace_support_selector_v1 | n/a | 0 | 0 | 0 | 0 | 0.000 | 0.000 |
| ov_trace_quality_heuristic_margin_0.15 | heuristic(no api) | 36 | 20 | 0 | 20 | 0.556 | 0.426 |
| ov_cohere_cached_partial_margin_0.15 | 60/94 | 30 | 16 | 0 | 16 | 0.533 | 0.340 |
| ov_cohere_cached_partial_best_margin_0.00 | 60/94 | 33 | 18 | 0 | 18 | 0.545 | 0.383 |

## Current selector recommendation

B. outcome_verifier_answer_group_selector_v1 with trace_quality_heuristic, margin 0.15

This is partial selector evidence, not final runtime safety or external_l1_max defeat claim.
