# s1 baseline run note

- run_id: `verify_20260421T190758Z_1_s1_mode_b`
- mode: `full_or_official`
- dataset: `openai/gsm8k`
- dataset_split: `test`
- subset_size_per_seed: `32`
- seeds: `11, 23, 37`
- budgets(actions): `4, 6, 8`
- action_to_token_equivalent: `64.0`

## Fairness and claim boundaries
- MODE A (inference_only) compares our method and s1 budget forcing on the same base model family.
- MODE B (full_or_official) is reported separately and is not apples-to-apples if post-training is included.
- This run stores exact-match/accuracy, compute-cost proxies, budget adherence, and frontier summaries.
