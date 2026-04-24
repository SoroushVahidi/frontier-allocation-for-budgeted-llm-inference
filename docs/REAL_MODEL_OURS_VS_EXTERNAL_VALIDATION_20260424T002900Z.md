# REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION

Timestamp: `20260424T002900Z`.
Artifact package: `outputs/real_model_ours_vs_external_validation_20260424T002900Z/`.

## Contract
- Datasets requested: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024', 'olympiadbench']
- Datasets active: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024', 'olympiadbench']
- Subset size: 20
- Seeds: [11, 23]
- Budgets: [4, 6, 8]
- Methods: ['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max', 'self_consistency_3']
- OpenAI model: `gpt-4.1-mini`
- Cohere model: `command-r-plus-08-2024`

## Status
- OpenAI status: attempted=True completed=False reason=dry_run_no_api_calls
- Cohere status: attempted=True completed=False reason=dry_run_no_api_calls

## Headline interpretation
- The headline comparison is ours-family vs external baselines under a matched API substrate.
- We do not claim strict_f3 universally beats strict_gate1_cap_k6; internal ordering is not the headline claim.
- We do not claim official reproduction of external papers; these are near-direct matched adapter baselines under shared substrate.

## Quantitative pointers
- See `combined_ours_vs_external_summary.csv`, `combined_dataset_summary.csv`, `combined_budget_curve.csv`, `combined_provider_summary.csv`.
- See `claim_safety_matrix.csv` for main/appendix/supportive/not-safe status.

## Conservative conclusion
- The real-model validation tests whether the proposed frontier-allocation family, represented by strict_f3/strict_gate1_cap_k6/strict_f2, improves over near-direct external adaptive-compute adapter baselines under a shared API-backed substrate.
- Internal variant ordering is treated as surface-sensitive and is not the headline claim.
