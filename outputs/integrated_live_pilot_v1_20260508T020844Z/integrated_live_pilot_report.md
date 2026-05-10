# Integrated live pilot v1

- Selected cases: 15
- Targeted retry cases: 12
- Structural-only cases: 3
- Cohere calls used: 0

## Results
- targeted_retry_exact: 0/12
- structural_commit_fixed: 3/3
- combined_exact_or_fixed: 3/15

## By track/scaffold
```json
{
  "targeted_retry::quantity_ledger": 5,
  "targeted_retry::rate_table": 3,
  "targeted_retry::before_after_state": 2,
  "targeted_retry::target_difference": 2,
  "structural_commit_only::none": 3
}
```

## Failures / errors
```json
{
  "api_errors": [
    "openai_gsm8k_1006: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1027: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1029: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1003: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1099: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_906: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1166: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_818: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1019: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1187: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1045: ModuleNotFoundError: No module named 'cohere'",
    "openai_gsm8k_1155: ModuleNotFoundError: No module named 'cohere'"
  ],
  "parsing_ambiguities": 0
}
```

Not yet sufficient for a broad external_l1_max checkpoint; use as end-to-end smoke evidence only.