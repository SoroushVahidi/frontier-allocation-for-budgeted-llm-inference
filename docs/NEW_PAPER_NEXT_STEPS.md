# New-paper next steps (non-heavy plan)

This plan is intentionally lightweight and keeps current infrastructure/results intact.

## Priority order

1. **Stabilize branch-scorer evidence (default path).**
   - Keep plain pairwise BT as current baseline.
   - Add targeted confidence calibration / uncertain-pair filtering checks.
   - Re-run the existing robustness grid only (no large expansion).

2. **Preserve external data as optional warm-start.**
   - Treat external datasets as auxiliary supervision.
   - Continue internal/repo-specific label generation for core evaluations.

3. **Tighten documentation after each pass.**
   - Update status + safe-claims notes.
   - Keep explicit “canonical vs exploratory” labels on new result notes.

4. **Expand real-model checks only after step (1).**
   - Use small controlled slices and matched budgets.
   - Avoid heavy runs until robustness trend is clearer.

## Recommended default baseline set for immediate comparisons

- `adaptive_relative_rank` (strong heuristic reference)
- `adaptive_bt_pairwise` (current strongest branch-scorer default)
- `adaptive_bt_pairwise_reliability` (promising exploratory)
- oracle upper bound (headroom context)

## Explicit non-goals for this pass

- No major redesign of the scientific problem.
- No broad benchmark explosion.
- No claims that exploratory variants are final winners.
