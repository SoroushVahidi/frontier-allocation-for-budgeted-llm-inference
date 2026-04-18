# Commands / assumptions / caveats

- Command:
  - `python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce_targets/compute_response_curve_target_20260418/regime_all_pairs --output-dir outputs/branch_label_bruteforce_targets --run-id rank_instability_target_20260418 --pair-strategies all_pairs,multistep_branch_utility_target_k3,discounted_multistep_branch_utility_target_gamma080,compute_response_curve_target_h123,rank_instability_target_v1 --near-tie-margin 0.03 --rank-instability-discount-gamma 0.8 --rank-instability-margin-threshold 0.03 --rank-instability-min-disagreement-count 1`
- Instability definition (bounded, conservative):
  - state unstable when top-1 branch identity disagrees across one-step / multistep-k3 / discounted / curve signals **and** minimum top-1 margin across signals is ≤ 0.03.
  - pair unstable when pairwise orientation disagrees with one-step for at least two alternate signals and pair margin is ≤ 0.03.
- Label semantics:
  - primary pair winner remains multistep-k3 orientation for `rank_instability_target_v1`.
  - instability object is stored explicitly (`rank_instability_state_label/score`, `rank_instability_pair_label/score`, disagreement counts, per-signal top-1 IDs).
- Caveat:
  - this is a bounded first pass using stored proxies (best-followup allocation and derived response-curve scalar), not a full stochastic continuation perturbation simulator.
