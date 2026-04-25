# REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION

Timestamp: `20260425T_WULVER_COHERE_LONG`.
Artifact package: `outputs/real_model_ours_vs_external_validation_20260425T_WULVER_COHERE_LONG/`.

## Contract used
- Providers requested: ['cohere']
- Datasets active: ['openai/gsm8k']
- Subset size: 120
- Seeds: [11, 23]
- Budgets: [4, 6, 8]
- Methods requested: ['strict_f3', 'external_l1_max']
- Methods runnable: ['strict_f3', 'external_l1_max']
- Unsupported in current canonical runner: []

## Required headline answers
1. Did best ours beat best external overall? NO
2. Best ours method: N/A (0.0000)
3. Best external method: N/A (0.0000)
4. Ours-minus-external gap: +0.0000
5. Dataset/budget slices: see `summary.md` and `combined_dataset_summary.csv` + `combined_budget_curve.csv`.
6. Failure decomposition categories reported in `combined_failure_decomposition.csv`.
7. API/runtime errors: 0 row(s) in `openai/retry_error_log.csv`.
8. Claim safety: not safe.

## Guardrails
- This run does not claim strict_f3 universally beats strict_gate1_cap_k6.
- Headline remains best-ours family vs best external baseline adapters under shared substrate.
- This is not an official reproduction of external papers.

## Next larger run prepared
- `python scripts/run_real_model_ours_vs_external_validation.py --timestamp 20260424T_OPENAI_REAL_MAIN --providers openai --datasets openai/gsm8k,HuggingFaceH4/MATH-500,HuggingFaceH4/aime_2024 --subset-size 20 --seeds 11,23 --budgets 4,6,8 --methods strict_f3,strict_gate1_cap_k6,strict_f2,external_l1_max,external_l1_exact,external_tale_prompt_budgeting,external_s1_budget_forcing,self_consistency_3 --resume`
