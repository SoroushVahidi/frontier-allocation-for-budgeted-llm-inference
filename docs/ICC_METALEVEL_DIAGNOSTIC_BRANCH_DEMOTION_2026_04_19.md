# ICC metalevel refinement line: consolidated demotion summary (2026-04-19)

## Status classification (final)

This incumbent-challenger metalevel ICC refinement line is now classified as:
- **useful diagnostic branch**,
- **not the promoted main method**,
- **not permanently closed**, but requiring a **materially different hypothesis** before revival.

## Consolidated bounded sequence

### Pass A: selector refinement (same family)
Source: `docs/INCUMBENT_CHALLENGER_SELECTOR_REFINEMENT_STATUS_2026_04_19.md`

What improved:
- wrong-challenger behavior improved materially (`7 -> 2`).

What did not:
- overall remained below baseline (`accuracy 0.625 vs 0.75`, `wrong_commit_timing 2 vs 0`).

### Pass B: commit-interaction local refinement (same family)
Source: `docs/INCUMBENT_CHALLENGER_COMMIT_INTERACTION_REFINEMENT_STATUS_2026_04_19.md`

What improved:
- richer stop/continue diagnostics and cleaner local two-stage gate instrumentation.

What did not:
- near-tie continuation remained sticky in bounded run.
- family still below baseline on commit timing.

### Pass C: final near-tie single-point adjustment (same family)
Source: `docs/INCUMBENT_CHALLENGER_NEAR_TIE_SINGLE_POINT_FINAL_STATUS_2026_04_19.md`

One adjustment tested:
- `near_tie_weak_continue_value_cap` (single-point local override signal).

Final bounded outcome:
- baseline: accuracy `0.75`, wrong_commit_timing `0`.
- best pre-final local variant: accuracy `0.625`, wrong_commit_timing `2`, wrong_challenger `2`.
- final single-point adjusted: accuracy `0.75`, wrong_commit_timing `2`, wrong_challenger `1`.

Primary criterion was not met:
- wrong_commit_timing did **not** improve from `2` to `<=1`.

## Why this line is demoted

Demotion is evidence-based and narrow:
1. selector-side issue improved substantially,
2. but commit-timing bottleneck persisted after bounded commit-side and near-tie adjustments,
3. and final single-point pass still did not reduce wrong_commit_timing to target.

So this line remains a valuable diagnostic reference, but not the lead optimization direction.

## Exact demotion wording for collaborators

> The metalevel ICC refinement line is **demoted to diagnostic-branch status**. It is **not the promoted main method** for current roadmap decisions. Reopen only with a **materially different hypothesis** that directly addresses persistent wrong_commit_timing without another threshold-only local nudge.

## Reopening conditions (required)

This line may be revived only if a new proposal provides all of:
1. a materially different mechanism (not another small threshold retune),
2. a falsifiable prediction for wrong_commit_timing reduction,
3. bounded matched evidence that improves wrong_commit_timing to at least `<=1` on the same pilot slice while keeping wrong_challenger controlled,
4. no regression in accuracy below the current best local value.

## Related artifacts

- `docs/INCUMBENT_CHALLENGER_SELECTOR_REFINEMENT_STATUS_2026_04_19.md`
- `docs/INCUMBENT_CHALLENGER_COMMIT_INTERACTION_REFINEMENT_STATUS_2026_04_19.md`
- `docs/INCUMBENT_CHALLENGER_NEAR_TIE_SINGLE_POINT_FINAL_STATUS_2026_04_19.md`
- `outputs/data_consolidation_20260418/icc_diagnostic_branch_demotion_summary_20260419.json`
