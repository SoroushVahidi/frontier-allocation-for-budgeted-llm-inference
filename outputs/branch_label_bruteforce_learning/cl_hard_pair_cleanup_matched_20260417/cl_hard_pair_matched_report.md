# CL hard-pair cleanup matched comparison

- targets_root: `outputs/branch_label_bruteforce_targets/cl_hard_pair_cleanup_20260417`
- seeds: `[11, 29, 47]`
- anchor_model: `pairwise`

## all_pairs_baseline
- pairwise_accuracy_test: `0.6572`
- ranking_top1_accuracy_test: `0.6517`
- near_tie_pairwise_accuracy_test: `0.1667`
- adjacent_rank_pairwise_accuracy_test: `0.6534`
- exact_promoted_pairwise_accuracy_test: `0.0000`
- exact_promoted_hard_region_pairwise_accuracy_test: `0.0000`
- pairwise_margin_brier_test: `0.2170`

## cl_hardpair_excluded
- pairwise_accuracy_test: `0.8353`
- ranking_top1_accuracy_test: `0.7333`
- near_tie_pairwise_accuracy_test: `0.1667`
- adjacent_rank_pairwise_accuracy_test: `0.7940`
- exact_promoted_pairwise_accuracy_test: `0.0000`
- exact_promoted_hard_region_pairwise_accuracy_test: `0.0000`
- pairwise_margin_brier_test: `0.1433`

## Delta (clean - baseline)
- pairwise_accuracy_test: `+0.1781`
- ranking_top1_accuracy_test: `+0.0816`
- near_tie_pairwise_accuracy_test: `+0.0000`
- adjacent_rank_pairwise_accuracy_test: `+0.1405`
- exact_promoted_pairwise_accuracy_test: `+0.0000`
- exact_promoted_hard_region_pairwise_accuracy_test: `+0.0000`
- pairwise_margin_brier_test: `-0.0737`

