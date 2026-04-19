# Incumbent-challenger selector refinement status (2026-04-19)

## Purpose

One more bounded local refinement pass inside the same metalevel ICC family, focused on wrong-challenger selection mechanics.

## Local refinement implemented

1. **Separated continue-time challenger ranking from commit calibration**
- Kept commit-side thresholds from the prior best bounded setting.
- Refined only the ranking among continuation candidates via a challenger overthrow score.

2. **Added challenger overthrow score + penalties**
- New inspectable terms:
  - `challenger_overthrow_weight`
  - `challenger_correlation_penalty`
  - `challenger_repeat_failure_penalty`
  - `challenger_min_relative_upside`
  - `challenger_low_margin_penalty`
- Challenger ranking now uses `challenger_overthrow_score` rather than raw `delta_expand_vs_commit_now` alone.

3. **Added challenger selection diagnostics in controller metadata**
- For challenger expansions, track outcomes:
  - `later_overtook_incumbent`
  - `improved_incumbent_support_indirectly`
  - `failed_to_change_winner`
  - `dominated_ex_post_by_other_challenger`
- Added aggregate fields:
  - `wrong_challenger_chosen_count`
  - `challenger_overtook_rate`
  - `challenger_dominated_rate`
  - `challenger_outcome_counts`

## Bounded comparison setup

- dataset: `openai/gsm8k`
- subset: `8`
- seed: `11`
- budget: `6`
- compared methods:
  1. baseline (`broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1`)
  2. current best metalevel v2 setting
  3. refined overthrow v1
  4. refined overthrow v2

## Bounded results (conservative)

- Baseline accuracy: `0.75`
- Current best v2 (unrefined selector): accuracy `0.375`, wrong_challenger_chosen_count `7`
- Refined v1: accuracy `0.50`, wrong_challenger_chosen_count `4`
- Refined v2: accuracy `0.625`, wrong_challenger_chosen_count `2`

Relative to baseline, refined v2 is still unfavorable on accuracy (`-0.125`) and wrong_commit_timing (`+2`), but it materially reduced wrong-challenger behavior versus the current best v2 (`7 -> 2` wrong-challenger count on this bounded run).

## Interpretation

- The local selector refinement appears directionally useful for the targeted failure mode (wrong-challenger choice), especially in refined v2.
- The metalevel line is **still not favorable vs baseline overall** in this bounded pass.
- Recommendation: keep this family active, but prioritize one more bounded local pass on commit-side calibration interaction after improved challenger ranking (no new family, no broad sweep).

## Artifacts

- `outputs/incumbent_challenger_selector_refinement_bounded_eval_20260419/summary.json`
- `outputs/incumbent_challenger_selector_refinement_bounded_eval_20260419/per_example_results.jsonl`
