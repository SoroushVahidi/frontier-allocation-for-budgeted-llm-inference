# Dedicated near-tie policy status (2026-04-16)

## Scope

This pass follows the ambiguity calibration + fallback study and tests a narrower claim:

> The unresolved hardest slice is near-tie forced branch comparison, so should we handle it with a dedicated near-tie detector + routing policy instead of only generic binary/ternary/abstention logic?

Project framing is unchanged:
- fixed-budget next-step branch allocation remains the conceptual center,
- pairwise branch comparison remains the main learned object,
- pointwise and outside-option views are supporting fallback semantics.

## What was added

### 1) Dedicated near-tie detector (configurable + manifest-backed)

New runner:
- `scripts/run_near_tie_policy_experiment.py`

Near-tie detection combines existing supervision/decision signals:
- absolute margin (`margin_abs <= abs_margin_max`),
- relative margin (`relative_margin <= relative_margin_max`),
- uncertainty/std (`pair_uncertainty_std_mean >= uncertainty_std_min`),
- calibrated confidence (`|p_calibrated - 0.5| * 2 <= calibrated_confidence_max`),
- existing supervised near-tie flag (`near_tie_flag` when enabled).

Detector rule:
- mark pair as near-tie when at least `min_triggered_signals` conditions fire.

In this run, detector config was:
- `abs_margin_max=0.03`
- `relative_margin_max=0.15`
- `uncertainty_std_min=0.08`
- `calibrated_confidence_max=0.30`
- `use_supervised_near_tie_flag=true`
- `min_triggered_signals=2`

Manifest/provenance:
- config and detector stats are stored in `near_tie_policy_results.json` under `near_tie_detector`.

### 2) Near-tie routing/fallback policies

Implemented near-tie routing options:
- `pairwise_binary_backup`
- `pointwise_value`
- `balanced_round_robin` (deterministic shared/proxy fallback)
- `score_gap_heuristic` (heuristic score fallback, but when score gap is very small uses balanced routing)
- baseline/no-route behavior via `binary_forced_baseline`

Generic abstention path is preserved for matched comparison through:
- `abstain_calibrated_pairwise_backup` (temperature-calibrated abstention + binary backup).

### 3) Non-forced/shared near-tie fallback

Implemented deterministic shared-allocation proxy policy:
- `balanced_round_robin`
- It does not use learned winner confidence in the routed near-tie region.
- Instead it uses stable hash parity over `(state_id, sorted_pair_ids, remaining_budget)` to alternate winners reproducibly and avoid always forcing the same side in ties.

## Commands executed

```bash
python -m py_compile \
  experiments/bruteforce_branch_allocator.py \
  scripts/train_bruteforce_branch_allocator.py \
  scripts/run_ambiguity_calibration_and_fallback_experiment.py \
  scripts/run_near_tie_policy_experiment.py \
  scripts/mine_bruteforce_hard_regions.py \
  scripts/expand_bruteforce_exact_hard_regions.py \
  scripts/build_exact_augmented_target_regimes.py

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id near_tie_base_20260416 \
  --dataset-name openai/gsm8k \
  --max-frontier-states 80 \
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
  --labels-dir outputs/branch_label_bruteforce/near_tie_base_20260416 \
  --run-id near_tie_hard_region_mining_20260416 \
  --near-tie-margin 0.03 \
  --small-margin-threshold 0.08 \
  --high-std-threshold 0.07 \
  --max-candidates 60

python scripts/expand_bruteforce_exact_hard_regions.py \
  --base-labels-dir outputs/branch_label_bruteforce/near_tie_base_20260416 \
  --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/near_tie_hard_region_mining_20260416/mined_hard_candidates.jsonl \
  --run-id near_tie_hard_region_exact_expansion_20260416 \
  --max-target-pairs 60

python scripts/build_exact_augmented_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/near_tie_base_20260416 \
  --exact-expansion-dir outputs/branch_label_bruteforce_targets/near_tie_hard_region_exact_expansion_20260416 \
  --run-id near_tie_exact_augmented_regimes_20260416 \
  --near-tie-margin 0.03 \
  --high-margin-threshold 0.08 \
  --max-pair-std 0.08 \
  --tie-abs-margin-threshold 0.03 \
  --tie-relative-margin-threshold 0.15 \
  --tie-std-threshold 0.08 \
  --tie-use-near-tie-flag \
  --tie-include-approx

python scripts/run_ambiguity_calibration_and_fallback_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_exact_augmented_regimes_20260416 \
  --run-id ambiguity_calibration_fallback_near_tie_20260416 \
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

python scripts/run_near_tie_policy_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/near_tie_exact_augmented_regimes_20260416 \
  --run-id near_tie_policy_20260416 \
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
  --score-gap-fallback-threshold 0.02
```

