# Semantic diversity expanded-pool result analysis (20260428T_DR_V2_LONG)

## A. Job and data status

- Job completion (Slurm `1011613`): **completed** (exit code 0, from `sacct`).
- Output directory: `outputs/semantic_diversity_controller_diagnostic_20260428T_DR_V2_LONG`
- Issue files present: `cohere_api_key_issue.md=False`, `run_failure_issue.md=False`
- Selected slots (rows): **30**
- Unique example IDs: **16**
- Duplicate/cycle fallback slots: **14**
- Methods included: `direct_reserve_semantic_frontier_v1`, `direct_reserve_semantic_frontier_v2`, `external_l1_max`, `semantic_minimum_maturation_plus_direct_reserve_v1`, `strict_f3`
- Budgets included: `4`, `6`, `8`
- Total analyzed non-error rows (`per_case_results.csv`): **450**

## B. Accuracy/action summary (all selected slots)

| method | n | accuracy | avg_actions | avg_cost_proxy |
|---|---:|---:|---:|---:|
| direct_reserve_semantic_frontier_v1 | 90 | 0.6778 | 4.60 | 0.000442 |
| direct_reserve_semantic_frontier_v2 | 90 | 0.7778 | 2.37 | 0.000227 |
| external_l1_max | 90 | 0.7111 | 1.01 | 0.000097 |
| semantic_minimum_maturation_plus_direct_reserve_v1 | 90 | 0.6778 | 4.58 | 0.000439 |
| strict_f3 | 90 | 0.4778 | 2.86 | 0.000274 |

## C. Unique-example-only analysis (duplicate-aware)

Per method, accuracy is averaged per `example_id` over available budgets, then averaged across unique examples.

| method | unique_examples | unique-example accuracy |
|---|---:|---:|
| direct_reserve_semantic_frontier_v1 | 16 | 0.6389 |
| direct_reserve_semantic_frontier_v2 | 16 | 0.7708 |
| external_l1_max | 16 | 0.7031 |
| semantic_minimum_maturation_plus_direct_reserve_v1 | 16 | 0.6372 |
| strict_f3 | 16 | 0.5694 |

Per-budget unique-example accuracy:
- budget 4: `direct_reserve_semantic_frontier_v1`=0.6875, `direct_reserve_semantic_frontier_v2`=0.7500, `external_l1_max`=0.7500, `semantic_minimum_maturation_plus_direct_reserve_v1`=0.6875, `strict_f3`=0.5625
- budget 6: `direct_reserve_semantic_frontier_v1`=0.4375, `direct_reserve_semantic_frontier_v2`=0.8125, `external_l1_max`=0.7500, `semantic_minimum_maturation_plus_direct_reserve_v1`=0.6250, `strict_f3`=0.7500
- budget 8: `direct_reserve_semantic_frontier_v1`=0.7500, `direct_reserve_semantic_frontier_v2`=0.8750, `external_l1_max`=0.6250, `semantic_minimum_maturation_plus_direct_reserve_v1`=0.5625, `strict_f3`=0.5625

- `direct_reserve_semantic_frontier_v1` vs `strict_f3` (unique-aware delta): **+0.0694**
- `direct_reserve_semantic_frontier_v1` vs `external_l1_max` (unique-aware delta): **-0.0642**

## D. Paired comparison analysis

- direct_reserve_semantic_frontier_v1 vs strict_f3: matched pairs=48, mean delta=+0.0000, wins/losses/ties=8/8/32; unique-aware mean delta=+0.0000 on 16 examples
  - budget 4: n=16, mean delta=+0.1250
  - budget 6: n=16, mean delta=-0.3125
  - budget 8: n=16, mean delta=+0.1875
- direct_reserve_semantic_frontier_v1 vs external_l1_max: matched pairs=48, mean delta=-0.0833, wins/losses/ties=6/10/32; unique-aware mean delta=-0.0833 on 16 examples
  - budget 4: n=16, mean delta=-0.0625
  - budget 6: n=16, mean delta=-0.3125
  - budget 8: n=16, mean delta=+0.1250
- semantic_minimum_maturation_plus_direct_reserve_v1 vs strict_f3: matched pairs=48, mean delta=+0.0000, wins/losses/ties=10/10/28; unique-aware mean delta=-0.0000 on 16 examples
  - budget 4: n=16, mean delta=+0.1250
  - budget 6: n=16, mean delta=-0.1250
  - budget 8: n=16, mean delta=+0.0000
- semantic_minimum_maturation_plus_direct_reserve_v1 vs external_l1_max: matched pairs=48, mean delta=-0.0833, wins/losses/ties=7/11/30; unique-aware mean delta=-0.0833 on 16 examples
  - budget 4: n=16, mean delta=-0.0625
  - budget 6: n=16, mean delta=-0.1250
  - budget 8: n=16, mean delta=-0.0625

## E. Rescue analysis

- `direct_reserve_rescue`: 0
- `both_rescue`: 0
- `semantic_plus_direct_reserve_rescue`: 0
- `strict_f3_regression`: 0
- `external_only_still_unsolved`: 0
- `all_wrong`: 0
- `all_correct`: 0
- Interpretation: rescue gains are mostly from direct-reserve variants changing final commit outcomes; no confirmed absent-from-tree-to-present rescue events were logged.
- `absent_from_tree_rescue_audit.csv` flagged rescue rows: **0**

## F. Failure taxonomy

- `unknown_unclassified`: 330
- `not_applicable_or_correct`: 43
- `bad_seeding_absent_answer_group`: 38
- `trace_sparse_or_truncated`: 30
- `correct_answer_group_present_but_underweighted`: 9
- `unknown_unclassified` dominates; `bad_seeding_absent_answer_group` remains a meaningful secondary contributor.
- Still not observable from this offline table: exact branch-level causal chains without deeper trace annotation.

## G. Cost/action tradeoff

- `direct_reserve_semantic_frontier_v1` improves all-slot and unique-aware accuracy vs `strict_f3`, but uses more actions (4.60 vs 2.86).
- vs `external_l1_max`, direct reserve is accuracy-competitive/slightly higher in this run but far costlier in actions (4.60 vs 1.01); not Pareto-better.
- Conclusion: direct reserve appears promising diagnostically, but needs action/cost reduction to become deployment-competitive.

## H. Final interpretation

- `strict_f3` is not competitive with `external_l1_max` on this Cohere diagnostic sample.
- `direct_reserve_semantic_frontier_v1` is the strongest internal diagnostic method in this run.
- Claim that direct reserve clearly beats `external_l1_max` should remain cautious due to only 16 unique examples and duplicated slots.
- Semantic maturation alone (without stronger reserve/selection controls) does not clearly dominate external baseline.
- Manuscript change recommendation: **no** (diagnostic evidence only).
- Most justified next algorithmic direction: **direct_reserve_semantic_frontier_v2** with lower action cost and stronger commit-time reranker/verifier.
