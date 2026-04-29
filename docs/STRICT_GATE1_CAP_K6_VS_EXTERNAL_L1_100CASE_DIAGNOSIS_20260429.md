> **WARNING (diagnostic/small-sample):** This document is not standalone canonical paper-facing evidence. Do not use for broad superiority claims without canonical matched-surface confirmation.

# Strict-gate1-cap-k6 vs external_l1_max 100-case Cohere diagnosis (2026-04-29)

## Setup
- Timestamp: `20260429T_STRICT_GATE1_CAP_K6_VS_L1_100CASE_DIAG`
- Provider: Cohere
- Dataset: `openai/gsm8k`
- Budget: `4`
- Seed: `11`
- Methods: `strict_gate1_cap_k6`, `external_l1_max`

## Main result
- `strict_gate1_cap_k6` accuracy: **0.48**
- `external_l1_max` accuracy: **0.75**
- Delta (`strict_gate1_cap_k6 - external_l1_max`): **-0.27**
- Conclusion: strict_gate1_cap_k6 does **not** beat external_l1_max on this clean 100-case test.

## Paired outcomes (100 paired)
- both_correct: 47
- both_wrong: 24
- strict_gate1_only_correct: 1
- external_l1_only_correct: 28
- paired wins/ties/losses (strict_gate1 vs l1): **1 / 71 / 28**

## Token/cost/latency comparison
- strict_gate1_cap_k6: 92,503 tokens; $0.471117; mean latency 4.1036s
- external_l1_max: 49,606 tokens; $0.277338; mean latency 3.2539s
- strict_gate1 is materially more expensive while underperforming.

## Loss-mode diagnosis counts (strict_gate1 losses)
Across 28 strict_gate1 loss cases to l1:
- correct answer absent from explored tree: **26**
- correct answer present but not selected: **2**
- extraction/canonicalization mismatch: **0**
- early commit / insufficient expansion: **0 explicit instrumentation** (unavailable)
- unknown: **0**

## Branch/action-to-correct visibility
- Average strict_gate1 total actions in loss cases is available via `strict_gate1_action_count`.
- But branch-to-correct path fields (first branch producing correct answer, depth-first-correct, actions-before-correct, prune/abandon flags) are not consistently emitted; marked unavailable/NA.

## Repeated failure patterns
Top repeated patterns:
1. Correct answer absent from strict_gate1 explored tree.
2. Large tie mass (71 ties), with losses dominating wins in non-tie cases.
3. Higher token/cost footprint without accuracy gain.

## Most justified algorithm fix
Prioritize **coverage/recall improvement before selector tuning**:
- Increase probability that gold answer is generated in-tree (family/diversity/coverage intervention), then reassess selector logic.
- Selector-only fixes are unlikely to close a gap dominated by absent-from-tree failures.
