# Incumbent-challenger metalevel controller calibration status (2026-04-19)

## Scope of this pass

This was a **diagnosis + bounded calibration** pass on the existing metalevel ICC scaffold (same family, no new method line).

Primary question:
- why did the initial bounded run underperform,
- and can local threshold calibration recover performance without broad changes?

## What was changed (local only)

1. **Precision correction on intermediate-result detector**
- Only fire mismatch logic on terminal branches with a predicted answer.
- Require stronger evidence before mismatch penalties trigger (numeric answer + missing finality marker conditions for target-type rules).

2. **Metalevel branch-selection hookup fix**
- The prior pass computed `delta_expand_vs_commit_now` but did not use it directly to override branch selection in the action loop.
- This pass applies metalevel preview selection (`best_expand_branch_id`) before action execution, while retaining the same controller family and observability fields.

3. **Grid-capable bounded runner + harmed-case diagnostics**
- Extended runner now executes a small matched grid over:
  - `challenger_upside_commit_max`
  - `metalevel_delta_margin`
  - `near_tie_commit_margin_extra`
  - near-tie force toggle and force-threshold fraction.
- Added explicit harmed-case subtype buckets:
  - `premature_extra_exploration_false_non_commit`
  - `wrong_challenger_chosen`
  - `intermediate_penalty_fired_but_hurt`
  - `correlated_support_penalty_side_effect`
  - `other_harmed`

## Small matched grid used

- dataset: `openai/gsm8k`
- subset: `8`
- grid seed: `11`
- confirmatory seed: `23`
- budget: `6`
- methods: baseline `...commit_v1` vs candidate `...metalevel_v2`
- total settings: `16` (cheap bounded grid)

## Diagnostic findings from this pass

1. **Intermediate-result penalty overfiring was not observed in this bounded slice**
- candidate intermediate flag rate remained `0.0` in grid and confirmatory summaries.

2. **Harms are mostly not from intermediate mismatch penalties**
- harmed breakdown is dominated by `wrong_challenger_chosen` + `other_harmed`.
- one prior false-non-commit style harm was reduced after wiring the metalevel branch override.

3. **Threshold knobs tested here had weak effect on this tiny slice**
- all 16 settings tied on the same bounded outcome metrics in this run.
- this suggests either a narrow slice bottleneck or limited threshold leverage at this budget/sample size.

## Bounded outcomes (conservative)

- Best grid setting selected by candidate accuracy then wrong_commit_timing:
  - `challenger_upside_commit_max=0.15`
  - `metalevel_delta_margin=0.00`
  - `near_tie_commit_margin_extra=0.00`
  - `force_extra_explore_on_near_tie=true`
  - `near_tie_force_upside_frac_threshold=0.60`

- **Grid best vs baseline (seed 11):**
  - candidate accuracy `0.625` vs baseline `0.75` (delta `-0.125`)
  - candidate wrong_commit_timing `2` vs baseline `1`
  - improved `1`, harmed `2`

- **Confirmatory bounded run (seed 23) with best setting:**
  - candidate accuracy still `-0.125` vs baseline
  - wrong_commit_timing still higher by `+1`

So this pass is still **unfavorable** relative to baseline under bounded evidence.

## Config/wiring update from calibration

The strategy defaults for `broad_diversity_aggregation_strong_v1_incumbent_challenger_metalevel_v2` were updated to the best bounded grid setting above.

## Artifacts to inspect

- `outputs/incumbent_challenger_metalevel_bounded_eval_20260419/grid_and_confirmatory_summary.json`
- `outputs/incumbent_challenger_metalevel_bounded_eval_20260419/best_setting_grid_harmed_cases.json`
- `outputs/incumbent_challenger_metalevel_bounded_eval_20260419/confirmatory_harmed_cases.json`

## Current recommendation

Keep the metalevel ICC line as an active candidate (still canonical-family-consistent), but treat it as **not yet favorable**. Next bounded step should target wrong-challenger selection mechanics directly (still local) before any broader sweep.
