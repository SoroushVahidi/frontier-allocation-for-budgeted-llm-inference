# Incumbent-challenger near-tie single-point final status (2026-04-19)

## Purpose

Final bounded single-point local refinement inside the same metalevel ICC family, targeting near-tie stop/continue stickiness.

## One local adjustment tested

Added one near-tie stop/continue override signal:
- `near_tie_weak_continue_value_cap`

Behavior (enabled only when cap > 0):
- in near-tie states,
- with low remaining budget,
- challenger not plausible,
- and weak best-continue value (`best_expand_delta <= cap`),
- allow stop/continue gate to treat residual near-tie hesitation as commit-favorable.

No new family, no sweep, selector parameters held fixed.

## Bounded setup

- dataset: `openai/gsm8k`
- subset size: `8`
- seed: `11`
- budget: `6`
- compared:
  1. baseline
  2. current best local family variant
  3. near-tie single-point adjusted variant

## Bounded results

- Baseline: accuracy `0.75`, wrong_commit_timing `0`
- Current best local family: accuracy `0.625`, wrong_commit_timing `2`, wrong_challenger `2`
- Near-tie single-point adjusted: accuracy `0.75`, wrong_commit_timing `2`, wrong_challenger `1`

Additional diagnostics:
- near_tie_continuation_rate stayed `1.0` for all compared methods.
- near_tie_false_continue_count stayed `0` in this bounded run.
- mean best-continue on baseline-commit / refined-continue states:
  - current best: `0.0323`
  - single-point adjusted: `0.0269`

## Interpretation (conservative)

- Primary success criterion was **not met**: wrong_commit_timing did **not** improve from `2` to `<=1`.
- Secondary criterion met: wrong_challenger remained `<=2` (improved to `1` in adjusted variant).
- Tertiary criterion met: accuracy did not fall below `0.625`.
- However, the core commit-timing bottleneck remains unresolved in this bounded slice.

## Recommendation after final pass

Demote this ICC commit-side line from active optimization priority.
- Keep artifacts for reference.
- Prefer switching effort to a different validated line unless a new hypothesis (not another threshold nudge) is introduced.

## Artifacts

- `outputs/incumbent_challenger_near_tie_single_point_refinement_20260419/summary.json`
- `outputs/incumbent_challenger_near_tie_single_point_refinement_20260419/near_tie_single_point_diagnostics.json`
- `outputs/incumbent_challenger_near_tie_single_point_refinement_20260419/per_example_results.jsonl`
