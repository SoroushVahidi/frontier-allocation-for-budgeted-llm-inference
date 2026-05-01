# TALE baseline run note

- run_id: `verify_20260421T190758Z_2_tale_mode_a`
- mode: `prompt_budgeting_inference_only`
- dataset: `openai/gsm8k`
- dataset_split: `test`
- subset_size_per_seed: `32`
- seeds: `11, 23, 37`
- budgets(actions): `4, 6, 8`

## Methodological honesty
- MODE A is a faithful in-repo TALE-style prompt budgeting adapter, not full TALE-PT reproduction.
- MODE B is separately labeled official/full import path and may include TALE-PT assets.
- TALE vs TALE-PT identity must be explicit in MODE B metadata and rows.
- Comparisons report matched-average-compute rows to reduce action-space mismatch bias.
