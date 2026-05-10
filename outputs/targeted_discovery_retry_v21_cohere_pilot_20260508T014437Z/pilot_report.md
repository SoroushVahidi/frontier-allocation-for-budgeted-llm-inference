# Targeted discovery retry v2.1 Cohere pilot

- Output dir: `outputs/targeted_discovery_retry_v21_cohere_pilot_20260508T014437Z`
- Selected cases: 10
- Cohere calls made: 10
- Exact matches: 10/10
- quantity_ledger v2.1 exact matches: 9/9

## openai_gsm8k_841 fixed?
yes

## quantity_ledger regressions (vs v2 exact successes)
(none)

## Results by scaffold
```json
{
  "quantity_ledger": {
    "cases": 9,
    "exact": 9,
    "improved": 9
  },
  "rate_table": {
    "cases": 1,
    "exact": 1,
    "improved": 1
  }
}
```

## API/parsing errors
```json
{
  "api_errors": []
}
```

## Recommendation
If `openai_gsm8k_841` is fixed and no regressions, proceed to a larger capped pilot; otherwise revise quantity_ledger v2.1 recurrence rules.
