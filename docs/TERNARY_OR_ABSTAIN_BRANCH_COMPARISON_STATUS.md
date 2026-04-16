# Ternary / selective-abstention branch-comparison status (2026-04-16)

## Scope

This pass tests whether remaining hard branch-comparison failures are mostly caused by forcing binary decisions on genuinely ambiguous pairs.

Project framing is unchanged:
- fixed-budget next-step branch allocation is the center,
- pairwise branch comparison remains the main learned object,
- pointwise value is used only as explicit fallback semantics.

## What was added

### 1) Ternary/tie-aware supervision hooks

Target-regime materialization now annotates pair rows with ambiguity/tie metadata and labels:
- `ambiguous_tie_target` (bool)
- `ambiguous_tie_reasons` (trigger list)
- `ternary_label_name` (`prefer_branch_i`, `tie_ambiguous`, `prefer_branch_j`)

Tie-band triggers are configurable and use existing signals:
- absolute margin threshold,
- relative margin threshold,
- uncertainty std threshold,
- near-tie flag,
- provenance gating by exact vs approx mode.

### 2) Learning-path support

The branch-allocation learning module now supports optional ternary pairwise supervision fields (`ternary_label`) and an optional ternary learner path (`pairwise_ternary_logreg`) while keeping the existing binary pairwise path intact.

### 3) Matched formulation experiment runner

New script: `scripts/run_ternary_or_abstain_branch_comparison_experiment.py`.

It compares, under matched features/regimes/seeds:
1. forced binary pairwise decisions,
2. ternary compare/tie predictions,
3. selective abstention from binary confidence.

It reports:
- accepted-pair accuracy,
- coverage / abstention,
- tie-detection precision/recall/F1,
- near-tie and adjacent-rank slices,
- forced-decision accuracy under fallback,
- top-1 effects from pairwise tournament resolution.

## Commands executed

```bash
python -m py_compile experiments/bruteforce_branch_allocator.py scripts/build_bruteforce_target_regimes.py scripts/build_exact_augmented_target_regimes.py scripts/run_ternary_or_abstain_branch_comparison_experiment.py scripts/train_bruteforce_branch_allocator.py

python scripts/run_bruteforce_branch_label_generator.py --run-id ternary_base_approx_20260416 --dataset-name openai/gsm8k --max-frontier-states 100 --episodes-per-example 1 --frontier-budget 7 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --rollout-samples-per-candidate 16 --max-allocation-samples 32 --seed 23

python scripts/mine_bruteforce_hard_regions.py --labels-dir outputs/branch_label_bruteforce/ternary_base_approx_20260416 --run-id ternary_hard_region_mining_20260416 --near-tie-margin 0.03 --small-margin-threshold 0.08 --high-std-threshold 0.07 --max-candidates 80

python scripts/expand_bruteforce_exact_hard_regions.py --base-labels-dir outputs/branch_label_bruteforce/ternary_base_approx_20260416 --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/ternary_hard_region_mining_20260416/mined_hard_candidates.jsonl --run-id ternary_hard_region_exact_expansion_20260416 --max-target-pairs 80

python scripts/build_exact_augmented_target_regimes.py --labels-dir outputs/branch_label_bruteforce/ternary_base_approx_20260416 --exact-expansion-dir outputs/branch_label_bruteforce_targets/ternary_hard_region_exact_expansion_20260416 --run-id ternary_exact_augmented_regimes_20260416 --near-tie-margin 0.03 --high-margin-threshold 0.08 --max-pair-std 0.08 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.15 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx

python scripts/run_ternary_or_abstain_branch_comparison_experiment.py --targets-root outputs/branch_label_bruteforce_targets/ternary_exact_augmented_regimes_20260416 --run-id ternary_or_abstain_branch_comparison_20260416 --seeds 11,29,47 --feature-set v2 --regimes all_pairs_approx,promoted_exact_hard_region --near-tie-margin 0.03 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.15 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx --abstain-confidence-threshold 0.20 --fallback-policy pointwise_value
```

