# Adaptive router v3 Cohere pilot

- Selected cases: 10
- Calls used: 10/14

## Results
- exact_match: 8/10
- improved_over_current_integrated: 5/10
- external_l1_only rescue: 0/4
- both_wrong rescue: 1/3

## By scaffold
{
  "average_target_score": {
    "exact": 2,
    "total": 2
  },
  "combinatorics_counting": {
    "exact": 1,
    "total": 1
  },
  "ratio_partition": {
    "exact": 3,
    "total": 4
  },
  "state_composition": {
    "exact": 2,
    "total": 3
  }
}

Supports integrating router-v3 in controlled mode if rescue rates remain stable; run a fresh Stage-2 checkpoint after integration.