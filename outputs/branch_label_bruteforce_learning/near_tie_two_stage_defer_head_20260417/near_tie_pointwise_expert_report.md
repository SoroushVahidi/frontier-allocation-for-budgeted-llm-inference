# Near-tie pointwise expert matched experiment

- targets_root: `outputs/branch_label_bruteforce_targets/two_stage_defer_targets_20260417`
- regimes: `['all_pairs_approx']`
- seeds: `[11]`
- feature_set: `v2`
- detector_mode: `strict`
- controller_policy: `all`
- active_detector: `{"abs_margin_max": 0.024, "calibrated_confidence_max": 0.24, "min_triggered_signals": 2, "relative_margin_max": 0.12, "uncertainty_std_min": 0.096}`
- strict_coupled_gate: `{"frontier_entropy_min": 0.7, "frontier_score_std_min": 0.09, "min_triggered_signals": 4, "rank_gap_abs_max": 1.25}`
- pointwise_margin_min: `0.03`

## Regime `all_pairs_approx`
- abstain_calibrated_pairwise_backup: accepted=1.0000, coverage=0.0769, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.0000, deferred_non_near=0.00, deferred_subset_acc=0.0000
- binary_forced_baseline: accepted=0.3846, coverage=1.0000, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.0000, deferred_non_near=0.00, deferred_subset_acc=0.0000
- near_tie_generic_pointwise: accepted=0.3846, coverage=1.0000, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.0000, deferred_non_near=0.00, deferred_subset_acc=0.0000
- near_tie_reweighted_pointwise: accepted=0.3846, coverage=1.0000, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.0000, deferred_non_near=0.00, deferred_subset_acc=0.0000
- near_tie_specialized_pointwise: accepted=0.3846, coverage=1.0000, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.0000, deferred_non_near=0.00, deferred_subset_acc=0.0000
- strict_coupled_near_tie_specialized_pointwise_improved_v1: accepted=0.3846, coverage=1.0000, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.0000, deferred_non_near=0.00, deferred_subset_acc=0.0000
- strict_coupled_near_tie_specialized_pointwise_v1: accepted=0.3846, coverage=1.0000, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.0000, deferred_non_near=0.00, deferred_subset_acc=0.0000
- strict_coupled_tie_aware_learned_two_stage_deferral_v1: accepted=0.3000, coverage=0.7692, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.2308, deferred_non_near=3.00, deferred_subset_acc=0.6667
- strict_coupled_tie_aware_posthoc_deferral_improved_expert_v1: accepted=0.3750, coverage=0.6154, forced=0.3077, near=0.0000, adj=0.0000, top1=0.2857, strict_routed=0.2000, strict_routed_near=0.0000, deferred_rate=0.3846, deferred_non_near=5.00, deferred_subset_acc=0.2000
- strict_coupled_tie_aware_posthoc_deferral_reliability_weighted_expert_v1: accepted=0.3750, coverage=0.6154, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.3846, deferred_non_near=5.00, deferred_subset_acc=0.4000
- strict_coupled_tie_aware_posthoc_deferral_v1: accepted=0.3750, coverage=0.6154, forced=0.3846, near=0.0000, adj=0.0000, top1=0.4286, strict_routed=0.4000, strict_routed_near=0.0000, deferred_rate=0.3846, deferred_non_near=5.00, deferred_subset_acc=0.4000

