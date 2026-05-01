# L1 baseline run note

- run_id: `verify_20260421T190758Z_5_l1_mode_b`
- mode: `official_full_adapter`
- dataset: `openai/gsm8k`
- subset_size_per_seed: `32`
- seeds: `11, 23, 37`
- budgets(actions): `4, 6, 8`
- action_to_token_equivalent: `64.0`
- l1_exact_token_budget: `512`
- l1_max_token_budget: `512`

## Fairness and claim boundaries
- MODE A compares our method against inference-only L1-style length control (Exact/Max) on the same base model family.
- MODE B (official_full_adapter) is separate reporting and is not apples-to-apples if RL-trained L1 checkpoints are used.
- This run stores exact-match/accuracy, budget adherence/violation, budget error, and frontier summaries.
