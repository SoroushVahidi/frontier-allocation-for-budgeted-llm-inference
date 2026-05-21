# MLJ Reviewer-Risk Analysis, 2026-05-20

This note records offline analyses added before MLJ submission. No provider API calls were made.

Budget accounting boundary: all comparisons use a per-method matched budget cap of
`B=6` logical calls for each candidate-producing method. FIX-2+FIX-4 is a
post-generation answer selector and adds no model calls after candidate answers
and frontier metadata are available. If frontier, L1, S1, and TALE must all be
generated from scratch, total deployment cost depends on which producers are run.

## Per-example artifacts used

- Seed 41 main 300:
  `outputs/overnight_fix5_promotion_grade_validation_20260519T040621Z/runner_output/cohere_real_model_cost_normalized_validation_fix5_overnight_live_20260519T040621Z/per_example_records.jsonl`
- Seed 61 independent 120:
  `outputs/fix6_lovec_independent_extra_action_pilot_20260519T163021Z/base_runner_output/cohere_real_model_cost_normalized_validation_base_live_20260519T163021Z/per_example_records.jsonl`
- Seed 71 Final-300:
  `outputs/final_fix24_all_external_validation_20260519_20260520T000902Z/runner_output/cohere_real_model_cost_normalized_validation_final_fix24_live_20260519/per_example_records.jsonl`
- Aggregate source manifest:
  `outputs/final_fix24_all_external_postrun_20260520_20260520T025349Z/aggregate_with_prior_validation.csv`

Required columns/fields were present: `example_id`, `dataset`, `question`, `seed`, `budget`, `provider`, `model`, `method`, `final_answer_canonical`, `gold_answer_canonical`, `exact_match`, and frontier `result_metadata` including `override_reason`, `frontier_support`, and `candidate_pool_answer_group_count`.

## Pooled ensemble baselines

Primary pooled ensemble: strict majority over frontier, L1, S1, and TALE; frontier answer is the deterministic gold-free fallback for 2-2 ties or all-different answers.

External-only ensemble: majority over L1, S1, and TALE; if no majority, use the existing fixed fallback TALE > S1 > L1.

| Split | FIX-2+FIX-4 | Pooled-4 | External-3 | FIX-2+FIX-4 minus Pooled-4 |
|---|---:|---:|---:|---:|
| seed41 | 250/300 = 83.33% | 251/300 = 83.67% | 253/300 = 84.33% | -0.33pp |
| seed61 | 71/120 = 59.17% | 71/120 = 59.17% | 69/120 = 57.50% | +0.00pp |
| seed71 Final-300 | 260/300 = 86.67% | 253/300 = 84.33% | 256/300 = 85.33% | +2.33pp |
| Aggregate-720 | 581/720 = 80.69% | 575/720 = 79.86% | 578/720 = 80.28% | +0.83pp |

Bootstrap results for FIX-2+FIX-4 minus Pooled-4:

| Split | Delta | 95% CI | Bootstrap positive-delta fraction | W/L/T |
|---|---:|---:|---:|---:|
| Final-300 | +2.33pp | [-0.67, +5.67] | 0.911 | 16/9/275 |
| Aggregate-720 | +0.83pp | [-1.11, +2.78] | 0.780 | 28/22/670 |

Interpretation: FIX-2+FIX-4 remains ahead by point estimate on Final-300 and Aggregate-720, but the pooled-ensemble comparison is not statistically separated.

External tie fallback sensitivity: the promoted policy uses the fixed deterministic
TALE > S1 > L1 fallback when L1/S1/TALE all differ. Aggregate-720 FIX-2-only replay
is 80.00% under that convention, 80.14% with S1-first, 80.42% with L1-first, and
80.83% if all-different external ties retain the frontier answer. The tie rule is
therefore reported as a fixed reproducibility convention, not as an optimized
learned ranker.

## FIX-4 marginal action counts

| Split | N | FIX-2 fires | FIX-4 fires | No gate | FIX-4 before | FIX-4 after | FIX-4 W/L/T vs frontier |
|---|---:|---:|---:|---:|---:|---:|---:|
| seed41 | 300 | 38 | 2 | 260 | 0/2 | 2/2 | 2/0/0 |
| seed61 | 120 | 21 | 0 | 99 | 0/0 | 0/0 | 0/0/0 |
| seed71 Final-300 | 300 | 63 | 3 | 234 | 0/3 | 3/3 | 3/0/0 |
| Aggregate-720 | 720 | 122 | 5 | 593 | 0/5 | 5/5 | 5/0/0 |

FIX-4 is rare and conservative. In these artifacts it adds five aggregate recoveries and no observed regressions after FIX-2 precedence.

## Seed-61 diagnostic

Seed 61 is lower in absolute accuracy for all methods: frontier 57.50%, L1 57.50%, S1 56.67%, TALE 54.17%, FIX-2+FIX-4 59.17%.

The provider/model/budget are unchanged (`cohere`, `command-r-plus-08-2024`, budget 6). Question length is only modestly higher than the other sources: mean 48.5 words for seed61 vs 46.1 for seed41 and 44.6 for seed71. The available evidence supports a source-sample difficulty explanation rather than a method-specific run configuration change. The exact cause remains a limitation.

## Second dataset/provider/budget feasibility

Existing repository artifacts include MATH-500, AIME, OpenAI/Cohere, and budget-sweep outputs. They do not provide the same current four-method per-example records plus frontier `result_metadata` needed to replay FIX-2+FIX-4 under the MLJ protocol. No valid second benchmark/provider/budget result was added. A clean replication would require new matched-budget generation with the same frontier, L1, S1, and TALE logging contract.
