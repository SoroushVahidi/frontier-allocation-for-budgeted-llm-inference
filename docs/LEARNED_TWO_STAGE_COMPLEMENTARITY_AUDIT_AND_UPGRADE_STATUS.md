# Learned two-stage complementarity audit + target-upgrade status (2026-04-17)

## A) Short implementation plan

1. Keep the current strict-coupled/tie-aware learned two-stage controller family fixed (pairwise default, `v2` features, specialist fallback, calibrated coverage-floor threshold selection).
2. Add one auditable complementarity analysis over test hard slices to measure pairwise-vs-specialist correctness overlap and true complementarity.
3. Keep architecture fixed, but add one **complementarity-aware stage-2 defer target** using a utility-gap rule with defer-cost and gap margin.
4. Run one bounded matched comparison with required rows and report controller metrics plus complementarity bucket outputs.

## B) Code changes

Primary file changed:
- `scripts/run_near_tie_pointwise_expert_experiment.py`

Implemented in this pass:
- Added a machine-readable complementarity audit that records four correctness buckets:
  - pairwise right / specialist wrong,
  - pairwise wrong / specialist right,
  - both right,
  - both wrong.
- Added required slicing for the audit:
  - near-tie vs non-near-tie,
  - adjacent vs non-adjacent,
  - deferred vs accepted (under current learned calibrated controller),
  - margin bucket and confidence bucket,
  - plus cross-slice combined bucket keys.
- Added one new stage-2 target variant (single new target only):
  - utility-gap defer-positive when `((1[specialist_correct] - defer_cost) - 1[pairwise_correct]) >= utility_gap_margin`.
- Kept threshold policy fixed to the best current calibrated policy (accepted-accuracy with coverage floor), reused for:
  - current learned two-stage calibrated row,
  - new complementarity-aware-target row.
- Added output artifacts:
  - `required_matched_rows.json/.csv`,
  - `complementarity_audit_summary.json/.csv`.

## C) Bounded matched run

Commands:

```bash
python -m py_compile scripts/run_near_tie_pointwise_expert_experiment.py

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id two_stage_complementarity_targets_20260417 \
  --max-frontier-states 50 \
  --dataset-name openai/gsm8k \
  --episodes-per-example 1 \
  --frontier-budget 6 \
  --min-remaining-budget 2 \
  --max-remaining-budget 3 \
  --init-branches 3 \
  --max-branches-per-state 4 \
  --rollout-samples-per-candidate 10 \
  --max-allocation-samples 20 \
  --seed 13

python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/two_stage_complementarity_targets_20260417 \
  --run-id two_stage_complementarity_targets_20260417 \
  --tie-use-near-tie-flag \
  --tie-include-approx

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/two_stage_complementarity_targets_20260417 \
  --run-id near_tie_two_stage_complementarity_audit_upgrade_20260417 \
  --seeds 11 \
  --feature-set v2 \
  --regimes all_pairs \
  --controller-policy all \
  --detector-threshold-mode strict \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --near-tie-detector-use-near-tie-flag \
  --posthoc-deferral-require-strict-gate
```

Required matched rows:

1. `binary_forced_baseline`
- accepted accuracy: `0.3846`
- coverage: `1.0000`
- forced accuracy: `0.3846`
- top-1: `0.4286`
- near-tie forced: `0.0000`
- adjacent forced: `0.4000`
- deferred rate: `0.0000`
- deferred non-near-tie count: `0`
- deferred-subset forced accuracy: `0.0000`

2. `strict_coupled_tie_aware_posthoc_deferral_v1`
- accepted accuracy: `0.4286`
- coverage: `0.5385`
- forced accuracy: `0.3846`
- top-1: `0.4286`
- near-tie forced: `0.0000`
- adjacent forced: `0.4000`
- deferred rate: `0.4615`
- deferred non-near-tie count: `5`
- deferred-subset forced accuracy: `0.3333`

3. `strict_coupled_tie_aware_learned_two_stage_deferral_calibrated_threshold_v1`
- accepted accuracy: `0.3333`
- coverage: `0.9231`
- forced accuracy: `0.3846`
- top-1: `0.4286`
- near-tie forced: `0.0000`
- adjacent forced: `0.4000`
- deferred rate: `0.0769`
- deferred non-near-tie count: `1`
- deferred-subset forced accuracy: `1.0000`

4. `strict_coupled_tie_aware_learned_two_stage_deferral_complementarity_target_v1`
- accepted accuracy: `0.3333`
- coverage: `0.9231`
- forced accuracy: `0.3846`
- top-1: `0.4286`
- near-tie forced: `0.0000`
- adjacent forced: `0.4000`
- deferred rate: `0.0769`
- deferred non-near-tie count: `1`
- deferred-subset forced accuracy: `1.0000`

## D) Complementarity audit result

Audit summary (`all_pairs`, seed 11, test hard-slice aware):
- pairwise right / specialist wrong: `0`
- pairwise wrong / specialist right: `0`
- both right: `5`
- both wrong: `8`
- net specialist complementarity gain count: `0`

Key slices:
- near-tie slice: 1 row, all in `both_wrong`.
- deferred-vs-accepted under current learned calibrated controller:
  - deferred: 1 row, `both_right`.
  - accepted: 12 rows, mostly `both_wrong`.

Interpretation:
- In this bounded run, observed pairwise↔specialist complementarity is effectively absent (no swap-win rows in either direction).
- This supports the hypothesis that the immediate gap is currently more consistent with missing discriminative signal quality (or low-data slice instability) than with defer-target semantics alone.

## E) Success/failure criterion outcome

- Complementarity audit requirement: **met** (machine-readable and sliced).
- Controller-upgrade requirement: **implemented** (single complementarity-aware utility-gap target).
- Improvement criterion: **not met in this bounded run** (new target ties current calibrated learned controller; no accepted/deferred-subset lift).

Conservative next-bottleneck call:
- This pass does not show evidence that defer-target redesign alone closes the gap.
- Given zero observed complementarity counts here, remaining bottleneck looks more like feature/signal informativeness (and/or small-sample hard-slice scarcity) than target-form choice alone.

## Artifacts

- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/near_tie_pointwise_expert_results.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/near_tie_pointwise_expert_summary.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/required_matched_rows.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/required_matched_rows.csv`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/complementarity_audit_summary.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_complementarity_audit_upgrade_20260417/complementarity_audit_summary.csv`
- `outputs/branch_label_bruteforce_targets/two_stage_complementarity_targets_20260417/`
- `outputs/branch_label_bruteforce/two_stage_complementarity_targets_20260417/`
