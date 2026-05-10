# Integrated live pilot v1

- Selected cases: 15
- Targeted retry cases: 12
- Structural-only cases: 3
- Cohere calls used: 12

## Results
- targeted_retry_exact: 12/12
- structural_commit_fixed: 3/3
- combined_exact_or_fixed: 15/15

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
  "api_errors": [],
  "parsing_ambiguities": 0
}
```

Not yet sufficient for a broad external_l1_max checkpoint; use as end-to-end smoke evidence only.