# Partial-order incomparability branch-comparison pass status (2026-04-17)

## Scope

This bounded pass adds one explicit incomparability (`i_wins` / `incomparable` / `j_wins`) target regime so the hardest pairs can remain unresolved instead of always being forced into directional labels or tie-probability interpolation.

Project scaffold was held fixed:
- fixed-budget cross-controller frontier allocation,
- pairwise branch comparison default object,
- `v2` hard-case features,
- no controller-family redesign.

## Conservative incomparability design implemented

A pair is labeled `incomparable` only when **all** of the following hold:
1. absolute margin is very small (`margin_abs <= tie_abs_margin_threshold`),
2. relative margin is very small (`relative_margin <= tie_relative_margin_threshold`),
3. near-tie flag is true,
4. at least one ambiguity-risk signal is present (`high std` or `adjacent-rank` or `exact-vs-approx disagreement risk`).

This is intentionally stricter than Davidson close-call ties and encodes:
- tie = “roughly equal preference”,
- incomparable = “insufficient evidence to force an ordering relation”.

## What changed

1. Added partial-order incomparability annotation helpers and strategy support in the generic target-regime builder.
2. Added exact-augmented partial-order regime materialization:
   - `regime_partial_order_promoted_exact_hard_region`.
3. Extended matched formulation runner with:
   - `partial_order_incomparable` formulation,
   - unresolved-rate metric,
   - ambiguity-detection metrics keyed to `partial_order_incomparable_target`.

## Commands executed

```bash
python -m py_compile scripts/build_bruteforce_target_regimes.py scripts/build_exact_augmented_target_regimes.py scripts/run_ternary_or_abstain_branch_comparison_experiment.py scripts/train_bruteforce_branch_allocator.py experiments/bruteforce_branch_allocator.py

python scripts/run_bruteforce_branch_label_generator.py --run-id incomparability_base_20260417 --dataset-name openai/gsm8k --max-frontier-states 60 --episodes-per-example 1 --frontier-budget 7 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --rollout-samples-per-candidate 8 --max-allocation-samples 16 --seed 23

python scripts/mine_bruteforce_hard_regions.py --labels-dir outputs/branch_label_bruteforce/incomparability_base_20260417 --run-id incomparability_hard_region_mining_20260417 --near-tie-margin 0.03 --small-margin-threshold 0.08 --high-std-threshold 0.07 --max-candidates 60

python scripts/expand_bruteforce_exact_hard_regions.py --base-labels-dir outputs/branch_label_bruteforce/incomparability_base_20260417 --mined-candidates-jsonl outputs/branch_label_bruteforce_targets/incomparability_hard_region_mining_20260417/mined_hard_candidates.jsonl --run-id incomparability_hard_region_exact_expansion_20260417 --max-target-pairs 60

python scripts/build_exact_augmented_target_regimes.py --labels-dir outputs/branch_label_bruteforce/incomparability_base_20260417 --exact-expansion-dir outputs/branch_label_bruteforce_targets/incomparability_hard_region_exact_expansion_20260417 --run-id incomparability_exact_augmented_regimes_20260417 --near-tie-margin 0.03 --high-margin-threshold 0.08 --max-pair-std 0.08 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.15 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx --tie-policy davidson_close_call

python scripts/run_ternary_or_abstain_branch_comparison_experiment.py --targets-root outputs/branch_label_bruteforce_targets/incomparability_exact_augmented_regimes_20260417 --run-id incomparability_partial_order_comparison_20260417 --seeds 11,29,47 --feature-set v2 --regimes all_pairs_approx,promoted_exact_hard_region,soft_prob_promoted_exact_hard_region,partial_order_promoted_exact_hard_region --near-tie-margin 0.03 --tie-abs-margin-threshold 0.03 --tie-relative-margin-threshold 0.15 --tie-std-threshold 0.08 --tie-use-near-tie-flag --tie-include-approx --abstain-confidence-threshold 0.20 --fallback-policy pointwise_value
```

## Target artifact summary

From `regime_partial_order_promoted_exact_hard_region/target_summary.json`:
- pairs: `85`
- near-tie rate: `0.0824`
- adjacent-rank rate: `0.8000`
- incomparability rate: `0.0824`

This confirms only a narrow hardest slice is marked unresolved.

## Matched comparison (3-seed mean)

### Binary baseline
- regime/formulation: `all_pairs_approx` + `binary_forced`
- accepted acc: `0.8419`
- coverage: `1.0000`
- forced acc: `0.8419`
- near-tie forced: `0.5000`
- adjacent forced: `0.8000`
- top-1: `0.7262`

### Davidson hard tie-aware
- regime/formulation: `promoted_exact_hard_region` + `ternary_tie`
- accepted acc: `0.7917`
- coverage: `0.6357`
- forced acc: `0.6891`
- near-tie forced: `0.3333`
- adjacent forced: `0.6524`
- top-1: `0.5992`

### Soft probabilistic tie-aware
- regime/formulation: `soft_prob_promoted_exact_hard_region` + `soft_ternary_tie`
- accepted acc: `0.7185`
- coverage: `0.8419`
- forced acc: `0.7051`
- near-tie forced: `0.3333`
- adjacent forced: `0.7000`
- top-1: `0.6071`

### New incomparability regime
- regime/formulation: `partial_order_promoted_exact_hard_region` + `partial_order_incomparable`
- accepted acc: `0.8120`
- coverage: `1.0000`
- unresolved rate: `0.0000` (model predicted no unresolved cases in test under this proxy learner)
- forced acc: `0.8120`
- near-tie forced: `0.3333`
- adjacent forced: `0.7667`
- top-1: `0.7381`

## Outcome

This bounded pass improved explicit incomparability target construction and auditing, but did **not** yet produce the desired accepted/coverage honesty gain at inference time because the current proxy learner collapsed to directional predictions (0 unresolved on test).

So, by the pass success criterion, this run should be treated as **not yet a clear win** for hard-slice honesty/accepted-coverage behavior versus strong binary anchors.

## Most likely next step

Given this failure mode, the highest-priority follow-up is:

> **abstention-aware optimization with explicit costs**

rather than more relabeling breadth or controller redesign.

Reason: unresolved targets now exist in a conservative hard slice, but the optimizer has no explicit utility/cost term forcing use of unresolved decisions at the right operating point.

## Artifacts

- Target regimes:
  - `outputs/branch_label_bruteforce_targets/incomparability_exact_augmented_regimes_20260417/`
- Matched learning run:
  - `outputs/branch_label_bruteforce_learning/incomparability_partial_order_comparison_20260417/`
