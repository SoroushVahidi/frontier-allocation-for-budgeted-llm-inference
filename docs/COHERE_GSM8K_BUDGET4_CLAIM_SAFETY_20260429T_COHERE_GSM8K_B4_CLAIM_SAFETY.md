# Cohere GSM8K Budget-4 Claim-Safety Diagnostic (20260429T_COHERE_GSM8K_B4_CLAIM_SAFETY)

## Scope
- Provider: Cohere
- Dataset: `openai/gsm8k`
- Budget: `4`
- Seed: `11`
- Target: 100 scored examples/method
- Priority methods planned: `strict_f3`, `external_l1_max`, `strict_gate1_cap_k6`, `tale`, `s1`
- Excluded: `direct_reserve_semantic_frontier_v2_thresholded_ordered`

## Completion status
Completed final (100/100):
- `strict_f3`
- `external_l1_max`

Not final yet in this timestamp:
- `strict_gate1_cap_k6`
- `tale`
- `s1`

## Main claim-safety comparison
- `strict_f3` accuracy: **0.55**
- `external_l1_max` accuracy: **0.72**
- Delta (`strict_f3 - external_l1_max`): **-0.17**
- Did `strict_f3` beat `external_l1_max` at budget 4? **No**.

## Budget-4 vs budget-2 interpretation
- Budget-2 prior diagnostic: delta `-0.15` (`0.54 - 0.69`).
- Budget-4 current diagnostic: delta `-0.17` (`0.55 - 0.72`).
- Interpretation: this follow-up **confirms** (not reverses/reduces) the disadvantage in the matched slice currently completed.

## Other method questions
- `strict_gate1_cap_k6` vs `strict_f3`: not yet evaluable in this timestamp (method incomplete).
- `tale` and `s1`: not yet completed in this timestamp; no final-safe comparison yet.

## Claim implications
Supported wording (appendix/supporting only):
- "In Cohere GSM8K diagnostics at budget 4 (seed 11), strict_f3 underperformed external_l1_max on the completed matched slice (0.55 vs 0.72)."
- "Increasing budget from 2 to 4 did not reverse the strict_f3 disadvantage against external_l1_max in this diagnostic setup."

Still unsafe:
- Any dominance/universal superiority claim for frontier allocation on real-model provider runs.
- Any canonical main-text promotion from this diagnostic run alone.
- Any claim about `strict_gate1_cap_k6`, `tale`, or `s1` relative order at budget 4 before their slices are final.
