# Targeted discovery retry pilots — consolidation

Previous discrepancy came from mixing status definitions: the old summary used v1+v2-only status while the recommended prompt versions already pointed to v2.1.
This corrected bundle reports both `ever_exact` and `recommended_version_exact`.

Total unique cases piloted: 25
Solved (ever exact): 18
Solved (recommended version exact): 18
Unsolved by ever_exact: 0
Unsolved by recommended version: 0

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

## Unsolved case IDs (recommended version)

(none)

## Recommendation
Integrate targeted retry with `structural_commit_v1` using recommended prompt versions; keep an allowlist/guard that excludes remaining percent-denominator outliers from automatic retry.