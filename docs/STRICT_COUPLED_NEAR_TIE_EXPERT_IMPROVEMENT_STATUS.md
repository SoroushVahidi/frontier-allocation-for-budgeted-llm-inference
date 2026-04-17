# Strict-coupled near-tie expert-improvement status (2026-04-17)

## Scope

This bounded pass keeps the strict-coupled controller scaffold fixed and targets only expert quality for routed hard cases:

- pairwise (`v2`) remains default,
- strict-coupled gate remains unchanged routing mechanism,
- only the specialized near-tie pointwise expert training regime is modified.

## Expert-improvement design (single bounded change)

Implemented one concrete expert-improvement variant:

- **`strict_coupled_near_tie_specialized_pointwise_improved_v1`**

Design details:

1. Keep specialized pointwise training anchored to near-tie states (`state_near_tie_train`).
2. Add bounded sample reweighting inside that specialized expert:
   - extra weight for strict-hard near-tie states,
   - extra weight for adjacent-rank states,
   - uncertainty-aware **downweighting** by candidate `allocation_value_std` (to emphasize more reliable routed hard cases).
3. Keep strict-coupled gate unchanged; no routing loosening.

## Code changes

- `scripts/run_near_tie_pointwise_expert_experiment.py`
  - Added improved-expert hyperparameters.
  - Added improved specialized model training path (`strict_hard_improved_specialized`).
  - Added new strict-coupled variant using the improved specialized scorer.
  - Added routed-case metrics per variant:
    - `strict_routed_forced_accuracy`
    - `strict_routed_near_tie_forced_accuracy`
  - Added these routed metrics to the generated markdown report summary.

## Commands run

```bash
python -m py_compile scripts/run_near_tie_pointwise_expert_experiment.py

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_strict_coupled_exact_augmented_regimes_20260417b \
  --run-id near_tie_pointwise_expert_strict_coupled_improved_expert_20260417 \
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
  --near-tie-detector-abs-margin 0.03 \
  --near-tie-detector-relative-margin 0.15 \
  --near-tie-detector-std 0.08 \
  --near-tie-detector-confidence-max 0.30 \
  --near-tie-detector-use-near-tie-flag \
  --near-tie-detector-min-signals 2 \
  --detector-threshold-mode strict \
  --controller-policy all \
  --pointwise-margin-min 0.03 \
  --pointwise-fallback-if-uncertain pairwise_binary \
  --near-tie-specialized-margin-max 0.08 \
  --near-tie-specialized-min-states 6 \
  --near-tie-reweight-factor 2.5 \
  --adjacent-reweight-factor 1.5 \
  --strict-coupled-rank-gap-max 1.25 \
  --strict-coupled-frontier-std-min 0.09 \
  --strict-coupled-frontier-entropy-min 0.70 \
  --strict-coupled-min-signals 4 \
  --improved-specialized-min-states 6 \
  --improved-near-tie-reweight-factor 2.0 \
  --improved-adjacent-reweight-factor 1.75 \
  --improved-uncertainty-weight-scale 1.5 \
  --improved-uncertainty-weight-cap 3.0
```

## Matched results (3-seed mean across 2 regimes)

Required comparison set:

- **binary forced baseline**
  - forced: 0.4665, top-1: 0.5345, near-tie forced: 0.0833, adjacent forced: 0.4630
- **calibrated abstain + pairwise backup**
  - forced: 0.4665, top-1: 0.5345, near-tie forced: 0.0833, adjacent forced: 0.4630
- **prior dedicated near-tie specialized pointwise** (`near_tie_specialized_pointwise`)
  - forced: 0.5309, top-1: 0.6077, near-tie forced: 0.5000, adjacent forced: 0.5423
- **strict-coupled baseline** (`strict_coupled_near_tie_specialized_pointwise_v1`)
  - forced: 0.5309, top-1: 0.6077, near-tie forced: 0.5000, adjacent forced: 0.5423
  - strict-routed forced: 0.5556, strict-routed near-tie forced: 0.5000
- **strict-coupled + improved expert** (`strict_coupled_near_tie_specialized_pointwise_improved_v1`)
  - forced: 0.5151, top-1: 0.5857, near-tie forced: 0.2500, adjacent forced: 0.5238
  - strict-routed forced: 0.4722, strict-routed near-tie forced: 0.2500

Routing diagnostics (gate behavior) stayed unchanged:

- legacy detected rate: 0.4605
- strict-coupled routed rate: 0.3040
- legacy non-near-tie routed count (mean): 6.333
- strict non-near-tie routed count (mean): 3.667

## Conservative interpretation

- This bounded expert-training change **did not improve** routed hard-case metrics.
- The improved expert variant underperformed the prior strict-coupled baseline on near-tie, strict-routed, and overall forced/top-1 metrics.
- The strict gate’s reduced-spillover behavior was preserved; degradation is attributable to expert-quality change, not routing expansion.
- Therefore, this pass is a negative result and should not replace the prior strict-coupled specialized baseline.

## Artifacts

- `outputs/branch_label_bruteforce_learning/near_tie_pointwise_expert_strict_coupled_improved_expert_20260417/`
  - `near_tie_pointwise_expert_summary.json`
  - `near_tie_pointwise_expert_results.json`
  - `near_tie_pointwise_expert_report.md`
