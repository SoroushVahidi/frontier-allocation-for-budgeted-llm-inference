# Method maturity and stop-improvement audit

## Current best main method
- production_equiv_v1: 36/50 on matched Stage-3 set.
- Beats individual fair baselines (L1=31, SC4=33, S1=32, TALE-EP=34).
- Trails best_core4 oracle by 2 and prior patch-focused by 3.

## Improvement mechanisms tried
- Free-form retry + commit: multiple pilots, output-contract and parsefix variants.
- Schema-grounded retry v1: fixed-schema prompts + structured parser/validator.

## Why free-form retry should be stopped
- Across micro-pilots, retry_exact_count and improvement_count remained 0.
- Conservative parse/alias fallbacks did not recover additional correct cases.
- Any further softening of commit policy would be unsafe and poorly evidenced.

## Why schema-grounded retry should be stopped
- Original and parsefix 5-case probes both yielded 0/5 parse + validation success under strict schemas.
- Stronger contracts and clean dev cases did not change this behavior.
- Additional schema complexity is unlikely to overcome the current model’s format non-compliance.

## Remaining failure patterns and actionability
- 113 unique our-failure cases; majority are parse/unknown_or_mixed.
- Ratio-equation and before/after-state families have some support but no safe, working retry mechanism.
- Best use of these families is now qualitative analysis and discussion of open error modes.

## Recommended next steps for a strong paper
- Focus on **evaluation and framing**, not further prompt patches:
  - Solidify external baseline suite (including SC6/PAL where feasible).
  - Prepare clear ablation and comparison tables for the matched-50 setting.
  - Use the 113-case failure bank to narrate failure modes and negative results.
- Treat both free-form and schema-grounded retries as **negative diagnostics**, not main methods.

## Safe claims now
- production_equiv_v1 vs fair external baselines on matched-50.
- Characterization of retry/patch attempts as non-improving under strict, small-sample probes.

## Claims that are not yet safe
- Any broad improvement claim from targeted retry mechanisms.
- Any 245-case robustness claim without a finalized baseline suite and clearer method storyline.
