# Duplicate-aware aggregation and answer-group commit status (2026-04-18)

## Purpose

This pass targets broad-family residuals in:
- aggregation concentration / correlation handling,
- ranking errors after diversity exists,
- commit-selection instability.

Scope is strictly inside the current broad diversity/aggregation family.

## Bottleneck targeted

After the marginal-coverage pass, the family still showed that additional diversity alone did not fully solve post-diversity ranking/aggregation and commit stability. This pass therefore focused on two mechanisms:
1. duplicate-aware support discounting at answer-group aggregation time,
2. answer-group-margin-based commit logic.

## Exact duplicate-aware support rule added

For each completed branch within an answer group:

- `support_weight(branch) = process_quality * target_completion * independence_discount`

Where:
- `process_quality` and `target_completion` are canonical-stack surrogates,
- `independence_discount = max(discount_floor, 1 - discount_strength * max_same_group_profile_similarity)`
- similarity is Jaccard over support-profile features (answer group, depth/score/verify buckets, reasoning markers).

In this pass:
- `discount_strength = 0.75`
- `discount_floor = 0.22`

Group support then uses the sum of these discounted support weights, with quality/readiness-aware group scoring.

## Exact answer-group commit rule added

Commit checks run during search for the new variant.

Commit is triggered only when all are true:
- `actions >= min_actions_before_commit_check`
- `top_group_support >= 0.61`
- `answer_group_margin >= 0.17`
- `top_group_readiness >= 0.57`
- `one_step_value_estimate <= 0.64`

Otherwise continue exploring.

This replaces a pure top-branch-style bias with answer-group dominance plus one-step continuation-value gating.

## Compared methods

- `self_consistency_3`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`
- `marginal_coverage_diversity_v1`
- `duplicate_aware_aggregation_commit_v1` (new)

Setup:
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`, `olympiadbench`
- seeds: `11,23,37`
- budgets: `4,6,8`
- subset size: `32`

## What improved

- New variant mean accuracy: `0.6362`
- Current broad main (`strong_v1`) mean: `0.6345`
- So this pass gives a small positive change vs current broad main (`+0.0016`) in this simulator setting.

Mistake-group shift vs current broad main:
- `insufficient_diversity_realized`: `279 -> 264` (improved by `15`)

Support/commit diagnostics show the intended mechanisms were actually active:
- mean independence discount `< 1` (`0.948`),
- duplicate discount applied on `~10.9%` of supporting branches,
- commit trigger rate `~54.7%`,
- unstable commit flag remained low (`~0.8%`).

## What did not improve

- This variant did **not** beat `marginal_coverage_diversity_v1` in this run (`0.6362` vs `0.6596`).
- `ranking_error_despite_diversity` increased vs strong baseline (`130 -> 139`).
- `unstable_commit_selection` appears as a small new residual (`0 -> 2` in this bounded pass).
- `aggregation_concentration_failure` remained at `0` under this pass’s heuristic taxonomy, so no measurable reduction signal there.

## Real-model confirmation status

Not run in this pass.

Reason: bounded simulator hardening pass; Cohere/Gemini credentials were not available in this environment for a clean bounded real-model rerun.

## Hard conclusion

Duplicate-aware aggregation plus answer-group commit-margin logic is **directionally useful but only slightly** in this simulator pass:
- it modestly improves over the current broad main candidate,
- but does not surpass the current best marginal-coverage variant,
- and does not yet reduce the key post-diversity ranking residual.

So this should be treated as a partial mechanism improvement, not a decisive next winner.
