# Incumbent-challenger commit-interaction refinement status (2026-04-19)

## Purpose

Run one bounded local refinement pass in the same metalevel ICC family, focused on **commit-side interaction** after challenger ranking improvements.

## Local change tested (same family, no redesign)

1. **Two-stage local separation kept explicit in controller internals**
- Stage 1: stop vs continue gate (`stop_vs_continue_gate`) using commit-vs-best-continue comparison.
- Stage 2: if continue, choose branch by existing incumbent-vs-challenger selector (including overthrow scoring).

2. **Budget-conditioned local commit tuning knobs (bounded)**
- `remaining_budget_commit_bias`
- `late_stage_commit_bonus`
- `stop_continue_value_margin`
- `continue_requires_min_best_value`
- `near_tie_commit_band`
- plus one near-tie cleanup toggle in v2: `force_extra_explore_on_near_tie = false`

3. **Commit-side diagnostics added (inspectable, per-check + aggregate)**
- `false_non_stop`
- `commit_should_have_happened_before_selected_challenger`
- `commit_deferred_despite_low_best_continue_value`
- `near_tie_commit_blocked`
- plus aggregate counts/rates in metadata (`false_non_stop_count`, `late_commit_after_selector_count`, `commit_deferred_low_continue_value_count`, `late_stage_commit_rate`, `near_tie_continuation_rate`).

## Bounded comparison setup

- dataset: `openai/gsm8k`
- subset size: `8`
- seed: `11`
- budget: `6`
- methods compared:
  1. baseline (`broad_diversity_aggregation_strong_v1_incumbent_challenger_commit_v1`)
  2. selector-refined reference inside same family (`metalevel_v2_selector_refined_v2`)
  3. commit-tuned local refinement v1
  4. commit-tuned local refinement v2

## Bounded results (conservative)

- Baseline: accuracy `0.75`, wrong_commit_timing `0`.
- Selector-refined reference: accuracy `0.375`, wrong_commit_timing `3`, wrong_challenger `7`.
- Commit-tuned v1: accuracy `0.50`, wrong_commit_timing `4`, wrong_challenger `4`.
- Commit-tuned v2: accuracy `0.625`, wrong_commit_timing `2`, wrong_challenger `2`.

### Diagnostic signal

- Harmed-case subtype concentration for commit-tuned v2 is mostly **late commit after improved challenger selection**.
- `near_tie_continuation_rate` remained high (`1.0`) across compared methods in this bounded run.
- Mean best-continue value on baseline-commit / refined-continue states was low-to-moderate (`~0.03`), supporting the hypothesis that some continuation decisions are weakly justified.
- `false_non_stop_count` is now explicitly tracked with stricter commit-side criteria; in this bounded pass it remained non-zero in selector-refined and commit-tuned v2 settings, indicating residual stop/continue gate miscalibration rather than pure challenger-selection error.

## Interpretation

- This local commit-side pass improved over the selector-refined reference (`0.375 -> 0.625` accuracy; wrong_challenger `7 -> 2`; wrong_commit_timing `3 -> 2`).
- But it **still remains unfavorable vs baseline** (`0.625 < 0.75`, wrong_commit_timing `2 > 0`).
- So the family is moving in the right local direction from the poorer selector-refined reference in this run, but is not yet baseline-competitive.

## Next recommendation (exact)

Run one additional **small** pass in the same family, but narrow to near-tie stop/continue behavior:
1. Reduce near-tie continuation stickiness without broad search (single-point tweak around `near_tie_commit_band` and `continue_requires_min_best_value`).
2. Keep selector parameters fixed at current refined values.
3. Re-check only the same matched slice and track whether wrong_commit_timing can be reduced from `2` to `<=1` while holding wrong_challenger at `<=2`.

## Artifacts

- `outputs/incumbent_challenger_commit_interaction_refinement_bounded_eval_20260419/summary.json`
- `outputs/incumbent_challenger_commit_interaction_refinement_bounded_eval_20260419/commit_side_diagnostics.json`
- `outputs/incumbent_challenger_commit_interaction_refinement_bounded_eval_20260419/per_example_results.jsonl`
