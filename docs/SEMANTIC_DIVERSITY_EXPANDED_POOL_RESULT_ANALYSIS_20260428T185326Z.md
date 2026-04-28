# Semantic diversity expanded-pool result analysis (20260428T185326Z)

## A. Job and data status

- Job completion (Slurm `1011613`): **completed** (exit code 0, from `sacct`).
- Output directory: `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z`
- Issue files present: `cohere_api_key_issue.md=False`, `run_failure_issue.md=False`
- Selected slots (rows): **30**
- Unique example IDs: **16**
- Duplicate/cycle fallback slots: **14**
- Methods included: `direct_reserve_semantic_frontier_v2`, `external_l1_exact`, `external_l1_max`, `self_consistency_3`, `strict_f3`, `tot_beam_matched_budget`, `tot_bfs_matched_budget`, `tot_dfs_matched_budget`
- Budgets included: `4`, `6`, `8`
- Total analyzed non-error rows (`per_case_results.csv`): **720**

## B. Accuracy/action summary (all selected slots)

| method | n | accuracy | avg_actions | avg_cost_proxy |
|---|---:|---:|---:|---:|
| direct_reserve_semantic_frontier_v2 | 90 | 0.8000 | 2.33 | 0.000224 |
| external_l1_exact | 90 | 0.7556 | 1.01 | 0.000097 |
| external_l1_max | 90 | 0.6889 | 1.06 | 0.000101 |
| self_consistency_3 | 90 | 0.4889 | 5.46 | 0.000524 |
| strict_f3 | 90 | 0.4556 | 2.87 | 0.000275 |
| tot_beam_matched_budget | 90 | 0.4000 | 1.31 | 0.000126 |
| tot_bfs_matched_budget | 90 | 0.4000 | 1.28 | 0.000123 |
| tot_dfs_matched_budget | 90 | 0.3444 | 1.37 | 0.000131 |

## C. Unique-example-only analysis (duplicate-aware)

Per method, accuracy is averaged per `example_id` over available budgets, then averaged across unique examples.

| method | unique_examples | unique-example accuracy |
|---|---:|---:|
| direct_reserve_semantic_frontier_v2 | 16 | 0.7944 |
| external_l1_exact | 16 | 0.6875 |
| external_l1_max | 16 | 0.6590 |
| self_consistency_3 | 16 | 0.5458 |
| strict_f3 | 16 | 0.5458 |
| tot_beam_matched_budget | 16 | 0.4573 |
| tot_bfs_matched_budget | 16 | 0.5094 |
| tot_dfs_matched_budget | 16 | 0.4260 |

Per-budget unique-example accuracy:
- budget 4: `direct_reserve_semantic_frontier_v2`=0.8125, `external_l1_exact`=0.7500, `external_l1_max`=0.6250, `self_consistency_3`=0.4375, `strict_f3`=0.6250, `tot_beam_matched_budget`=0.5625, `tot_bfs_matched_budget`=0.5000, `tot_dfs_matched_budget`=0.3750
- budget 6: `direct_reserve_semantic_frontier_v2`=0.8750, `external_l1_exact`=0.6875, `external_l1_max`=0.7500, `self_consistency_3`=0.5000, `strict_f3`=0.5000, `tot_beam_matched_budget`=0.3125, `tot_bfs_matched_budget`=0.5000, `tot_dfs_matched_budget`=0.5000
- budget 8: `direct_reserve_semantic_frontier_v2`=0.6875, `external_l1_exact`=0.7500, `external_l1_max`=0.6875, `self_consistency_3`=0.5000, `strict_f3`=0.3750, `tot_beam_matched_budget`=0.4375, `tot_bfs_matched_budget`=0.5000, `tot_dfs_matched_budget`=0.3750

- `direct_reserve_semantic_frontier_v1` vs `strict_f3` (unique-aware delta): **-0.5458**
- `direct_reserve_semantic_frontier_v1` vs `external_l1_max` (unique-aware delta): **-0.6590**

## D. Paired comparison analysis

- direct_reserve_semantic_frontier_v1 vs strict_f3: matched pairs=0, mean delta=+nan, wins/losses/ties=0/0/0; unique-aware mean delta=+nan on 0 examples
  - budget 4: n=0, mean delta=+nan
  - budget 6: n=0, mean delta=+nan
  - budget 8: n=0, mean delta=+nan
- direct_reserve_semantic_frontier_v1 vs external_l1_max: matched pairs=0, mean delta=+nan, wins/losses/ties=0/0/0; unique-aware mean delta=+nan on 0 examples
  - budget 4: n=0, mean delta=+nan
  - budget 6: n=0, mean delta=+nan
  - budget 8: n=0, mean delta=+nan
- semantic_minimum_maturation_plus_direct_reserve_v1 vs strict_f3: matched pairs=0, mean delta=+nan, wins/losses/ties=0/0/0; unique-aware mean delta=+nan on 0 examples
  - budget 4: n=0, mean delta=+nan
  - budget 6: n=0, mean delta=+nan
  - budget 8: n=0, mean delta=+nan
- semantic_minimum_maturation_plus_direct_reserve_v1 vs external_l1_max: matched pairs=0, mean delta=+nan, wins/losses/ties=0/0/0; unique-aware mean delta=+nan on 0 examples
  - budget 4: n=0, mean delta=+nan
  - budget 6: n=0, mean delta=+nan
  - budget 8: n=0, mean delta=+nan

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

- `trace_sparse_or_truncated`: 479
- `unknown_unclassified`: 151
- `not_applicable_or_correct`: 41
- `bad_seeding_absent_answer_group`: 39
- `correct_answer_group_present_but_underweighted`: 10
- `unknown_unclassified` dominates; `bad_seeding_absent_answer_group` remains a meaningful secondary contributor.
- Still not observable from this offline table: exact branch-level causal chains without deeper trace annotation.

## G. Cost/action tradeoff

- `direct_reserve_semantic_frontier_v1` improves all-slot and unique-aware accuracy vs `strict_f3`, but uses more actions (0.00 vs 2.87).
- vs `external_l1_max`, direct reserve is accuracy-competitive/slightly higher in this run but far costlier in actions (0.00 vs 1.06); not Pareto-better.
- Conclusion: direct reserve appears promising diagnostically, but needs action/cost reduction to become deployment-competitive.

## H. Final interpretation

- `strict_f3` is not competitive with `external_l1_max` on this Cohere diagnostic sample.
- `direct_reserve_semantic_frontier_v1` is the strongest internal diagnostic method in this run.
- Claim that direct reserve clearly beats `external_l1_max` should remain cautious due to only 16 unique examples and duplicated slots.
- Semantic maturation alone (without stronger reserve/selection controls) does not clearly dominate external baseline.
- Manuscript change recommendation: **no** (diagnostic evidence only).
- Most justified next algorithmic direction: **direct_reserve_semantic_frontier_v2** with lower action cost and stronger commit-time reranker/verifier.
