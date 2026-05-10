# Targeted discovery retry v2 Cohere pilot

- Output dir: `outputs/targeted_discovery_retry_v2_cohere_pilot_20260508T013332Z`
- Selected cases: 15
- Scaffold counts: `{'quantity_ledger': 6, 'rate_table': 3, 'before_after_state': 3, 'target_difference': 3}`
- Cohere calls made: 15
- Exact matches: 12/15
- Improved over current PAL: 12/15

## Results by scaffold
```json
{
  "quantity_ledger": {
    "cases": 6,
    "exact": 3,
    "improved": 3
  },
  "rate_table": {
    "cases": 3,
    "exact": 3,
    "improved": 3
  },
  "before_after_state": {
    "cases": 3,
    "exact": 3,
    "improved": 3
  },
  "target_difference": {
    "cases": 3,
    "exact": 3,
    "improved": 3
  }
}
```

## quantity_ledger v2: did it fix v1 failures?
```json
{
  "openai_gsm8k_750": true,
  "openai_gsm8k_841": false
}
```

## API/parsing errors
```json
{
  "api_errors": []
}
```

## Recommendation
Continue if both v1 quantity_ledger failures are fixed; otherwise revise quantity_ledger v2 prompt again.
