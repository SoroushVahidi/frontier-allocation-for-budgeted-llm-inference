# Broad diversity/aggregation method status (2026-04-18)

## Why the bounded local hybrid was insufficient

The previous broad pass showed:
- selective local hybridization improved over canonical pre-hybrid,
- but broad gap reduction vs `self_consistency_3` was not material,
- and dominant remaining failure was still `insufficient_diversity_or_aggregation` (with secondary `over_conservative_gating`).

That implies the bottleneck was not just hard-case override quality; it was missing **global** diversity/aggregation behavior during normal allocation.

## What broader variant was implemented

This pass implements a broader family where diversity/aggregation is part of the main policy:

- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`

Core policy changes:
1. Allocation priority = continuation-value base + diversity bonus - duplicate-answer penalty.
2. Diversity pressure is active globally (not restricted to near-tie hard-case mode).
3. Final decision is answer-group aggregation (support + value weighted), not only branch-top fallback.
4. Commit-delay behavior is global support-aware: keep exploring while support concentration is weak.

## How this differs from bounded local hybridization

Previous bounded hybrid:
- local activation (`hard_case_active`) driven by near-tie/disagreement/trap triggers,
- bounded local diversity and rare consensus override.

New broad variant:
- diversity-aware allocation acts across all states,
- answer-support aggregation is a default final decision mechanism,
- commit-delay is globally tied to support concentration, not near-tie-only.

## Broad comparison setting

Methods compared:
- `self_consistency_3`
- `adaptive_min_expand_1`
- `intermediate_trap_aware_near_tie_v1`
- `selective_sc_hybrid_v1`
- `broad_diversity_aggregation_v1`
- `broad_diversity_aggregation_strong_v1`

Datasets/seeds/budgets:
- datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`, `HuggingFaceH4/aime_2024`, `olympiadbench`
- seeds: `11, 23, 37`
- budgets: `4, 6, 8`
- subset size: `24`

## Results

From `aggregate_comparison_summary.json`:
- mean accuracy over budgets:
  - `self_consistency_3`: `0.4826`
  - `adaptive_min_expand_1`: `0.3750`
  - `selective_sc_hybrid_v1`: `0.3900`
  - `broad_diversity_aggregation_v1`: `0.6343`
  - `broad_diversity_aggregation_strong_v1`: `0.6343`

Gap summary:
- previous hybrid gap to SC: `+0.0926`
- best broad variant gap to SC: `-0.1516` (best broad variant now above SC in this setting)
- material narrowing flag: `true`

Hard-slice summary also improved for broad variants relative to SC in this pass.

## Diversity/answer-support behavior

From `diversity_behavior_summary.json`:
- aggregation usage is near-universal (`~0.98`)
- strong variant explores more unique answer groups and higher entropy,
- baseline broad variant keeps higher final support concentration.

Interpretation:
- global allocation + aggregation integration meaningfully changed behavior,
- not just another threshold gate tweak.

## Is this now a serious broad competitor?

In this broad simulator setting: **yes, first serious broad-competitor signal**.

However, keep caveats explicit:
- this is still a light simulator-mode broad pass (pilot subset scale),
- claim should be framed as strong directional evidence, not final paper-grade universal dominance.

## Hard conclusion

This pass is the first repository run where a method that stays within fixed-budget branch allocation but adds global diversity/aggregation as a core policy **materially closes and reverses** the previous broad gap to `self_consistency_3` in the tested setting.

So the direction is now: **promising broad-competitor candidate, pending stronger-scale confirmation.**
