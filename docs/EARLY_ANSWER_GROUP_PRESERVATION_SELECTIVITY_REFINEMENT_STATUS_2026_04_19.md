# Early answer-group preservation selectivity refinement status (2026-04-19)

## Scope
One bounded refinement pass within the same broad diversity/aggregation family:
- baseline: `broad_diversity_aggregation_strong_v1`
- prior line: `broad_diversity_aggregation_strong_v1_early_answer_group_preservation_v1`
- refined line: `broad_diversity_aggregation_strong_v1_early_answer_group_preservation_refined_v1`

Datasets/seeds/budgets were kept matched via `configs/early_answer_group_preservation_bounded_eval_20260419.json` and emitted under `outputs/early_answer_group_preservation_selectivity_refinement_bounded_eval_20260419/`.

## Exact selectivity refinement made
Kept the same early-preservation mechanism and changed only local trigger knobs:
- `early_preservation_action_window`: `5 -> 4`
- `early_preservation_min_plausible_continuation`: `0.46 -> 0.48`
- `early_preservation_target_alignment_min`: `0.34 -> 0.40`
- `early_preservation_required_group_gap`: `0.18 -> 0.24`
- `early_preservation_challenger_hold_steps`: `2 -> 1`

## Bounded outcomes
- Accuracy:
  - baseline broad: `0.6958`
  - early-preservation v1: `0.6333`
  - refined early-preservation v1: `0.6583`
- Gold answer-group survival after first split:
  - baseline broad: `0.6708`
  - early-preservation v1: `0.6042`
  - refined early-preservation v1: `0.6458`
- Gold answer-group survival after second split:
  - baseline broad: `0.6500`
  - early-preservation v1: `0.6167`
  - refined early-preservation v1: `0.6708`
- Improved / harmed / unchanged vs baseline broad:
  - early-preservation v1: `44 / 59 / 137`
  - refined early-preservation v1: `43 / 52 / 145`

## Failure categories (counts)
- Baseline broad:
  - `not_generated`: 63
  - `generated_but_underweighted`: 0
  - `collapsed_early`: 0
  - `generated_but_committed_away_from_later`: 10
- Early-preservation v1:
  - `not_generated`: 76
  - `generated_but_underweighted`: 0
  - `collapsed_early`: 0
  - `generated_but_committed_away_from_later`: 12
- Refined early-preservation v1:
  - `not_generated`: 61
  - `generated_but_underweighted`: 0
  - `collapsed_early`: 0
  - `generated_but_committed_away_from_later`: 21

## Preservation activation and harmed-case subtype readout
- Activation rate (`action_trace` had any `early_preservation_activated=true`):
  - early-preservation v1: `0.0458`
  - refined v1: `0.0000`
- Forced-step rate (`early_answer_group_preservation_forced_steps > 0`):
  - early-preservation v1: `0.0250`
  - refined v1: `0.0000`
- Harmed subtype buckets (vs baseline broad) were included as required; in this bounded pass, harmed cases were overwhelmingly `non_preservation_or_unattributed_harm`.

## Compact residual harmed-case note
Main residual failure mode after this selectivity tightening:
- The refined setting appears over-tightened; preservation almost never fires, so the run mostly reverts to baseline-like behavior without recapturing the previously observed joint gains.
- Harms did fall (59 -> 52 vs baseline broad), but this happened alongside lower-than-baseline accuracy and first-split survival, so this is not a promotable final/default state.

## Recommendation
Keep this line as active but **not promoted**. Next pass should relax one knob at a time from the refined setting (start with `target_alignment_min` or `required_group_gap`) to recover non-zero, high-quality activation while preserving the harmed-case reduction.