## Tie-band and abstention rules used

### Tie-band definition

A pair is marked `ambiguous_tie_target = true` if **any** of the following hold:
- `margin_abs <= 0.03`,
- `relative_margin <= 0.15`,
- `pair_uncertainty_std_mean >= 0.08`,
- `near_tie_flag == true`.

Mode policy in this run:
- `tie_include_approx = true`,
- `tie_require_exact_or_mixed = false`.

Observed tie prevalence in main regimes: ~0.743 ambiguous rate.

### Selective abstention definition

Binary logistic confidence abstains when:
- `abs(sigmoid(score_i-score_j)-0.5)*2 < 0.20`.

Fallback for tie/abstain in this run:
- `pointwise_value` (pointwise ridge score comparison on the same candidate features).

## Matched results (3-seed means, feature set fixed at v2)

Results were identical across `all_pairs_approx` and `promoted_exact_hard_region` in this bounded run.

### Forced binary baseline

- accepted accuracy: **0.5606**
- coverage: **1.0000**
- abstention: **0.0000**
- forced accuracy: **0.5606**
- tie-detection F1: **0.0000**
- near-tie forced accuracy: **0.1667**
- adjacent-rank forced accuracy: **0.5629**
- top-1 accuracy: **0.5984**

### Ternary compare/tie formulation

- accepted accuracy: **0.3333**
- coverage: **0.0152**
- abstention/tie rate: **0.9848**
- forced accuracy (with pointwise fallback): **0.5265**
- tie-detection F1: **0.8796**
- near-tie forced accuracy: **0.5833**
- adjacent-rank forced accuracy: **0.5237**
- top-1 accuracy: **0.5040**

Interpretation: tie detection was strong, but the tie policy was overly broad in this threshold setting and collapsed usable coverage.

### Selective abstention formulation

- accepted accuracy: **0.5659**
- coverage: **0.6136**
- abstention rate: **0.3864**
- forced accuracy (with pointwise fallback): **0.5114**
- tie/abstain detection F1 (vs ambiguous target): **0.4333**
- near-tie forced accuracy: **0.1667**
- adjacent-rank forced accuracy: **0.5205**
- top-1 accuracy: **0.5508**

Interpretation: selective abstention improved accepted-pair accuracy at moderate coverage, but fallback quality still limited forced and ranking outcomes.

## Main question answer (bounded evidence)

Was forced binary comparison still hurting hardest slices?
- **Partly yes**: binary near-tie forced accuracy remained weak (0.1667), consistent with ambiguity pressure.

Did tie/abstain handling improve hard-case reliability?
- **Mixed**:
  - Ternary labeling improved tie detection strongly, but practical coverage collapsed under this rule set.
  - Selective abstention gave a cleaner coverage/accuracy tradeoff, but did not improve forced near-tie behavior under current fallback.

Does bottleneck now look like irreducible ambiguity vs remaining feature/model weakness?
- Evidence is most consistent with **substantial ambiguity effects plus fallback-calibration weakness**.
- This pass does **not** justify claiming the bottleneck is solved.

## Artifacts

- Base approximate labels:
  - `outputs/branch_label_bruteforce/ternary_base_approx_20260416/`
- Hard-region mining:
  - `outputs/branch_label_bruteforce_targets/ternary_hard_region_mining_20260416/`
- Targeted exact expansion:
  - `outputs/branch_label_bruteforce_targets/ternary_hard_region_exact_expansion_20260416/`
- Exact-augmented regimes with tie annotations:
  - `outputs/branch_label_bruteforce_targets/ternary_exact_augmented_regimes_20260416/`
- Matched formulation comparison:
  - `outputs/branch_label_bruteforce_learning/ternary_or_abstain_branch_comparison_20260416/`
