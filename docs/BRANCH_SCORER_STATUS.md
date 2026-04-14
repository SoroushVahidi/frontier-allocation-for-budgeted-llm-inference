# Branch-scorer status and sequence (new-paper track)

This note organizes branch-scorer development into a practical sequence.

## Development sequence

1. **Basic learned scalar branch scorer (early v-lines).**
   - Learned from weak/static-style targets.
   - Main lesson: target misalignment limits controller gains.

2. **Continuation/progress-oriented scalar targets (v3 and related).**
   - Better local alignment than static promise.
   - Competitive, but not a robust universal winner.

3. **Ordered-history feature expansion + pairwise BT training.**
   - Shift from pointwise approximation to pairwise preference signal.
   - Current strongest default direction.

4. **Reliability-aware BT variants.**
   - Motivation: not all pair labels are equally trustworthy.
   - Outcome so far: promising in some settings, mixed overall.

5. **External warm-start variants.**
   - External supervision as initialization/regularization.
   - Small gains possible, but not a replacement for internal supervision.

6. **Pairwise diagnostic audits.**
   - Exposes confidence-range and proxy-alignment limitations.
   - Supports focused non-heavy next steps.

## Current default and recommendations

- **Default baseline for branch-scorer line:** plain `adaptive_bt_pairwise`.
- **Strong heuristic anchor:** `adaptive_relative_rank`.
- **Main lightweight experimental branch:** tie-aware Rao-Kupper BT (`adaptive_bt_pairwise_tie_aware_raokupper`), currently tracked with matched bounded audits.
- **Promising but not default:** reliability-weighted BT and external warm-start variants.
- **Diagnostic utility:** pairwise diagnostic pipeline should be run before heavier expansion.

## Conservative switch policy (proxy BT -> Rao-Kupper)

- Keep `adaptive_bt_pairwise` as default unless **independent matched reruns** show Rao-Kupper is consistently positive.
- Promote Rao-Kupper only when all of the following hold in bounded matched audits:
  1. positive mean controller delta vs proxy BT,
  2. wins exceed losses across seeds (not just one lucky run),
  3. near-tie slice is at least non-regressing on average,
  4. result is reproduced on a fresh seed set.
- If any condition fails, keep proxy BT default and keep Rao-Kupper as experimental-leading branch.

## Canonical vs exploratory labels

- Canonical (new-paper internal default):
  - plain pairwise BT line + robustness checks.
- Exploratory:
  - reliability-filtered BT,
  - external warm-start combinations,
  - additional confidence heuristics not yet robust.
- Historical/contextual:
  - early static/weak target notes retained for negative-result provenance.

## Notes index (where details live)

- `experiments/branch_scorer_v3_result_note.md`
- `experiments/bt_pairwise_branch_scorer_result_note.md`
- `experiments/bt_reliability_weighted_branch_scorer_result_note.md`
- `experiments/external_warmstart_branch_scorer_result_note.md`
- `experiments/pairwise_diagnostic_audit_result_note.md`
- `docs/learned_scorer_lessons_2026-04-13.md`
