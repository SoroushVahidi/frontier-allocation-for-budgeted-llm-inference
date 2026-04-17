# Strict-coupled tie-aware post-hoc deferral status (2026-04-17)

## Scope

Bounded pass that keeps the strict-coupled controller philosophy and pairwise `v2` default path, but treats hard low-margin cases as an explicit post-hoc deferral region instead of purely forced binary routing analysis.

## Implementation summary

Primary file changed:

- `scripts/run_near_tie_pointwise_expert_experiment.py`

Added one explicit controller variant:

- `strict_coupled_tie_aware_posthoc_deferral_v1`

Variant behavior:

1. default decision path remains pairwise comparator,
2. post-hoc deferral gate identifies tie/unresolved cases from existing signals,
3. deferred subset is routed to specialized near-tie pointwise expert,
4. non-deferred subset remains pairwise,
5. unresolved accounting is explicit (`decision_fn` can abstain on deferred rows while `forced_fn` routes them).

## Post-hoc deferral signals

The deferral gate reuses existing signals:

- `margin_abs`,
- `relative_margin`,
- `pair_std`,
- calibrated confidence,
- supervised near-tie flag,
- rank-gap,
- frontier dispersion (`frontier_score_std_mean` / `frontier_entropy_mean`),
- optional requirement that strict-coupled gate is active.

## New accounting metrics

Per-variant outputs now include:

- `deferred_rate`,
- `deferred_test_pairs`,
- `deferred_non_near_tie_count`,
- `deferred_subset_forced_accuracy`,
- plus existing strict-routed diagnostics.

## Commands run

```bash
python -m py_compile scripts/run_near_tie_pointwise_expert_experiment.py

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_compare_bundle_exact_augmented_regimes_20260417 \
  --run-id near_tie_pointwise_expert_tie_aware_posthoc_deferral_20260417 \
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
  --posthoc-deferral-abs-margin-max 0.03 \
  --posthoc-deferral-relative-margin-max 0.15 \
  --posthoc-deferral-std-min 0.08 \
  --posthoc-deferral-confidence-max 0.30 \
  --posthoc-deferral-rank-gap-max 1.25 \
  --posthoc-deferral-frontier-std-min 0.09 \
  --posthoc-deferral-frontier-entropy-min 0.70 \
  --posthoc-deferral-min-signals 4 \
  --posthoc-deferral-require-strict-gate
```

## Matched comparison summary (3-seed mean across 2 regimes)

Required rows:

- **binary forced baseline**
  - forced: 0.4665
  - top-1: 0.5345
  - near-tie forced: 0.0833
  - adjacent forced: 0.4630
- **calibrated abstain + pairwise backup**
  - forced: 0.4665
  - top-1: 0.5345
  - near-tie forced: 0.0833
  - adjacent forced: 0.4630
- **prior strict-coupled specialized pointwise** (`strict_coupled_near_tie_specialized_pointwise_v1`)
  - forced: 0.5309
  - top-1: 0.6077
  - near-tie forced: 0.5000
  - adjacent forced: 0.5423
- **new tie-aware post-hoc deferral** (`strict_coupled_tie_aware_posthoc_deferral_v1`)
  - forced: 0.5309
  - top-1: 0.6077
  - near-tie forced: 0.5000
  - adjacent forced: 0.5423
  - deferred rate: 0.3040
  - deferred non-near-tie count: 3.667
  - deferred-subset forced accuracy: 0.5556

Additional tie/unresolved accounting:

- strict-coupled specialized accepted accuracy / coverage: 0.5309 / 1.0000
- tie-aware post-hoc deferral accepted accuracy / coverage: 0.5452 / 0.6960

## Conservative interpretation

- Tie-aware post-hoc deferral produced explicit unresolved/deferred accounting without loosening the strict-coupled gate philosophy.
- Forced/top-1/hard-slice metrics were preserved relative to prior strict-coupled specialized baseline in this bounded run.
- Deferred subset quality is measurable (`deferred_subset_forced_accuracy`), enabling cleaner reporting of hard-case handling than pure forced-binary accounting.
- This is not evidence of universal gain; it is a bounded improvement in controller accounting structure with preserved forced behavior.

## Artifacts

- `outputs/branch_label_bruteforce_learning/near_tie_pointwise_expert_tie_aware_posthoc_deferral_20260417/`
  - `near_tie_pointwise_expert_summary.json`
  - `near_tie_pointwise_expert_results.json`
  - `near_tie_pointwise_expert_report.md`
