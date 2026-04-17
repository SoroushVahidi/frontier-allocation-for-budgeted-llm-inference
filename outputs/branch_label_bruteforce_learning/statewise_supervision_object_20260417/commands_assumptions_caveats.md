# Commands / assumptions / caveats

## Commands run
- python scripts/run_statewise_supervision_object_experiment.py --labels-dir outputs/branch_label_bruteforce_targets/target_semantics_upstream_20260417/regime_all_pairs_approx --run-id statewise_supervision_object_20260417 --output-root outputs/branch_label_bruteforce_learning --seeds 11,29,47 --feature-set v2 --near-tie-margin 0.03

## Assumptions
- Canonical candidate target estimated_value_if_allocate_next is a valid next-branch value proxy.
- Canonical feature set and split assignment from prepare_learning_tables are kept unchanged.

## Caveats
- Statewise models are mapped back to pairwise accepted-accuracy metrics by induced pair predictions from candidate scores.
- No explicit defer head is used in this bounded experiment; coverage=1 and defer_rate=0 by design for compared modes.
