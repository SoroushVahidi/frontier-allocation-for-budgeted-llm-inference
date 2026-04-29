# Cohere DR-v2 vs external_l1_max 100-case validation (20260429T_COHERE_DR_V2_VS_L1_100CASE)

## Scope
- Provider: Cohere
- Dataset: `openai/gsm8k`
- Budget: `4`
- Seed: `11`
- Target: 100 scored per method
- Methods: `direct_reserve_semantic_frontier_v2`, `direct_reserve_semantic_frontier_v2_selection_fix_v1`, `external_l1_max`, `strict_f3`
- Excluded: `direct_reserve_semantic_frontier_v2_thresholded_ordered`

## Final status (all four methods completed 100/100)
- `direct_reserve_semantic_frontier_v2`: accuracy `0.56`
- `direct_reserve_semantic_frontier_v2_selection_fix_v1`: accuracy `0.55`
- `external_l1_max`: accuracy `0.72`
- `strict_f3`: accuracy `0.56`

## Deltas vs external_l1_max
- DR-v2: `0.56 - 0.72 = -0.16`
- DR-v2 selection-fix: `0.55 - 0.72 = -0.17`
- strict_f3: `0.56 - 0.72 = -0.16`

## Paired wins/ties/losses vs external_l1_max (100 paired)
- DR-v2 vs external_l1_max: `9 / 66 / 25`
- DR-v2 selection-fix vs external_l1_max: `9 / 65 / 26`
- strict_f3 vs external_l1_max: `6 / 72 / 22`

## Token / cost / latency summary (final slices)
- DR-v2: `112162` tokens, `$0.590502`, mean latency `9.2057s`
- DR-v2 selection-fix: `112306` tokens, `$0.594198`, mean latency `8.1336s`
- strict_f3: `90648` tokens, `$0.458088`, mean latency `4.3083s`
- external_l1_max: `48892` tokens, `$0.272604`, mean latency `3.6775s`

## Interpretation
- Neither DR-v2 variant beats external_l1_max at 100 examples.
- Selection-fix did **not** improve over original DR-v2 on this slice (0.55 vs 0.56, and slightly worse paired W/T/L).
- strict_f3 and DR-v2 tie on aggregate accuracy (both 0.56), but strict_f3 remains below external_l1_max.
- In this completed four-method set, **no internal version beats external_l1_max**.

## Relation to earlier tiny positive DR-v2 signal
- Earlier 10-example positive DR-v2 signal is not confirmed here.
- This completed 100-example run rejects that positive signal for this setting (provider/dataset/budget/seed).

## Claim-safety impact
- No main-text upgrade.
- Appendix/supporting only: this completed 100-case Cohere slice is unfavorable to all three internal methods vs `external_l1_max`.
