# L1 Better Than Frontier Casebook

Offline failure casebook for the traced Cohere GSM8K Stage-1 replay. No API calls were made.

- Matched examples: 30
- `external_l1_max` accuracy: 0.7000
- `strict_f3` accuracy: 0.5667
- `direct_reserve_frontier_gate_v1` accuracy: 0.6667
- L1-better-than-strict_f3 cases: 6
- Frontier-better-than-L1 cases: 5
- Both-wrong cases: 7
- Gold absent in L1-better cases: 0
- L1 answer present but not selected: 6
- Wrong frontier answer more supported than gold: 1
- Top failure labels: [('insufficient_branch_diversity', 13), ('unknown_needs_manual_review', 5), ('direct_answer_should_have_been_preserved', 3)]

Recommended next algorithmic fix: better direct preservation plus verifier/answer selection calibration; gold is present in the traced frontier support for these L1-better cases, so selection/preservation is the immediate bottleneck.
