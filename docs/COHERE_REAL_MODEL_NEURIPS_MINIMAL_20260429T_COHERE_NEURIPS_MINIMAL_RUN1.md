# Cohere Real-Model NeurIPS Minimal Run Report (20260429T_COHERE_NEURIPS_MINIMAL_RUN1)

## Scope
- Provider: Cohere
- Dataset: `openai/gsm8k`
- Budget: `2`
- Seed: `11`
- Target: `100` scored examples per method
- Methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`, `direct_reserve_semantic_frontier_v2`, `direct_reserve_semantic_frontier_v2_selection_fix_v1`, `external_l1_max`, `tale`, `s1`, `self_consistency_3`
- Excluded as required: `direct_reserve_semantic_frontier_v2_thresholded_ordered`

## Completion status
Completed exactly 100 scored examples:
- `strict_f3` (100)
- `strict_gate1_cap_k6` (100)
- `strict_f2` (100)
- `external_l1_max` (100)
- `tale` (100)
- `s1` (100)

Not completed to exactly 100:
- `self_consistency_3` (0)
- `direct_reserve_semantic_frontier_v2_selection_fix_v1` (42)
- `direct_reserve_semantic_frontier_v2` (162; exceeds target due prior rerun/resume accumulation and is not final-safe)

## Headline comparisons requested
- Did `strict_f3` beat `external_l1_max`? **No.**
- Did `strict_f3` lose to `external_l1_max`? **Yes.**
- `strict_f3` accuracy: **0.54**
- `external_l1_max` accuracy: **0.69**
- Delta (`strict_f3 - external_l1_max`): **-0.15** (unfavorable to `strict_f3`).
- `strict_gate1_cap_k6` vs `strict_f3`: tie (`0.54` vs `0.54`).
- Best method among final-safe slices: `external_l1_max` (`0.69`).
- Worst method among final-safe slices: tie between `strict_f3` and `strict_gate1_cap_k6` (`0.54`).

## Failures / limits
- No explicit quota/rate-limit/API auth failure was surfaced in completed chunk logs.
- Run continuation is still open for `self_consistency_3` and direct-reserve nonfinal slices.

## Field availability
- Token/cost/latency fields are available for completed slices (`total_tokens`, `estimated_cost_usd`, `avg_latency_seconds`) in finality outputs.

## Claim-safety interpretation
Safer now:
- Appendix-level statement that this exact Cohere minimal slice includes completed external baseline evidence (`external_l1_max`, `tale`, `s1`) on the same dataset/budget/seed contract.
- Appendix-level statement that in this completed slice subset, `strict_f3` is below `external_l1_max`.

Still unsafe:
- Any dominance/universal real-model claim.
- Any promotion of this run to canonical paper-table evidence.
- Any claim that requires completed `self_consistency_3` or finalized direct-reserve slices in this timestamp.
