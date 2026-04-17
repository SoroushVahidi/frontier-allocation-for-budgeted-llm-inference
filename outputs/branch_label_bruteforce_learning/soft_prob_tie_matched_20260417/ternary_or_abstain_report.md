# Binary vs ternary vs selective-abstention branch comparison

- targets_root: `outputs/branch_label_bruteforce_targets/soft_prob_tie_target_regimes_20260417`
- regimes: `['all_pairs', 'davidson_tie_aware', 'soft_prob_tie_aware']`
- seeds: `[11, 29, 47]`
- feature_set: `v2`
- fallback_policy: `pointwise_value`
- abstain_confidence_threshold: `0.2`

## Regime `all_pairs`
- binary_forced: accepted_acc=0.7817, coverage=1.0000, forced_acc=0.7817, tie_f1=0.0000, near_tie_forced=0.9167, adjacent_forced=0.8265, top1=0.8259
- ternary_tie: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.7305, tie_f1=1.0000, near_tie_forced=0.8333, adjacent_forced=0.7197, top1=0.6926
- soft_ternary_tie: accepted_acc=0.0000, coverage=0.0000, forced_acc=0.7305, tie_f1=1.0000, near_tie_forced=0.8333, adjacent_forced=0.7197, top1=0.6926
- selective_abstain: accepted_acc=0.8381, coverage=0.4965, forced_acc=0.8084, tie_f1=0.6032, near_tie_forced=0.9167, adjacent_forced=0.7752, top1=0.7593

## Regime `davidson_tie_aware`
- binary_forced: accepted_acc=0.7817, coverage=1.0000, forced_acc=0.7817, tie_f1=0.0000, near_tie_forced=0.9167, adjacent_forced=0.8265, top1=0.8259
- ternary_tie: accepted_acc=0.8333, coverage=0.2825, forced_acc=0.7703, tie_f1=0.4405, near_tie_forced=0.9167, adjacent_forced=0.7274, top1=0.6963
- soft_ternary_tie: accepted_acc=0.9048, coverage=0.4532, forced_acc=0.8387, tie_f1=0.4138, near_tie_forced=0.9167, adjacent_forced=0.8085, top1=0.7963
- selective_abstain: accepted_acc=0.8381, coverage=0.4965, forced_acc=0.8084, tie_f1=0.4471, near_tie_forced=0.9167, adjacent_forced=0.7752, top1=0.7593

## Regime `soft_prob_tie_aware`
- binary_forced: accepted_acc=0.7817, coverage=1.0000, forced_acc=0.7817, tie_f1=0.0000, near_tie_forced=0.9167, adjacent_forced=0.8265, top1=0.8259
- ternary_tie: accepted_acc=0.8333, coverage=0.2825, forced_acc=0.7703, tie_f1=0.4405, near_tie_forced=0.9167, adjacent_forced=0.7274, top1=0.6963
- soft_ternary_tie: accepted_acc=0.9524, coverage=0.4532, forced_acc=0.7608, tie_f1=0.4434, near_tie_forced=0.9167, adjacent_forced=0.7197, top1=0.6926
- selective_abstain: accepted_acc=0.8381, coverage=0.4965, forced_acc=0.8084, tie_f1=0.4471, near_tie_forced=0.9167, adjacent_forced=0.7752, top1=0.7593

