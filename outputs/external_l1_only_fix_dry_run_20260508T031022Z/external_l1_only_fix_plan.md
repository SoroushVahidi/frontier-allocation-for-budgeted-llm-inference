# External L1-only Fix Dry Run Plan

## Per-case proposed fixes
- openai_gsm8k_674: new_scaffold via `state_composition_v2` (better_state_model)
- openai_gsm8k_683: combined via `percent_base_denominator_v2` (better_percent_base)
- openai_gsm8k_746: verifier_check via `final_target_verifier_retry` (better_final_target)
- openai_gsm8k_752: new_scaffold via `ratio_partition_v2` (better_ratio_setup)
- openai_gsm8k_758: l1_style_prompt via `l1_style_concise_decomposition` (better_decomposition)
- openai_gsm8k_765: verifier_check via `final_target_verifier_retry` (better_final_target)
- openai_gsm8k_769: new_scaffold via `ratio_partition_v2` (better_ratio_setup)

## Strategy split
- verifier-only: `final_target_verifier_retry` and sign/target checks
- scaffold retry: ratio/state/percent-base v2 focused scaffolds
- L1-style prompt ablation: concise decomposition for decomposition-sensitive case(s)

## Expected risks
- over-triggering percent-base logic on non-percent ratio cases
- final-target verifier may catch sign issues but miss subtle denominator drift
- concise prompts can reduce explanation quality on multi-step states

## Next live pilot scoring (7-case)
- primary: exact-match wins over current integrated prediction on these 7 IDs
- secondary: no regressions on already-correct target direction
- telemetry: verifier flags fired, scaffold chosen, final-target mismatch warnings

## Stage-2 rerun feed-in
- If >=3/7 external_l1-only rescues with <=1 harm, promote to guarded 100-case rerun path.
- Otherwise keep changes offline and iterate verifier/scaffold mapping only.
