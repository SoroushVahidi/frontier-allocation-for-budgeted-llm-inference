# Thresholded/ordered fix check (2026-04-29)

## What was wrong
The prior preflight reported `direct_reserve_semantic_frontier_v2_thresholded_ordered` with 0 scored rows because its runtime is not in the runner execution specs, but old validation incorrectly marked it runnable by checking the semantic diagnostic registry as well.

## What was fixed or not fixed
Fixed validation/wiring only: `--validate-methods-only` now distinguishes `runnable` vs `diagnostic_only` using runner specs first. No controller algorithm behavior was changed. The thresholded/ordered method remains excluded from this runner live check.

## Methods run
| method_id | included_in_live_command | scored_nonzero |
|---|---|---|
| direct_reserve_semantic_frontier_v2_thresholded_ordered | no (diagnostic_only in current runner path) | no |
| direct_reserve_semantic_frontier_v2 | yes | yes |
| external_l1_max | yes | yes |

## Accuracy and scored counts
| method | scored count | accuracy | total tokens | estimated cost USD |
|---|---:|---:|---:|---:|
| direct_reserve_semantic_frontier_v2 | 10 | 0.700 | 10597 | 0.054915 |
| external_l1_max | 10 | 1.000 | 4791 | 0.026865 |

## Pairwise result
| pair | matched examples | mean delta (internal-comparator) | wins/ties/losses |
|---|---:|---:|---|
| direct_reserve_semantic_frontier_v2_thresholded_ordered vs external_l1_max | 0 | N/A | N/A |
| direct_reserve_semantic_frontier_v2 vs external_l1_max | 10 | -0.300 | 0/7/3 |

## Direct answer
- Did thresholded/ordered become runnable? **No** (diagnostic_only in this runner path).
- Did it score nonzero rows? **No** (not run).
- Did it beat external_l1_max? **Not evaluable** in this runner path.
- Did direct_reserve_semantic_frontier_v2 still beat external_l1_max? **No** in this targeted rerun (0.700 vs 1.000, delta -0.300).
- Should this change manuscript claims? **No**; still small-sample diagnostic-only evidence.
- Is this still diagnostic-only? **Yes**.