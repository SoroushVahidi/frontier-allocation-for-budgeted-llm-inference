# Confident-Learning-style hard-pair cleanup pass status (2026-04-17)

## Scope

This bounded pass applies one auditable **Confident-Learning-style error ranking** over the current pairwise corpus, then performs one conservative hard-pair cleanup action (exclude worst suspicious hard pairs only).

What stayed fixed:
- fixed-budget cross-controller frontier allocation framing,
- pairwise branch comparison as default learned object,
- `v2` features in matched training,
- existing tie-aware / strict-coupled / learned-deferral controller family untouched.

## Commands executed

```bash
python scripts/run_bruteforce_branch_label_generator.py \
  --run-id cl_cleanup_base_20260417 \
  --max-frontier-states 120 \
  --dataset-name openai/gsm8k \
  --episodes-per-example 1 \
  --frontier-budget 7 \
  --min-remaining-budget 2 \
  --max-remaining-budget 4 \
  --init-branches 3 \
  --max-branches-per-state 4 \
  --rollout-samples-per-candidate 12 \
  --max-allocation-samples 24 \
  --seed 23

python scripts/build_bruteforce_target_regimes.py \
  --labels-dir outputs/branch_label_bruteforce/cl_cleanup_base_20260417 \
  --run-id cl_cleanup_base_targets_20260417 \
  --pair-strategies all_pairs \
  --near-tie-margin 0.03 \
  --tie-use-near-tie-flag \
  --tie-include-approx

python scripts/run_confident_learning_hard_pair_cleanup_pass.py \
  --labels-dir outputs/branch_label_bruteforce_targets/cl_cleanup_base_targets_20260417/regime_all_pairs \
  --run-id cl_hard_pair_cleanup_20260417 \
  --near-tie-margin 0.03 \
  --low-margin-threshold 0.08 \
  --high-std-threshold 0.08 \
  --suspicious-top-hard-fraction 0.15 \
  --max-exclude-hard 24 \
  --min-hard-exclude 8

python scripts/run_confident_learning_hard_pair_matched_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/cl_hard_pair_cleanup_20260417 \
  --run-id cl_hard_pair_cleanup_matched_20260417 \
  --seeds 11,29,47 \
  --feature-set v2 \
  --near-tie-margin 0.03
```

## A) Suspicious-pair scoring method implemented

Method name:
- `bounded_confident_learning_style_hard_pair_error_ranking_v1`

Pipeline:
1. Build pairwise learning table from current all-pairs regime.
2. Fit out-of-fold (5-fold, state-hash-split) provisional pairwise logistic model.
3. For each pair, compute observed-label confidence `p_obs` and inconsistency `1 - p_obs`.
4. Restrict ranking to hard-region rows and apply severity multipliers.

Hard-region emphasis used in this pass:
- near-tie,
- adjacent-rank,
- low absolute margin,
- low relative margin,
- high pair uncertainty std,
- approx + (low-margin & high-std) disagreement-prone indicator.

Primary artifact:
- `outputs/suspicious_hard_pairs/cl_hard_pair_cleanup_20260417/suspicious_pair_ranking.jsonl`

## B) Cleaned target regime created (single design)

Chosen conservative action:
- **exclude only top suspicious hard pairs**.

Created regimes:
- baseline: `outputs/branch_label_bruteforce_targets/cl_hard_pair_cleanup_20260417/regime_all_pairs_baseline`
- cleaned: `outputs/branch_label_bruteforce_targets/cl_hard_pair_cleanup_20260417/regime_cl_hardpair_excluded`

Coverage summary:
- base pairs: 162
- hard pairs scored: 156
- excluded hard pairs: 23 (14.7% of hard)
- cleaned pairs retained: 139 (85.8% overall retention)
- near-tie retained: 11 / 13

## C) Bounded matched learner comparison run

Run artifact:
- `outputs/branch_label_bruteforce_learning/cl_hard_pair_cleanup_matched_20260417/cl_hard_pair_matched_summary.json`

Anchor model for primary comparison:
- `pairwise` (logistic pairwise baseline), seeds `11,29,47`, fixed `v2` features.

Mean metrics (clean - baseline):
- pairwise accuracy: `+0.1781`
- top-1: `+0.0816`
- near-tie: `+0.0000`
- adjacent-rank: `+0.1405`
- Brier: `-0.0737` (improved)
- exact-promoted slices: unchanged at `0.0000` in both regimes (no exact-promoted labels in this corpus)

## D) Interpretation against success/failure criteria

- This bounded CL-style cleanup **improved at least one hard slice** (adjacent-rank) and improved trustworthiness proxy (Brier) while preserving broad coverage.
- Near-tie forced behavior did **not** improve in this run.
- So this is a **partial success**: hard-slice quality improved for adjacent-rank but near-tie ambiguity remains unresolved.

## E) What remains unresolved / next step

Remaining unresolved:
- persistent near-tie ambiguity quality,
- zero exact-promoted evaluation signal in this specific bounded corpus.

If next pass is needed, recommended priority order:
1. stronger probabilistic/soft targets for the very top suspicious near-tie pairs,
2. budgeted exact review of top suspicious near-tie pairs,
3. multi-judge reliability aggregation only after (1)/(2) are in place.

## Artifacts

- Suspicious ranking:
  - `outputs/suspicious_hard_pairs/cl_hard_pair_cleanup_20260417/suspicious_pair_ranking.jsonl`
- Cleanup summary:
  - `outputs/branch_label_bruteforce_targets/cl_hard_pair_cleanup_20260417/cl_hard_pair_cleanup_summary.json`
- Cleaned regimes:
  - `outputs/branch_label_bruteforce_targets/cl_hard_pair_cleanup_20260417/regime_all_pairs_baseline/`
  - `outputs/branch_label_bruteforce_targets/cl_hard_pair_cleanup_20260417/regime_cl_hardpair_excluded/`
- Matched comparison:
  - `outputs/branch_label_bruteforce_learning/cl_hard_pair_cleanup_matched_20260417/cl_hard_pair_matched_results.json`
  - `outputs/branch_label_bruteforce_learning/cl_hard_pair_cleanup_matched_20260417/cl_hard_pair_matched_summary.json`
