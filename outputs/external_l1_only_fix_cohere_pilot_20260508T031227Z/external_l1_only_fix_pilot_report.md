# External L1-only Fix Cohere Pilot Report

- Selected cases: 7
- Actual Cohere calls: 7
- Exact matches: 5/7
- Improved over current integrated: 5/7
- External_l1-only rescues: 5/7

## Results by scaffold
- final_target_verifier_retry: exact 2/2, improved 2/2
- l1_style_concise_decomposition: exact 1/1, improved 1/1
- percent_base_denominator_v2: exact 0/1, improved 0/1
- ratio_partition_v2: exact 1/2, improved 1/2
- state_composition_v2: exact 1/1, improved 1/1

## Rescued external_l1-only cases
- openai_gsm8k_674
- openai_gsm8k_746
- openai_gsm8k_752
- openai_gsm8k_758
- openai_gsm8k_765

## Failures and suspected reasons
- Remaining misses likely due to target extraction drift, denominator/base mis-binding, or parse ambiguity.

## Integration decision
- Integrate fixes only if rescue count and no-regression profile are acceptable in this focused pilot.
- Stage-2 rerun justified only with positive rescue signal and bounded ambiguity/API error rate.

## Caveats
- Focused 7-case slice; not representative of full Stage-2 distribution.
- Offline scoring uses gold only post-generation.
