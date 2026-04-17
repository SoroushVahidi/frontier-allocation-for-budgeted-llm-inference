# Target-fidelity matched regime experiment

- targets_root: `outputs/branch_label_bruteforce_targets/dq_target_regimes_quality_only_20260417`
- seeds: `[11, 29, 47]`

## Regime `all_pairs`
- catboost_ranker: pairwise=0.4394, top1=0.3750, near_tie=0.7500, far_margin=0.3983, exact=0.0000
- lightgbm_ranker: pairwise=0.4394, top1=0.3750, near_tie=0.7500, far_margin=0.3983, exact=0.0000
- outside_option: pairwise=0.4928, top1=0.4583, near_tie=0.4167, far_margin=0.4949, exact=0.0000
- pairwise: pairwise=0.5931, top1=0.5278, near_tie=0.1667, far_margin=0.6530, exact=0.0000
- pointwise: pairwise=0.4986, top1=0.4861, near_tie=0.5833, far_margin=0.4570, exact=0.0000

## Regime `quality_mixed_trust`
- catboost_ranker: pairwise=0.4372, top1=0.3750, near_tie=0.5000, far_margin=0.3983, exact=0.0000
- lightgbm_ranker: pairwise=0.4372, top1=0.3750, near_tie=0.5000, far_margin=0.3983, exact=0.0000
- outside_option: pairwise=0.5004, top1=0.4583, near_tie=0.3333, far_margin=0.4949, exact=0.0000
- pairwise: pairwise=0.6141, top1=0.5556, near_tie=0.1667, far_margin=0.6530, exact=0.0000
- pointwise: pairwise=0.4996, top1=0.4861, near_tie=0.5000, far_margin=0.4570, exact=0.0000

