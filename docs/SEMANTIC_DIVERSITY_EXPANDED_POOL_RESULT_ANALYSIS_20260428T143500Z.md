# Semantic diversity expanded-pool result analysis (20260428T143500Z)

## A. Job and data status

- Job completion (Slurm `1011613`): **completed** (exit code 0, from `sacct`).
- Output directory: `outputs/semantic_diversity_controller_diagnostic_20260428T143500Z`
- Issue files present: `cohere_api_key_issue.md=False`, `run_failure_issue.md=False`
- Selected slots (rows): **30**
- Unique example IDs: **16**
- Duplicate/cycle fallback slots: **14**
- Methods included: `direct_reserve_semantic_frontier_v1`, `external_l1_max`, `semantic_minimum_maturation_plus_direct_reserve_v1`, `strict_f3`
- Budgets included: `4`, `6`, `8`
- Total analyzed non-error rows (`per_case_results.csv`): **360**

## B. Accuracy/action summary (all selected slots)

| method | n | accuracy | avg_actions | avg_cost_proxy |
|---|---:|---:|---:|---:|
| direct_reserve_semantic_frontier_v1 | 90 | 0.7444 | 4.64 | 0.000446 |
| external_l1_max | 90 | 0.7222 | 1.04 | 0.000100 |
| semantic_minimum_maturation_plus_direct_reserve_v1 | 90 | 0.7111 | 4.69 | 0.000450 |
| strict_f3 | 90 | 0.4778 | 2.94 | 0.000283 |

## C. Unique-example-only analysis (duplicate-aware)

Per method, accuracy is averaged per `example_id` over available budgets, then averaged across unique examples.

| method | unique_examples | unique-example accuracy |
|---|---:|---:|
| direct_reserve_semantic_frontier_v1 | 16 | 0.7188 |
| external_l1_max | 16 | 0.7170 |
| semantic_minimum_maturation_plus_direct_reserve_v1 | 16 | 0.7083 |
| strict_f3 | 16 | 0.5191 |

Per-budget unique-example accuracy:
- budget 4: `direct_reserve_semantic_frontier_v1`=0.6875, `external_l1_max`=0.7500, `semantic_minimum_maturation_plus_direct_reserve_v1`=0.6250, `strict_f3`=0.5000
- budget 6: `direct_reserve_semantic_frontier_v1`=0.8750, `external_l1_max`=0.6875, `semantic_minimum_maturation_plus_direct_reserve_v1`=0.8125, `strict_f3`=0.4375
- budget 8: `direct_reserve_semantic_frontier_v1`=0.7500, `external_l1_max`=0.6875, `semantic_minimum_maturation_plus_direct_reserve_v1`=0.7500, `strict_f3`=0.6250

- `direct_reserve_semantic_frontier_v1` vs `strict_f3` (unique-aware delta): **+0.1997**
- `direct_reserve_semantic_frontier_v1` vs `external_l1_max` (unique-aware delta): **+0.0017**

## D. Paired comparison analysis

- direct_reserve_semantic_frontier_v1 vs strict_f3: matched pairs=48, mean delta=+0.2500, wins/losses/ties=15/3/30; unique-aware mean delta=+0.2500 on 16 examples
  - budget 4: n=16, mean delta=+0.1875
  - budget 6: n=16, mean delta=+0.4375
  - budget 8: n=16, mean delta=+0.1250
- direct_reserve_semantic_frontier_v1 vs external_l1_max: matched pairs=48, mean delta=+0.0625, wins/losses/ties=7/4/37; unique-aware mean delta=+0.0625 on 16 examples
  - budget 4: n=16, mean delta=-0.0625
  - budget 6: n=16, mean delta=+0.1875
  - budget 8: n=16, mean delta=+0.0625
- semantic_minimum_maturation_plus_direct_reserve_v1 vs strict_f3: matched pairs=48, mean delta=+0.2083, wins/losses/ties=15/5/28; unique-aware mean delta=+0.2083 on 16 examples
  - budget 4: n=16, mean delta=+0.1250
  - budget 6: n=16, mean delta=+0.3750
  - budget 8: n=16, mean delta=+0.1250
- semantic_minimum_maturation_plus_direct_reserve_v1 vs external_l1_max: matched pairs=48, mean delta=+0.0208, wins/losses/ties=9/8/31; unique-aware mean delta=+0.0208 on 16 examples
  - budget 4: n=16, mean delta=-0.1250
  - budget 6: n=16, mean delta=+0.1250
  - budget 8: n=16, mean delta=+0.0625

## E. Rescue analysis

- `direct_reserve_rescue`: 2
- `both_rescue`: 10
- `semantic_plus_direct_reserve_rescue`: 5
- `strict_f3_regression`: 3
- `external_only_still_unsolved`: 2
- `all_wrong`: 4
- `all_correct`: 14
- Interpretation: rescue gains are mostly from direct-reserve variants changing final commit outcomes; no confirmed absent-from-tree-to-present rescue events were logged.
- `absent_from_tree_rescue_audit.csv` flagged rescue rows: **0**

## F. Failure taxonomy

- `unknown_unclassified`: 270
- `not_applicable_or_correct`: 43
- `bad_seeding_absent_answer_group`: 35
- `correct_answer_group_present_but_underweighted`: 11
- `bad_selection_repair`: 1
- `unknown_unclassified` dominates; `bad_seeding_absent_answer_group` remains a meaningful secondary contributor.
- Still not observable from this offline table: exact branch-level causal chains without deeper trace annotation.

## G. Cost/action tradeoff

- `direct_reserve_semantic_frontier_v1` improves all-slot and unique-aware accuracy vs `strict_f3`, but uses more actions (4.64 vs 2.94).
- vs `external_l1_max`, direct reserve is accuracy-competitive/slightly higher in this run but far costlier in actions (4.64 vs 1.04); not Pareto-better.
- Conclusion: direct reserve appears promising diagnostically, but needs action/cost reduction to become deployment-competitive.

## H. Final interpretation

- `strict_f3` is not competitive with `external_l1_max` on this Cohere diagnostic sample.
- `direct_reserve_semantic_frontier_v1` is the strongest internal diagnostic method in this run.
- Claim that direct reserve clearly beats `external_l1_max` should remain cautious due to only 16 unique examples and duplicated slots.
- Semantic maturation alone (without stronger reserve/selection controls) does not clearly dominate external baseline.
- Manuscript change recommendation: **no** (diagnostic evidence only).
- Most justified next algorithmic direction: **direct_reserve_semantic_frontier_v2** with lower action cost and stronger commit-time reranker/verifier.
