# Binary vs ternary vs selective-abstention branch comparison

- targets_root: `outputs/branch_label_bruteforce_targets/incomparability_exact_augmented_regimes_20260417`
- regimes: `['all_pairs_approx', 'promoted_exact_hard_region', 'soft_prob_promoted_exact_hard_region', 'partial_order_promoted_exact_hard_region']`
- seeds: `[11, 29, 47]`
- feature_set: `v2`
- fallback_policy: `pointwise_value`
- abstain_confidence_threshold: `0.2`

## Regime `all_pairs_approx`
- binary_forced: accepted_acc=0.8419, coverage=1.0000, forced_acc=0.8419, tie_f1=0.0000, near_tie_forced=0.5000, adjacent_forced=0.8000, top1=0.7262
- ternary_tie: accepted_acc=0.7917, coverage=0.6357, forced_acc=0.6891, tie_f1=0.4286, near_tie_forced=0.3333, adjacent_forced=0.6524, top1=0.5992
- soft_ternary_tie: accepted_acc=0.7917, coverage=0.6357, forced_acc=0.6891, tie_f1=0.4286, near_tie_forced=0.3333, adjacent_forced=0.6524, top1=0.5992
- selective_abstain: accepted_acc=0.8333, coverage=0.8259, forced_acc=0.8120, tie_f1=0.3333, near_tie_forced=0.1667, adjacent_forced=0.7667, top1=0.6905
- partial_order_incomparable: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000

## Regime `partial_order_promoted_exact_hard_region`
- binary_forced: accepted_acc=0.8419, coverage=1.0000, forced_acc=0.8419, tie_f1=0.0000, near_tie_forced=0.5000, adjacent_forced=0.8000, top1=0.7262
- ternary_tie: accepted_acc=0.7917, coverage=0.6357, forced_acc=0.6891, tie_f1=0.4286, near_tie_forced=0.3333, adjacent_forced=0.6524, top1=0.5992
- soft_ternary_tie: accepted_acc=0.7917, coverage=0.6357, forced_acc=0.6891, tie_f1=0.4286, near_tie_forced=0.3333, adjacent_forced=0.6524, top1=0.5992
- selective_abstain: accepted_acc=0.8333, coverage=0.8259, forced_acc=0.8120, tie_f1=0.3333, near_tie_forced=0.1667, adjacent_forced=0.7667, top1=0.6905
- partial_order_incomparable: accepted_acc=0.8120, coverage=1.0000, forced_acc=0.8120, tie_f1=0.0000, near_tie_forced=0.3333, adjacent_forced=0.7667, top1=0.7381

## Regime `promoted_exact_hard_region`
- binary_forced: accepted_acc=0.8419, coverage=1.0000, forced_acc=0.8419, tie_f1=0.0000, near_tie_forced=0.5000, adjacent_forced=0.8000, top1=0.7262
- ternary_tie: accepted_acc=0.7917, coverage=0.6357, forced_acc=0.6891, tie_f1=0.4286, near_tie_forced=0.3333, adjacent_forced=0.6524, top1=0.5992
- soft_ternary_tie: accepted_acc=0.7917, coverage=0.6357, forced_acc=0.6891, tie_f1=0.4286, near_tie_forced=0.3333, adjacent_forced=0.6524, top1=0.5992
- selective_abstain: accepted_acc=0.8333, coverage=0.8259, forced_acc=0.8120, tie_f1=0.3333, near_tie_forced=0.1667, adjacent_forced=0.7667, top1=0.6905
- partial_order_incomparable: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000

## Regime `soft_prob_promoted_exact_hard_region`
- binary_forced: accepted_acc=0.8419, coverage=1.0000, forced_acc=0.8419, tie_f1=0.0000, near_tie_forced=0.5000, adjacent_forced=0.8000, top1=0.7262
- ternary_tie: accepted_acc=0.7917, coverage=0.6357, forced_acc=0.6891, tie_f1=0.4286, near_tie_forced=0.3333, adjacent_forced=0.6524, top1=0.5992
- soft_ternary_tie: accepted_acc=0.7185, coverage=0.8419, forced_acc=0.7051, tie_f1=0.2222, near_tie_forced=0.3333, adjacent_forced=0.7000, top1=0.6071
- selective_abstain: accepted_acc=0.8333, coverage=0.8259, forced_acc=0.8120, tie_f1=0.3333, near_tie_forced=0.1667, adjacent_forced=0.7667, top1=0.6905
- partial_order_incomparable: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.0000, tie_f1=0.0000, near_tie_forced=0.0000, adjacent_forced=0.0000, top1=0.0000

