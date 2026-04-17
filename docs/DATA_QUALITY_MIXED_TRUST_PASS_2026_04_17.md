# Bounded data-quality pass: quality-mixed-trust regime (2026-04-17)

## A) Short implementation plan

1. Keep current project direction fixed (pairwise default, `v2` features, no controller redesign).
2. Implement one bounded supervision-quality improvement in the existing target builder:
   - add provenance-aware reliability weights,
   - add one new regime that excludes only the noisiest approximate hard pairs,
   - keep broad coverage for easy/high-confidence pairs.
3. Build a matched baseline (`all_pairs`) and improved (`quality_mixed_trust`) target regime from the same source corpus.
4. Run one matched learner comparison (same seeds/model stack) and compare hard-slice metrics.

## B) Concrete data-quality change implemented

Single design implemented: **provenance-aware mixed-trust hard-case filtering + reliability weighting**.

- Added a `quality_mixed_trust` target regime in `scripts/build_bruteforce_target_regimes.py`.
- Added explicit per-pair provenance fields:
  - `supervision_trust_tier`
  - `supervision_reliability_weight`
  - `keep_in_quality_mixed_trust`
- Regime behavior:
  - keep high-confidence easy approximate pairs,
  - keep medium-trust pairs with lower reliability weight,
  - exclude only low-trust approximate near-tie + adjacent-rank + high-uncertainty pairs,
  - preserve pairwise metadata/provenance.
- Learning now consumes `supervision_reliability_weight` via pairwise sample weighting.

This is one bounded pipeline-quality change (not a controller redesign, not a new dataset pass).

## C) Target/data artifacts created

- Base approx labels:
  - `outputs/branch_label_bruteforce/dq_base_approx_20260417/`
- Baseline/improved regimes for the pass:
  - `outputs/branch_label_bruteforce_targets/dq_target_regimes_quality_only_20260417/regime_all_pairs/`
  - `outputs/branch_label_bruteforce_targets/dq_target_regimes_quality_only_20260417/regime_quality_mixed_trust/`
- Exact-vs-approx trust diagnostic artifacts (same source config; audit capability check):
  - `outputs/branch_label_bruteforce_targets/dq_target_regimes_20260417/exact_vs_approx_audit_pairs/`

Coverage retained vs baseline:

- baseline pairs: 135
- improved pairs: 116
- excluded low-trust hard pairs: 19 (14.1%)
- near-tie rate reduced: 0.2296 -> 0.1034
- adjacent-rank pairs retained: 88 / 107 (82.2%)

Interpretation: this pass does **not** collapse to easy-only data; it keeps most adjacent-rank structure while removing the most ambiguous low-trust subset.

## D) One bounded matched learner comparison run

- Matched run:
  - `outputs/branch_label_bruteforce_learning/dq_quality_matched_quality_only_20260417/`
- Setup:
  - same seeds: 11, 29, 47
  - same target root, models, and evaluation path
  - feature set fixed at `v2`
  - compared only:
    - `all_pairs`
    - `quality_mixed_trust`

## E) Results summary (pairwise model, 3-seed means)

- Pairwise accuracy: **0.5931 -> 0.6141** (+0.0210)
- Top-1: **0.5278 -> 0.5556** (+0.0278)
- Near-tie: **0.1667 -> 0.1667** (flat)
- Adjacent-rank: **0.5914 -> 0.6222** (+0.0308)
- Exact-promoted slice: not present in this no-promotion run (`0.0` by construction)

Conservative interpretation:

- The bounded mixed-trust cleanup improved overall and adjacent-rank behavior.
- It did **not** improve near-tie forced behavior in this run.
- The remaining unresolved problem is still hardest near-tie ambiguity; likely next step is either:
  1) more exact coverage specifically on near-tie adjacent hard slices, or
  2) stronger selective weighting/defer semantics specifically for those pairs.

## Commands executed

```bash
python scripts/run_bruteforce_branch_label_generator.py --run-id dq_base_approx_20260417 --dataset-name openai/gsm8k --max-frontier-states 90 --episodes-per-example 1 --frontier-budget 7 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --rollout-samples-per-candidate 16 --max-allocation-samples 32 --seed 23

python scripts/run_bruteforce_branch_label_generator.py --run-id dq_base_exact_20260417 --dataset-name openai/gsm8k --max-frontier-states 90 --episodes-per-example 1 --frontier-budget 7 --min-remaining-budget 2 --max-remaining-budget 4 --init-branches 3 --max-branches-per-state 4 --rollout-samples-per-candidate 16 --max-allocation-samples 32 --seed 23 --exact-mode --max-exact-branches 6 --max-exact-remaining-budget 8

python scripts/build_bruteforce_target_regimes.py --labels-dir outputs/branch_label_bruteforce/dq_base_approx_20260417 --run-id dq_target_regimes_quality_only_20260417 --pair-strategies all_pairs,quality_mixed_trust --near-tie-margin 0.03 --high-margin-threshold 0.08 --max-pair-std 0.08 --low-trust-near-tie-approx-weight 0.25 --medium-trust-approx-weight 0.7 --exact-trust-weight 1.15 --low-trust-std-threshold 0.06

python scripts/run_target_fidelity_regime_experiment.py --targets-root outputs/branch_label_bruteforce_targets/dq_target_regimes_quality_only_20260417 --run-id dq_quality_matched_quality_only_20260417 --seeds 11,29,47 --near-tie-margin 0.03 --pairwise-near-tie-action none --feature-set v2
```
