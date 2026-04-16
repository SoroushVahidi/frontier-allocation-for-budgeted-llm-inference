# Ambiguity calibration and fallback status (2026-04-16)

## Scope

This pass follows the ternary/abstain study and tests whether hard-case reliability improves when we:
1. calibrate pairwise confidence,
2. and strengthen fallback policy behavior for abstained/tie cases.

Conceptual center remains fixed-budget next-step branch allocation with pairwise branch comparison as the primary learned object.

## What was added

### 1) Confidence calibration support (pairwise logistic path)

New matched runner:
- `scripts/run_ambiguity_calibration_and_fallback_experiment.py`

Implemented calibration methods:
- `none` (uncalibrated baseline)
- `temperature` scaling
- `platt` logistic calibration
- `isotonic` regression calibration

Calibration provenance is explicit:
- calibration fit split: `val`
- calibration evaluation split: `test`
- per-method fit/eval metrics stored in output JSON manifests.

### 2) Fallback policy expansion

Implemented explicit fallback policies for abstained/tie decisions:
- `pointwise_value` (existing baseline)
- `pairwise_binary_backup`
- `heuristic_score` (candidate branch score comparison)
- `outside_option_aware` (outside-option model-aware gating, then pointwise fallback)

Also included:
- ternary tie-aware path with configurable improved fallback.

### 3) Additional diagnostics

Added:
- Brier/ECE/NLL calibration metrics (pre/post by method)
- accepted-accuracy vs confidence-threshold curves
- per-budget and per-dataset forced-accuracy slices in per-variant outputs

## Commands executed

```bash
python -m py_compile scripts/run_ambiguity_calibration_and_fallback_experiment.py

python scripts/run_ambiguity_calibration_and_fallback_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/ternary_exact_augmented_regimes_20260416 \
  --run-id ambiguity_calibration_fallback_20260416 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --near-tie-margin 0.03 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --abstain-confidence-threshold 0.20 \
  --calibration-methods none,temperature,platt,isotonic \
  --primary-calibration temperature \
  --ternary-fallback-policy outside_option_aware
```

## Matched results (3-seed means, feature set fixed at v2)

In this bounded run, metrics were identical across the two regimes used (`all_pairs_approx`, `promoted_exact_hard_region`).

### A) Calibration quality (pairwise probability quality)

Test calibration metrics (lower is better):
- `none`: Brier **0.2420**, ECE **0.2608**
- `temperature`: Brier **0.2989**, ECE **0.3226**
- `platt`: Brier **0.2447**, ECE **0.2770**
- `isotonic`: Brier **0.2725**, ECE **0.2972**

Interpretation: in this run, confidence calibration quality did **not** improve under tested calibrators vs uncalibrated logistic confidence on Brier/ECE.

### B) Accepted-accuracy vs threshold snapshot (`threshold=0.20`)

- `none`: coverage **0.6136**, accepted accuracy **0.5659**
- `temperature`: coverage **0.7670**, accepted accuracy **0.5825**
- `platt`: coverage **0.5833**, accepted accuracy **0.5500**
- `isotonic`: coverage **0.6742**, accepted accuracy **0.5833**

Interpretation: although Brier/ECE worsened for temperature/isotonic here, abstention operating behavior at the selected threshold improved accepted-accuracy/coverage tradeoff for temperature and isotonic.

### C) Formulation/fallback comparison (`abstain-confidence-threshold=0.20`)

- `binary_forced_baseline`:
  - accepted 0.5606, coverage 1.0000, forced 0.5606, near-tie forced 0.1667, adjacent forced 0.5629, top1 0.5984
- `abstain_uncalibrated_pointwise`:
  - accepted 0.5659, coverage 0.6136, forced 0.5114, near-tie forced 0.1667, adjacent forced 0.5205, top1 0.5508
- `abstain_calibrated_pointwise` (temperature):
  - accepted 0.5825, coverage 0.7670, forced 0.5208, near-tie forced 0.1667, adjacent forced 0.5319, top1 0.5984
- `abstain_calibrated_pairwise_backup` (temperature + binary fallback):
  - accepted 0.5825, coverage 0.7670, forced 0.5606, near-tie forced 0.1667, adjacent forced 0.5629, top1 0.5984
- `abstain_calibrated_heuristic_score` (temperature + heuristic fallback):
  - accepted 0.5825, coverage 0.7670, forced 0.4754, near-tie forced 0.1667, adjacent forced 0.4927, top1 0.5429
- `abstain_calibrated_outside_option` (temperature + outside-option-aware fallback):
  - accepted 0.5825, coverage 0.7670, forced 0.5000, near-tie forced 0.1667, adjacent forced 0.5063, top1 0.5984
- `ternary_tie_aware_improved_fallback` (outside-option-aware fallback):
  - accepted 0.3333, coverage 0.0152, forced 0.4034, near-tie forced 0.5000, adjacent forced 0.3984, top1 0.3754

## Main question answers (bounded evidence)

1. **Did confidence calibration materially help?**
   - Mixed. Probability-calibration metrics (Brier/ECE) did not improve with tested calibrators.
   - But abstention operating behavior improved for selected calibrated variants (higher accepted accuracy with higher coverage at threshold 0.20 for temperature/isotonic).

2. **Which fallback policy worked best?**
   - For preserving forced/top1 behavior, `pairwise_binary_backup` was strongest in this run.
   - `pointwise_value` remained competitive but weaker than binary-backup on forced accuracy.
   - `heuristic_score` and `outside_option_aware` were weaker on forced pair accuracy in this bounded setting.

3. **Did abstention become practically useful after calibration/fallback improvements?**
   - Partly yes: calibrated abstention (temperature) + binary backup gave better accepted accuracy (0.5825) at substantially higher coverage (0.7670) than the previous uncalibrated abstention baseline (0.5659 at 0.6136).
   - However, near-tie forced behavior did not improve.

4. **What is the main remaining bottleneck now?**
   - Evidence is consistent with a remaining bottleneck in hard-case ambiguity handling and fallback design/calibration together.
   - Near-tie behavior remains stubborn; this pass does not support a solved claim.

## Artifacts

- Matched ambiguity calibration/fallback run:
  - `outputs/branch_label_bruteforce_learning/ambiguity_calibration_fallback_20260416/`
  - `ambiguity_calibration_fallback_results.json`
  - `ambiguity_calibration_fallback_summary.json`
  - `ambiguity_calibration_fallback_report.md`
