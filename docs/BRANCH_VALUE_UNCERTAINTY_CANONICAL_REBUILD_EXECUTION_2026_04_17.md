# Branch-value uncertainty canonical rebuild execution (2026-04-17)

## What was missing (exact upstream chain)

To build a strict-replay-usable canonical targets root with
`regime_all_pairs_approx`, `regime_promoted_exact_hard_region`, and `regime_penalized_marginal_defer`, the following upstream artifact chain was required and was missing in the checkout at task start:

1. Base branch-label artifacts (`candidate_labels.jsonl`, `pairwise_labels.jsonl`, `state_summaries.jsonl`) under a `outputs/branch_label_bruteforce/<run_id>/` root.
2. Hard-region mining outputs (`mined_hard_candidates.jsonl`) for targeted exact promotion.
3. Exact hard-region expansion outputs (`exact_pairwise_labels.jsonl`) for promotion.
4. Exact-augmented regime root (providing `regime_all_pairs_approx` + `regime_promoted_exact_hard_region`).
5. Penalized regime root (providing `regime_penalized_marginal_defer`).

## Rebuild path chosen (smallest clean path)

Chosen path used only existing frozen scripts and existing naming conventions:

1. `scripts/run_bruteforce_branch_label_generator.py`
2. `scripts/mine_bruteforce_hard_regions.py`
3. `scripts/expand_bruteforce_exact_hard_regions.py`
4. `scripts/build_exact_augmented_target_regimes.py`
5. `scripts/build_bruteforce_target_regimes.py` (penalized regime only)
6. Assemble a manifest-backed canonical root containing the 3 strict-required regime directories.

This was chosen because it is the minimal script-faithful chain that yields the exact required regime names without method redesign.

## Artifacts rebuilt

- Base labels: `outputs/branch_label_bruteforce/canonical_rebuild_base_labels_20260417`
- Hard-region mining: `outputs/branch_label_bruteforce_targets/canonical_rebuild_hard_region_mining_20260417`
- Exact expansion: `outputs/branch_label_bruteforce_targets/canonical_rebuild_exact_hard_region_expansion_20260417`
- Exact-augmented regimes: `outputs/branch_label_bruteforce_targets/canonical_rebuild_exact_augmented_regimes_20260417`
- Penalized regimes: `outputs/branch_label_bruteforce_targets/canonical_rebuild_penalized_regimes_20260417`

## Canonical targets root created for strict replay

Created manifest-backed canonical root:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_root`

Containing:

- `regime_all_pairs_approx`
- `regime_promoted_exact_hard_region`
- `regime_penalized_marginal_defer`

Manifest:

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_manifest.json`

## Strict validation replay (unchanged harness)

Replayed unchanged:

- `scripts/run_branch_value_uncertainty_strict_validation_pass.py`
- regimes: `all_pairs_approx,promoted_exact_hard_region,penalized_marginal_defer`
- seeds: `11,29,47`
- feature set: `v3`

Run id:

- `branch_value_uncertainty_strict_validation_canonical_rebuild_20260417`

Result:

- Replay succeeded on real rebuilt artifacts with `missing_regimes = []`.
- Full-method aggregate: accuracy `0.9333`, coverage `0.2698`, defer rate `0.7302`.
- Pairwise baseline aggregate: accuracy `0.7937`, coverage `1.0`.

## Repository-recorded outputs for this pass

- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/rebuild_and_replay_summary.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/rebuild_commands_and_caveats.md`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_canonical_regime_rebuild_20260417/canonical_targets_manifest.json`
- `outputs/branch_label_bruteforce_learning/branch_value_uncertainty_strict_validation_canonical_rebuild_20260417/strict_validation_{config,results,summary,manifest}.json`

## Caveat

This pass reconstructs missing artifacts in this checkout using repository generators and frozen settings; it does not claim byte-identical restoration of previously missing local output directories.
