# CROSS_PROVIDER_REAL_MODEL_TOKEN_ACCOUNTING_VALIDATION

Timestamp: `20260424T140000Z_CROSS_REAL`.
Artifact package: `outputs/cross_provider_real_model_token_accounting_validation_20260424T140000Z_CROSS_REAL/`.

- This pass is appendix/supporting evidence and not a replacement for primary matched-surface simulation results.
- It addresses provider-robustness and token/latency/cost-accounting visibility concerns.
- It does not convert the paper into a systems-cost paper.
- Action-budget matching remains the primary comparison contract.
- Strict-F3 vs Strict-Gate1-Cap-K6 should remain non-decisive unless stronger, larger-sample evidence appears.

## Contract
- Providers: ['openai', 'cohere']
- Provider models: {'openai': 'gpt-4.1-mini', 'cohere': 'command-r-plus-08-2024'}
- Datasets: ['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']
- Budgets: [4, 6, 8]
- Seeds: [11, 23]
- Subset size: 1
- Methods: ['strict_f3', 'strict_gate1_cap_k6', 'external_l1_max']

## Files
- `manifest.json`
- `per_case_results.csv`
- `summary_by_provider_method_budget.csv`
- `summary_by_provider_method.csv`
- `STATUS.md`
