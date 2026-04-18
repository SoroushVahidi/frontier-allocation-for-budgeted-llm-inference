# Commands / assumptions / caveats

- Command: `scripts/run_rank_instability_experiment.py --targets-root outputs/branch_label_bruteforce_targets/rank_instability_target_20260418 --run-id rank_instability_eval_20260418 --output-root outputs/branch_label_bruteforce_learning --seeds 11,29,47 --feature-set v3 --near-tie-margin 0.03 --baseline-regime all_pairs --multistep-regime multistep_branch_utility_target_k3 --discounted-regime discounted_multistep_branch_utility_target_gamma080 --curve-regime compute_response_curve_target_h123 --rank-instability-regime rank_instability_target_v1 --instability-threshold 0.35 --decision-margin-threshold 0.10`
- Bounded policy: defer only when predicted top-2 pair instability is high and score gap is small.
- Accepted metrics are computed on non-deferred states only.
- Forced metrics keep a branch decision for every state (deferred states counted via default top-1 score choice).
