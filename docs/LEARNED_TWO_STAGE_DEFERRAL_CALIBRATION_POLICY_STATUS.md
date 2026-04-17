# Learned two-stage deferral calibration policy status (2026-04-17)

## A) Short implementation plan

1. Keep `strict_coupled_tie_aware_learned_two_stage_deferral_v1` model architecture fixed (same two-stage defer heads and feature set).
2. Add exactly one bounded threshold-selection upgrade for converting stage-2 defer probabilities into accept/defer actions.
3. Run one matched bounded experiment with required comparison rows and report accepted/coverage/forced/top-1/hard-slice/deferred metrics.

## B) Policy added (single policy only)

New policy: **validation-selected defer threshold that maximizes accepted accuracy under a minimum accepted-coverage floor**.

- Stage-1 and stage-2 learned heads are unchanged.
- Only threshold selection changed for the new variant:
  - Existing baseline policy (`v1`) kept for matched comparison: defer-rate-constrained utility threshold.
  - New policy: choose threshold on validation to maximize accepted-set accuracy, subject to accepted coverage `>= floor` (default `0.65`).

## C) Code changes

Primary file changed:
- `scripts/run_near_tie_pointwise_expert_experiment.py`

What changed:
- added reusable threshold-selection helpers;
- preserved legacy learned-two-stage threshold policy;
- added improved coverage-floor accepted-accuracy policy;
- added one new controller variant that uses the improved policy:
  - `strict_coupled_tie_aware_learned_two_stage_deferral_calibrated_threshold_v1`.

## D) Bounded matched run

Commands:

```bash
python -m py_compile scripts/run_near_tie_pointwise_expert_experiment.py

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id two_stage_calib_targets_20260417 \
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
  --labels-dir outputs/branch_label_bruteforce/two_stage_calib_targets_20260417 \
  --run-id two_stage_calib_targets_20260417 \
  --tie-use-near-tie-flag \
  --tie-include-approx

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/two_stage_calib_targets_20260417 \
  --run-id near_tie_two_stage_defer_calib_policy_20260417 \
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

Required matched rows (single bounded run):

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

3. `strict_coupled_tie_aware_learned_two_stage_deferral_v1` (legacy threshold policy)
- accepted accuracy: `0.2727`
- coverage: `0.8462`
- forced accuracy: `0.3846`
- top-1: `0.4286`
- near-tie forced: `0.0000`
- adjacent forced: `0.4000`
- deferred rate: `0.1538`
- deferred non-near-tie count: `2`
- deferred-subset forced accuracy: `1.0000`

4. `strict_coupled_tie_aware_learned_two_stage_deferral_calibrated_threshold_v1` (new policy)
- accepted accuracy: `0.3333`
- coverage: `0.9231`
- forced accuracy: `0.3846`
- top-1: `0.4286`
- near-tie forced: `0.0000`
- adjacent forced: `0.4000`
- deferred rate: `0.0769`
- deferred non-near-tie count: `1`
- deferred-subset forced accuracy: `1.0000`

## E) Conservative interpretation

- The new calibration/threshold policy improved accepted accuracy relative to the **legacy learned-two-stage threshold policy** (`0.3333` vs `0.2727`) while increasing coverage and reducing deferral.
- It did **not** improve forced accuracy or top-1 in this bounded run.
- It did **not** close the gap to the current tie-aware post-hoc controller on accepted accuracy (`0.3333` vs `0.4286`).

So this pass improves learned-two-stage decision policy behavior, but does not yet deliver a headline overall win.

## Artifacts

- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_calib_policy_20260417/near_tie_pointwise_expert_results.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_calib_policy_20260417/near_tie_pointwise_expert_summary.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_calib_policy_20260417/required_matched_rows.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_calib_policy_20260417/required_matched_rows.csv`