## Matched comparison results (3-seed means, `v2`, both regimes matched)

In this bounded run, `all_pairs_approx` and `promoted_exact_hard_region` produced identical summary means.

Required policy set:

1. **binary forced baseline**
   - accepted accuracy: **0.5693**
   - coverage: **1.0000**
   - forced accuracy: **0.5693**
   - top-1 accuracy: **0.5238**
   - near-tie slice forced accuracy: **0.2222**
   - adjacent-rank slice forced accuracy: **0.5677**

2. **calibrated abstention + pairwise binary backup**
   - accepted accuracy: **0.6017**
   - coverage: **0.7691**
   - forced accuracy: **0.5693**
   - top-1 accuracy: **0.5238**
   - near-tie slice forced accuracy: **0.2222**
   - adjacent-rank slice forced accuracy: **0.5677**

3. **dedicated near-tie detector + pairwise binary backup**
   - accepted accuracy: **0.5693**
   - coverage: **1.0000**
   - forced accuracy: **0.5693**
   - top-1 accuracy: **0.5238**
   - near-tie slice forced accuracy: **0.2222**
   - adjacent-rank slice forced accuracy: **0.5677**

4. **dedicated near-tie detector + pointwise fallback**
   - accepted accuracy: **0.5960**
   - coverage: **1.0000**
   - forced accuracy: **0.5960**
   - top-1 accuracy: **0.6012**
   - near-tie slice forced accuracy: **0.5556**
   - adjacent-rank slice forced accuracy: **0.6337**

5. **dedicated near-tie detector + balanced/shared fallback**
   - accepted accuracy: **0.4863**
   - coverage: **1.0000**
   - forced accuracy: **0.4863**
   - top-1 accuracy: **0.4226**
   - near-tie slice forced accuracy: **0.4444**
   - adjacent-rank slice forced accuracy: **0.4997**

Additional implemented policy (`score_gap_heuristic`) was weaker overall in this run.

## Detector behavior summary

- Detected near-tie rate on test pairs: **0.5887**
- Detection coverage on supervised near-tie slice: **1.0000**

## Per-dataset and per-budget slices (forced accuracy)

Dataset slice in this bounded run (`openai/gsm8k` only):
- binary forced baseline: **0.5693**
- calibrated abstention + pairwise backup: **0.5693**
- near-tie + pairwise backup: **0.5693**
- near-tie + pointwise: **0.5960**
- near-tie + balanced/shared: **0.4863**

Budget slices:
- Budget 2: baseline **0.5000**, near-tie+pointwise **0.6667**, near-tie+balanced **0.1667**
- Budget 3: baseline **0.7500**, near-tie+pointwise **0.7500**, near-tie+balanced **0.4167**
- Budget 4: baseline **0.5833**, near-tie+pointwise **0.5833**, near-tie+balanced **0.5833**

## Main question answers

### 1) Did dedicated near-tie policy help more than generic calibration/fallback?

- **Partially yes** in this bounded setting:
  - near-tie detector + pointwise fallback improved forced near-tie accuracy from **0.2222 -> 0.5556**,
  - and improved overall forced/top-1 accuracy over both baseline and calibrated-abstention+binary-backup.
- **Not universally**:
  - near-tie detector + pairwise-binary-backup did not change outcomes,
  - detector + balanced/shared improved near-tie slice but hurt overall forced/top-1 substantially.

### 2) Is non-forced/shared tie handling better than always forcing one winner?

- **Mixed/negative overall in this run**:
  - balanced/shared policy improved near-tie slice vs baseline (**0.4444 vs 0.2222**),
  - but reduced overall forced accuracy and top-1 materially.
- Therefore this run does not support replacing sharp tie resolution with pure balanced sharing as the default.

### 3) Has the main bottleneck shifted?

- Conservative reading:
  - near-tie ambiguity remains a central bottleneck,
  - dedicated routing helps only with the right fallback (pointwise here),
  - policy choice in the near-tie route is now a first-order lever.
- This does **not** justify a solved claim.

## Artifacts

- Base labels:
  - `outputs/branch_label_bruteforce/near_tie_base_20260416/`
- Hard-region mining:
  - `outputs/branch_label_bruteforce_targets/near_tie_hard_region_mining_20260416/`
- Exact hard-region expansion:
  - `outputs/branch_label_bruteforce_targets/near_tie_hard_region_exact_expansion_20260416/`
- Exact-augmented regimes:
  - `outputs/branch_label_bruteforce_targets/near_tie_exact_augmented_regimes_20260416/`
- Matched ambiguity baseline:
  - `outputs/branch_label_bruteforce_learning/ambiguity_calibration_fallback_near_tie_20260416/`
- Matched near-tie policy run:
  - `outputs/branch_label_bruteforce_learning/near_tie_policy_20260416/`
