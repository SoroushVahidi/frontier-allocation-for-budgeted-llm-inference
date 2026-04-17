# Strict coupled near-tie controller status (2026-04-17)

## Scope

Bounded method-improvement pass for fixed-budget branch allocation focused on near-tie handling coupling:

1. pairwise branch comparison with `v2` features as default,
2. stricter near-tie/ambiguity routing gate,
3. dedicated near-tie specialized pointwise expert for routed hard cases.

This pass intentionally extends the near-tie pointwise-expert line and does **not** revisit binary revise-routing.

## Code changes

Primary implementation file:

- `scripts/run_near_tie_pointwise_expert_experiment.py`

What was added:

- explicit controller policy selector:
  - `--controller-policy {legacy_variants,strict_coupled_v1,all}`
- new stricter coupled controller variant:
  - `strict_coupled_near_tie_specialized_pointwise_v1`
- stricter routing gate using existing + contextual hard-case signals:
  - absolute margin,
  - relative margin,
  - uncertainty/std,
  - calibrated confidence,
  - supervised near-tie flag (optional),
  - rank-gap,
  - frontier dispersion context (std/entropy).
- explicit strict gate diagnostics:
  - routed rate,
  - routed near-tie-flag vs non-near-tie-flag counts,
  - routed adjacent-pair counts.
- matching legacy detector spillover diagnostics for direct comparison.

## Commands run

```bash
python -m py_compile \
  scripts/run_near_tie_pointwise_expert_experiment.py \
  scripts/run_near_tie_policy_experiment.py \
  scripts/run_ambiguity_calibration_and_fallback_experiment.py \
  experiments/bruteforce_branch_allocator.py \
  scripts/train_bruteforce_branch_allocator.py

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id near_tie_strict_coupled_base_20260417b \
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
  --labels-dir outputs/branch_label_bruteforce/near_tie_strict_coupled_base_20260417b \
  --run-id near_tie_strict_coupled_hard_region_mining_20260417b \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.07 \
  --max-candidates 60

python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/near_tie_strict_coupled_base_20260417b \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/near_tie_strict_coupled_hard_region_mining_20260417b/mined_hard_candidates.jsonl \
  --run-id near_tie_strict_coupled_hard_region_exact_expansion_20260417b \
  --max-target-pairs 60

python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/near_tie_strict_coupled_base_20260417b \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/near_tie_strict_coupled_hard_region_exact_expansion_20260417b \
  --run-id near_tie_strict_coupled_exact_augmented_regimes_20260417b \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_strict_coupled_exact_augmented_regimes_20260417b \
  --run-id near_tie_pointwise_expert_strict_coupled_20260417b \
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
  --strict-coupled-min-signals 4
```

## Matched result summary (3-seed mean across 2 regimes)

From `near_tie_pointwise_expert_summary.json`:

- **binary forced baseline**
  - accepted: 0.4665
  - coverage: 1.0000
  - forced: 0.4665
  - top-1: 0.5345
  - near-tie forced: 0.0833
  - adjacent forced: 0.4630

- **calibrated abstain + pairwise backup**
  - accepted: 0.6111
  - coverage: 0.6154
  - forced: 0.4665
  - top-1: 0.5345
  - near-tie forced: 0.0833
  - adjacent forced: 0.4630

- **prior dedicated near-tie specialized pointwise** (`near_tie_specialized_pointwise`)
  - accepted: 0.5309
  - coverage: 1.0000
  - forced: 0.5309
  - top-1: 0.6077
  - near-tie forced: 0.5000
  - adjacent forced: 0.5423

- **new strict coupled controller** (`strict_coupled_near_tie_specialized_pointwise_v1`)
  - accepted: 0.5309
  - coverage: 1.0000
  - forced: 0.5309
  - top-1: 0.6077
  - near-tie forced: 0.5000
  - adjacent forced: 0.5423

Routing diagnostics from `near_tie_pointwise_expert_results.json`:

- legacy detector routed rate: 0.4605
- strict-coupled routed rate: 0.3040
- legacy routed non-near-tie-flag pairs (mean count): 6.333
- strict routed non-near-tie-flag pairs (mean count): 3.667

Interpretation:

- strict coupled gate substantially reduced routing/spillover into non-near-tie-flag pairs,
- hardest-slice and overall metrics were preserved vs the prior near-tie-specialized policy,
- in this bounded run, strict coupling did **not** further improve near-tie forced over the prior best specialized fallback (it preserved it).

## Artifacts

- labels: `outputs/branch_label_bruteforce/near_tie_strict_coupled_base_20260417b/`
- mining: `outputs/branch_label_bruteforce_targets/near_tie_strict_coupled_hard_region_mining_20260417b/`
- exact expansion: `outputs/branch_label_bruteforce_targets/near_tie_strict_coupled_hard_region_exact_expansion_20260417b/`
- regimes: `outputs/branch_label_bruteforce_targets/near_tie_strict_coupled_exact_augmented_regimes_20260417b/`
- matched run: `outputs/branch_label_bruteforce_learning/near_tie_pointwise_expert_strict_coupled_20260417b/`
