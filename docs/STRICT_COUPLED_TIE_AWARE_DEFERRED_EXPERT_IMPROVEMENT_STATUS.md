# Strict-coupled tie-aware deferred-expert improvement status (2026-04-17)

## Scope

Bounded pass keeping the strict-coupled tie-aware post-hoc deferral controller fixed and modifying only specialized expert training on the deferred subset.

## Single improvement implemented

Implemented one concrete expert-regime change:

- `strict_coupled_tie_aware_posthoc_deferral_improved_expert_v1`

Design:

- train a dedicated deferred-specialized pointwise expert using only train states that are deferred by the existing post-hoc deferral gate,
- keep routing/deferral gate unchanged,
- use this deferred-specialized expert only for deferred rows.

This is a stricter expert-training state-selection change (no routing redesign).

## Code changes

File changed:

- `scripts/run_near_tie_pointwise_expert_experiment.py`

Key additions:

- `--deferred-specialized-min-states`
- train-time `state_posthoc_deferred_train` extraction from existing deferral gate
- `deferred_specialized_model` fit path
- variant `strict_coupled_tie_aware_posthoc_deferral_improved_expert_v1`
- `posthoc_deferred_specialized` model provenance in per-seed outputs

## Commands run

```bash
python -m py_compile scripts/run_near_tie_pointwise_expert_experiment.py

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id near_tie_deferred_improvement_base_20260417 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 120 \
  --episodes-per-example 1 \
  --frontier-budget 7 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --init-branches 3 \
  --max-branches-per-state 4 \
  --rollout-samples-per-candidate 16 \
  --max-allocation-samples 32 \
  --seed 23

python scripts/mine_bruteforce_hard_regions.py \
  --labels-dir outputs/branch_label_bruteforce/near_tie_deferred_improvement_base_20260417 \
  --run-id near_tie_deferred_improvement_hard_region_mining_20260417 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.07 \
  --max-candidates 60

python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/near_tie_deferred_improvement_base_20260417 \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/near_tie_deferred_improvement_hard_region_mining_20260417/mined_hard_candidates.jsonl \
  --run-id near_tie_deferred_improvement_hard_region_exact_expansion_20260417 \
  --max-target-pairs 60

python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/near_tie_deferred_improvement_base_20260417 \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/near_tie_deferred_improvement_hard_region_exact_expansion_20260417 \
  --run-id near_tie_deferred_improvement_exact_augmented_regimes_20260417 \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_deferred_improvement_exact_augmented_regimes_20260417 \
  --run-id near_tie_pointwise_expert_tie_aware_deferred_expert_improvement_20260417 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --regimes all_pairs_approx,promoted_exact_hard_region \
  --detector-threshold-mode strict \
  --controller-policy all \
  --posthoc-deferral-abs-margin-max 0.03 \
  --posthoc-deferral-relative-margin-max 0.15 \
  --posthoc-deferral-std-min 0.08 \
  --posthoc-deferral-confidence-max 0.30 \
  --posthoc-deferral-rank-gap-max 1.25 \
  --posthoc-deferral-frontier-std-min 0.09 \
  --posthoc-deferral-frontier-entropy-min 0.70 \
  --posthoc-deferral-min-signals 4 \
  --posthoc-deferral-require-strict-gate \
  --deferred-specialized-min-states 6
```

## Required comparison summary (3-seed means over 2 regimes)

1. **binary forced baseline**
- accepted: 0.4665
- coverage: 1.0000
- forced: 0.4665
- top-1: 0.5345
- near-tie forced: 0.0833
- adjacent forced: 0.4630

2. **calibrated abstain + pairwise backup**
- accepted: 0.6111
- coverage: 0.6154
- forced: 0.4665
- top-1: 0.5345
- near-tie forced: 0.0833
- adjacent forced: 0.4630

3. **prior strict-coupled specialized-pointwise**
- accepted: 0.5309
- coverage: 1.0000
- forced: 0.5309
- top-1: 0.6077
- near-tie forced: 0.5000
- adjacent forced: 0.5423

4. **current tie-aware post-hoc deferral**
- accepted: 0.5452
- coverage: 0.6960
- forced: 0.5309
- top-1: 0.6077
- near-tie forced: 0.5000
- adjacent forced: 0.5423
- deferred rate: 0.3040
- deferred non-near-tie count: 3.6667
- deferred-subset forced accuracy: 0.5556

5. **tie-aware post-hoc deferral + improved deferred expert**
- accepted: 0.5452
- coverage: 0.6960
- forced: 0.4861
- top-1: 0.5345
- near-tie forced: 0.4167
- adjacent forced: 0.5238
- deferred rate: 0.3040
- deferred non-near-tie count: 3.6667
- deferred-subset forced accuracy: 0.4167

## Conservative interpretation

- Routing/deferral behavior stayed fixed (`deferred_rate` and `deferred_non_near_tie_count` unchanged), so this pass did not gain by loosening the scaffold.
- The deferred-specialized training change **did not improve** deferred-subset quality and materially hurt forced/top-1 versus current tie-aware deferral baseline.
- This is a negative result for this bounded expert-improvement option; do not replace the current tie-aware deferral baseline with this improved variant.

## Artifacts

- `outputs/branch_label_bruteforce/near_tie_deferred_improvement_base_20260417/`
- `outputs/branch_label_bruteforce_targets/near_tie_deferred_improvement_hard_region_mining_20260417/`
- `outputs/branch_label_bruteforce_targets/near_tie_deferred_improvement_hard_region_exact_expansion_20260417/`
- `outputs/branch_label_bruteforce_targets/near_tie_deferred_improvement_exact_augmented_regimes_20260417/`
- `outputs/branch_label_bruteforce_learning/near_tie_pointwise_expert_tie_aware_deferred_expert_improvement_20260417/`
