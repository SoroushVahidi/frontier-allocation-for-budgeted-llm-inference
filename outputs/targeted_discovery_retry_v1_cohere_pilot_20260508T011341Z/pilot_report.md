# Targeted discovery retry v1 Cohere pilot

- Output dir: `outputs/targeted_discovery_retry_v1_cohere_pilot_20260508T011341Z`
- Selected cases: 10
- Scaffold counts: {'quantity_ledger': 3, 'rate_table': 3, 'before_after_state': 2, 'target_difference': 2}
- Cohere calls made: 10
- Exact matches: 8/10
- Improved over current PAL: 8/10

## Results by scaffold
```json
{
  "quantity_ledger": {
    "cases": 3,
    "exact_match": 1,
    "improved_over_pal": 1,
    "parse_or_api_issues": 0
  },
  "rate_table": {
    "cases": 3,
    "exact_match": 3,
    "improved_over_pal": 3,
    "parse_or_api_issues": 0
  },
  "before_after_state": {
    "cases": 2,
    "exact_match": 2,
    "improved_over_pal": 2,
    "parse_or_api_issues": 0
  },
  "target_difference": {
    "cases": 2,
    "exact_match": 2,
    "improved_over_pal": 2,
    "parse_or_api_issues": 0
  }
}
```

## Parsing ambiguities / API errors
```json
{
  "api_errors": [],
  "ambiguous_parse_cases": []
}
```

## Recommendation
continue with a slightly larger capped pilot
