# REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION

Timestamp: `20260424T120000Z_REAL_SMOKE`.
Artifact package: `outputs/real_model_token_accounting_validation_20260424T120000Z_REAL_SMOKE/`.

- This pass is appendix/supporting evidence only and is not a replacement for the primary matched-surface simulation results.
- The core comparison remains primarily action-budget matched.
- Token/latency/cost diagnostics are included to directly address reviewer concerns about accounting visibility.
- The internal strict_f3 vs strict_gate1_cap_k6 difference should not be treated as statistically decisive unless this package shows a clearly stable gap at larger sample sizes.

## Contract
- Mode: `real_api`
- Provider/model: `openai/gpt-4.1-mini`
- Datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Budgets: [4]
- Seeds: [11]
- Subset size: 1
- Methods: ['strict_f3', 'strict_gate1_cap_k6', 'external_l1_max']
- API key present: True

## Files
- `manifest.json`
- `per_case_results.csv`
- `summary_by_method_budget.csv`
- `summary_by_method.csv`
- `STATUS.md`
