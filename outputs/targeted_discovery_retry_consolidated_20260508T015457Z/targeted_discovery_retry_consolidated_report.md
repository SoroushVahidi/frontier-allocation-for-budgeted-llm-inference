# Targeted discovery retry pilots — consolidation

Total unique cases piloted: 25
Solved (ever exact): 13
Unsolved: 5

## Results by scaffold (occurrence-level exact)

{
  "quantity_ledger": {
    "cases": 18,
    "exact": 13
  },
  "rate_table": {
    "cases": 7,
    "exact": 7
  },
  "before_after_state": {
    "cases": 5,
    "exact": 5
  },
  "target_difference": {
    "cases": 5,
    "exact": 5
  }
}

## Unsolved case IDs

openai_gsm8k_1006, openai_gsm8k_1027, openai_gsm8k_1155, openai_gsm8k_814, openai_gsm8k_841

## Recommendation
Integrate targeted retry with `structural_commit_v1` using the best prompt versions; keep an allowlist for percent/base-denominator ambiguous cases (the remaining unsolved quantity_ledger ones).