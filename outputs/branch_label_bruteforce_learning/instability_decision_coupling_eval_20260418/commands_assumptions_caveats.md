# Commands / assumptions / caveats

- Command: `scripts/run_instability_decision_coupling_experiment.py --targets-root outputs/branch_label_bruteforce_targets/rank_instability_target_20260418 --run-id instability_decision_coupling_eval_20260418 --output-root outputs/branch_label_bruteforce_learning --seeds 11,29,47 --feature-set v3 --near-tie-margin 0.03 --defer-instability-threshold 0.01 --defer-margin-threshold 0.2 --penalty-weight 1.0 --penalty-state-score-weight 1.0 --penalty-outside-weak-floor 0.12 --penalty-defer-instability-threshold 0.01 --penalty-defer-adjusted-margin-threshold 0.12 --gate-instability-threshold 0.01 --gate-outside-gap-threshold 0.08 --gate-margin-threshold 0.2 --hard-instability-threshold 0.01 --hard-margin-threshold 0.12 --hard-outside-threshold 0.08 --current-instability-threshold 0.01 --current-margin-threshold 0.12`
- This is a bounded decision-policy pass: no new target family and no new simulator labels were introduced.
- New coupling policies are explicit rule-based action layers that consume existing multistep/outside-gap/instability/margin signals.
- Accepted metrics are computed on non-deferred states only; coverage/defer_rate expose selective behavior.
- Diagnostics include fragile overconfident wrong accepts, delayed-payoff overvaluation failures, and easy-state defer spillover.
