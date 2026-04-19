# Marginal coverage diversity status (2026-04-18)

## Purpose

This pass targets the two dominant broad-family residuals identified in the latest audits:
- `insufficient_diversity_realized`
- `bad_diversity_realized`

Scope is explicitly **inside** the current broad diversity/aggregation family (no new family search).

## Bottleneck targeted

The current broad family (`broad_diversity_aggregation_strong_v1` main candidate, `broad_diversity_aggregation_v1` sibling) still loses many cases because:
1. diversity often fails to materialize,
2. and when diversity exists, branch additions can be low-value overlap instead of useful incremental support.

## What was implemented

New variant:
- `marginal_coverage_diversity_v1`

Implemented inside `GlobalDiversityAggregationController` as an optional mode:

\[
\text{priority} = \text{continuation} + \text{diversity\_bonus} + \lambda\,\text{coverage\_gain} - \mu\,\text{semantic\_overlap} - \text{duplicate\_cost}
\]

with this pass using:
- `lambda (coverage_weight) = 0.24`
- `mu (overlap_weight) = 0.16`

### Coverage gain design

`coverage_gain` is not lexical novelty. It combines:
1. `group_undercoverage`: branch’s normalized answer group is under-represented in active+supported mass,
2. `new_group_bonus`: branch introduces an as-yet under-covered answer group,
3. `profile_novelty`: branch support profile is dissimilar from already completed profiles in the same answer group.

Formula used:
- `0.50 * group_undercoverage + 0.30 * new_group_bonus + 0.20 * profile_novelty`

### Semantic overlap design

`semantic_overlap` penalizes near-duplicate support contributions using answer-group and support-profile similarity:
1. same-group max similarity,
2. global max similarity against completed profiles.

Formula used:
- `0.65 * same_group_max_similarity + 0.35 * global_max_similarity`

Support profiles use structured fields (answer group, depth/score/verification buckets, and lightweight reasoning-structure markers), not raw text-difference reward.

## Compared methods

Bounded simulator comparison set:
- `self_consistency_3`
- `selective_sc_hybrid_v1`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1` (current main candidate)
- `marginal_coverage_diversity_v1` (new)

Datasets/seeds/budgets:
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`, `olympiadbench`
- seeds: `11,23,37`
- budgets: `4,6,8`
- subset size: `32`

## What improved

From `aggregate_comparison_summary.json`:
- mean accuracy over budgets:
  - `self_consistency_3`: `0.5059`
  - `broad_diversity_aggregation_strong_v1`: `0.6291`
  - `marginal_coverage_diversity_v1`: `0.6669`

So the new variant improves over current broad main by `+0.0378` and remains above SC in this simulator pass.

From diversity diagnostics:
- `mean_unique_answer_groups_seen`: `1.502` (new) vs `1.254` (strong baseline)
- `useful_answer_distinct_branch_rate`: `0.381` (new) vs `0.219` (strong baseline)

This indicates more realized answer-distinct branching under budget.

## What did not improve

Mistake-group shifts versus `broad_diversity_aggregation_strong_v1`:
- `insufficient_diversity_realized`: **decreased** (`256 -> 159`, delta `-97`)
- `bad_diversity_realized`: **increased** (`23 -> 38`, delta `+15`)

Secondary residuals also increased in this pass:
- `value_ranking_error_despite_diversity`: `134 -> 157`
- `other_or_commit_timing`: `7 -> 24`

Interpretation: the pass successfully increases realized diversity, but also introduces additional noisy/low-quality diversity in a subset of cases.

## Real-model confirmation status

Not run in this pass.

Reason: this improvement pass was executed as a bounded simulator hardening step; Cohere/Gemini real-model confirmation was not feasible in this environment due missing provider credentials.

## Hard conclusion

`marginal_coverage_diversity_v1` is a useful next pass **for fixing insufficient diversity realization** and improving broad simulator competitiveness.

However, it does **not** yet solve the second bottleneck (`bad_diversity_realized`), which worsened in this run.

So the idea is partially successful and should be kept as a promising broad-family refinement, with next work focused on tightening ranking/aggregation quality so extra diversity is consistently useful.
