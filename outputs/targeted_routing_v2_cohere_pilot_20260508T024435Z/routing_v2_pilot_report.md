# Routing v2 Cohere pilot

- Selected cases: 14
- Cohere calls used: 14

## Overall
- exact_match: 10/14
- improved_over_current_integrated: 10/14
- external_l1_only rescued: 0
- both_wrong rescued: 3

## By scaffold
{
  "average_target_score": {
    "exact": 1,
    "total": 1
  },
  "combinatorics_counting": {
    "exact": 1,
    "total": 1
  },
  "percent_base_denominator": {
    "exact": 1,
    "total": 3
  },
  "ratio_partition": {
    "exact": 3,
    "total": 3
  },
  "state_composition": {
    "exact": 4,
    "total": 6
  }
}

## Errors
{
  "api_errors": [],
  "parsing_ambiguities": 0
}

Recommendation: integrate routing v2 in controlled mode and rerun Stage-2 checkpoint if gains hold with zero leakage/errors.
Caveat: this is a focused 14-case live pilot, not a broad baseline comparison.