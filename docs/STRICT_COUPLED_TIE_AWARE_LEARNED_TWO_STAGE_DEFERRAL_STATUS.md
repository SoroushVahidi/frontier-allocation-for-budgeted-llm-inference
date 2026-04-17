# Strict-coupled tie-aware learned two-stage deferral status (2026-04-17)

## A) Short bounded implementation plan

1. Keep the current strongest scaffold fixed: pairwise default comparator, `v2` features, strict-coupled/tie-aware controller family, specialist pointwise fallback.
2. Replace only the post-hoc heuristic deferral trigger with a learned post-hoc defer head.
3. Implement a **two-stage** defer model:
   - Stage 1: predict pairwise error risk.
   - Stage 2: predict whether deferring to the specialist has positive utility over accepting pairwise.
4. Train both heads from existing pair rows/features (no end-to-end controller redesign).
5. Run one bounded matched comparison including required rows.

## B) Implementation summary

Primary file changed:
- `scripts/run_near_tie_pointwise_expert_experiment.py`

New explicit controller variant:
- `strict_coupled_tie_aware_learned_two_stage_deferral_v1`

What was kept fixed:
- pairwise comparator remains primary decision module,
- `v2` representation remains default,
- strict-coupled/tie-aware family remains scaffold,
- specialist pointwise fallback remains deferred-case expert.

What changed:
- the defer decision is now produced by learned two-stage heads instead of the previous hand-designed post-hoc signal counter.

## C) Defer-target construction (explicit and conservative)

Per pair row, define:
- `pairwise_pred`: current pairwise winner,
- `specialist_pred`: specialist pointwise fallback decision (with existing pointwise-margin guard + pairwise backup),
- `label`: existing pairwise supervision label.

Targets:
- Stage-1 target (`pairwise_error_target`): `1` iff `pairwise_pred != label`.
- Stage-2 target (`defer_utility_target`): `1` iff `specialist_pred == label` **and** `pairwise_pred != label`.

So defer is trained to fire only when fallback is expected to improve over accepting pairwise.

## D) New defer-head feature signals

The learned defer head uses current pairwise signals plus PRePair-style independent pointwise signals:

Pairwise/ambiguity/context signals:
- `margin_abs`, `relative_margin`, `pair_uncertainty_std`,
- calibrated pairwise confidence/probability,
- near-tie indicator, adjacent-rank flag,
- rank-gap,
- frontier dispersion (`frontier_score_std_mean`, `frontier_entropy_mean`),
- strict-gate/post-hoc-gate indicators and strict-gate signal count.

Independent pointwise + disagreement signals:
- `pointwise_value_i`, `pointwise_value_j`,
- `pointwise_gap_abs`,
- pairwise-vs-pointwise disagreement flag,
- `pair_margin_minus_point_gap`.

## E) Bounded matched run

Commands run:

```bash
python -m py_compile scripts/run_near_tie_pointwise_expert_experiment.py

python scripts/run_bruteforce_branch_label_generator.py \
  --run-id two_stage_defer_base_20260417 \
  --max-frontier-states 50 \
  --dataset-name openai/gsm8k \
  --episodes-per-example 1 \
  --frontier-budget 6 \
  --min-remaining-budget 2 \
  --max-remaining-budget 3 \
  --init-branches 3 \
  --max-branches-per-state 4 \
  --rollout-samples-per-candidate 10 \
  --max-allocation-samples 20 \
  --seed 13

python scripts/run_near_tie_pointwise_expert_experiment.py \
  --targets-root outputs/branch_label_bruteforce_targets/two_stage_defer_targets_20260417 \
  --run-id near_tie_two_stage_defer_head_20260417 \
  --seeds 11 \
  --feature-set v2 \
  --regimes all_pairs_approx \
  --controller-policy all \
  --detector-threshold-mode strict \
  --tie-use-near-tie-flag \
  --tie-include-approx \
  --near-tie-detector-use-near-tie-flag \
  --posthoc-deferral-require-strict-gate
```

## Required matched rows (bounded run result)

1. **binary forced baseline**
- accepted: 0.3846
- coverage: 1.0000
- forced: 0.3846
- top-1: 0.4286
- near-tie forced: 0.0000
- adjacent forced: 0.0000

2. **calibrated abstain + pairwise backup**
- accepted: 1.0000
- coverage: 0.0769
- forced: 0.3846
- top-1: 0.4286
- near-tie forced: 0.0000
- adjacent forced: 0.0000

3. **current tie-aware post-hoc deferral** (`strict_coupled_tie_aware_posthoc_deferral_v1`)
- accepted: 0.3750
- coverage: 0.6154
- forced: 0.3846
- top-1: 0.4286
- near-tie forced: 0.0000
- adjacent forced: 0.0000
- deferred rate: 0.3846
- deferred non-near-tie count: 5
- deferred-subset forced accuracy: 0.4000

4. **current strongest specialist-pointwise variant** (`strict_coupled_near_tie_specialized_pointwise_v1`)
- accepted: 0.3846
- coverage: 1.0000
- forced: 0.3846
- top-1: 0.4286
- near-tie forced: 0.0000
- adjacent forced: 0.0000

5. **new learned two-stage defer-head controller** (`strict_coupled_tie_aware_learned_two_stage_deferral_v1`)
- accepted: 0.3000
- coverage: 0.7692
- forced: 0.3846
- top-1: 0.4286
- near-tie forced: 0.0000
- adjacent forced: 0.0000
- deferred rate: 0.2308
- deferred non-near-tie count: 3
- deferred-subset forced accuracy: 0.6667

## Conservative interpretation

- The new learned two-stage defer head **reduced deferral rate** and improved deferred-subset quality in this bounded run.
- It **did not improve accepted accuracy** versus current post-hoc deferral and did not improve forced/top-1 over anchors here.
- So this is **not** a win-claim pass; it is a bounded selective-control replacement with mixed results.

## What remains unresolved

- The defer policy is now learned and cleaner, but accepted-set quality is still unstable on this tiny bounded setting.
- Hard-slice behavior (near-tie/adjacent) remains weak in this run and still depends heavily on specialist quality and target fidelity.
- Next bounded step should tune defer-head supervision/thresholding on a slightly larger fixed corpus while keeping the same scaffold.

## Artifacts

- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_head_20260417/near_tie_pointwise_expert_summary.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_head_20260417/near_tie_pointwise_expert_results.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_head_20260417/required_matched_rows.json`
- `outputs/branch_label_bruteforce_learning/near_tie_two_stage_defer_head_20260417/required_matched_rows.csv`
