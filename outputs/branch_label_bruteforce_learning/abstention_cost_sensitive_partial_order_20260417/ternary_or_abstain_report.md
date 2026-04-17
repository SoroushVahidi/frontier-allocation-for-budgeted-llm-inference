# Binary vs ternary vs selective-abstention branch comparison

- targets_root: `outputs/branch_label_bruteforce_targets/abstain_cost_target_regimes_20260417`
- regimes: `['all_pairs', 'davidson_tie_aware', 'soft_prob_tie_aware', 'partial_order_incomparable']`
- seeds: `[11, 29, 47]`
- feature_set: `v2`
- fallback_policy: `pointwise_value`
- abstain_confidence_threshold: `0.2`
- abstention_unresolved_class_upweight: `1.35`

## Regime `all_pairs`
- binary_forced: accepted_acc=0.6313, coverage=1.0000, forced_acc=0.6313, tie_f1=0.0000, near_tie_forced=0.3333, adjacent_forced=0.6411, top1=0.5714
- ternary_tie: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.6053, tie_f1=1.0000, near_tie_forced=0.3333, adjacent_forced=0.5906, top1=0.5179
- soft_ternary_tie: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.6053, tie_f1=1.0000, near_tie_forced=0.3333, adjacent_forced=0.5906, top1=0.5179
- selective_abstain: accepted_acc=0.9524, coverage=0.4293, forced_acc=0.6724, tie_f1=0.7242, near_tie_forced=0.3333, adjacent_forced=0.6343, top1=0.6131
- partial_order_incomparable: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000
- partial_order_cost_sensitive_abstain: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000

## Regime `davidson_tie_aware`
- binary_forced: accepted_acc=0.6313, coverage=1.0000, forced_acc=0.6313, tie_f1=0.0000, near_tie_forced=0.3333, adjacent_forced=0.6411, top1=0.5714
- ternary_tie: accepted_acc=0.9048, coverage=0.4545, forced_acc=0.5880, tie_f1=0.5940, near_tie_forced=0.3333, adjacent_forced=0.5603, top1=0.5179
- soft_ternary_tie: accepted_acc=0.9048, coverage=0.4545, forced_acc=0.5880, tie_f1=0.5940, near_tie_forced=0.3333, adjacent_forced=0.5603, top1=0.5179
- selective_abstain: accepted_acc=0.9524, coverage=0.4293, forced_acc=0.6724, tie_f1=0.6746, near_tie_forced=0.3333, adjacent_forced=0.6343, top1=0.6131
- partial_order_incomparable: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000
- partial_order_cost_sensitive_abstain: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000

## Regime `partial_order_incomparable`
- binary_forced: accepted_acc=0.6313, coverage=1.0000, forced_acc=0.6313, tie_f1=0.0000, near_tie_forced=0.3333, adjacent_forced=0.6411, top1=0.5714
- ternary_tie: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.6053, tie_f1=1.0000, near_tie_forced=0.3333, adjacent_forced=0.5906, top1=0.5179
- soft_ternary_tie: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.6053, tie_f1=1.0000, near_tie_forced=0.3333, adjacent_forced=0.5906, top1=0.5179
- selective_abstain: accepted_acc=0.9524, coverage=0.4293, forced_acc=0.6724, tie_f1=0.7242, near_tie_forced=0.3333, adjacent_forced=0.6343, top1=0.6131
- partial_order_incomparable: accepted_acc=0.6854, coverage=1.0000, forced_acc=0.6854, tie_f1=0.0000, near_tie_forced=0.3333, adjacent_forced=0.7084, top1=0.6190
- partial_order_cost_sensitive_abstain: accepted_acc=0.8889, coverage=0.2128, forced_acc=0.5815, tie_f1=0.1333, near_tie_forced=0.3333, adjacent_forced=0.5603, top1=0.5179

## Regime `soft_prob_tie_aware`
- binary_forced: accepted_acc=0.6313, coverage=1.0000, forced_acc=0.6313, tie_f1=0.0000, near_tie_forced=0.3333, adjacent_forced=0.6411, top1=0.5714
- ternary_tie: accepted_acc=0.9048, coverage=0.4545, forced_acc=0.5880, tie_f1=0.5940, near_tie_forced=0.3333, adjacent_forced=0.5603, top1=0.5179
- soft_ternary_tie: accepted_acc=0.6852, coverage=0.6183, forced_acc=0.5390, tie_f1=0.4485, near_tie_forced=0.3333, adjacent_forced=0.5306, top1=0.4405
- selective_abstain: accepted_acc=0.9524, coverage=0.4293, forced_acc=0.6724, tie_f1=0.6746, near_tie_forced=0.3333, adjacent_forced=0.6343, top1=0.6131
- partial_order_incomparable: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000
- partial_order_cost_sensitive_abstain: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000

