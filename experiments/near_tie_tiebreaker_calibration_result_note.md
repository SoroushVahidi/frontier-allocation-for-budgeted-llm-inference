# Near-tie tie-breaker calibration result note (new-paper, 2026-04-14)

This is a cheap, bounded calibration/stress-test pass on the existing two-stage architecture:
- Stage 1: baseline proxy BT scorer.
- Stage 2: selective near-tie tie-breaker for close top-2 only.

## Audit context used

Audited and reused:
- `scripts/run_new_paper_near_tie_tiebreaker.py`
- `experiments/scoring.py`
- prior outputs under `outputs/new_paper/near_tie_tiebreaker/...`
- near-tie pair outputs under `outputs/new_paper/near_tie_pairs/...`
- `experiments/near_tie_tiebreaker_result_note.md`

## Calibration run

- Output root: `outputs/new_paper/near_tie_tiebreaker_calibration/20260414T191525Z/`
- Near-tie pair artifacts: `outputs/new_paper/near_tie_pairs/20260414T191525Z/`

Sweep axes (bounded):
- `near_tie_margin`: 0.04 / 0.06 / 0.08 / 0.10
- tie-break train subset: `all_near_tie` vs `strict_margin`
- feature set: `compact`, `diff_only`, `diff_abs`
- tie-break model: logistic regression and decision stump
- regularization: light (`1e-4`, `1e-3`) for logistic

## Explicit answers

### Was the previous two-stage gain robust or fragile?
**Fragile in this calibration pass.**
All swept two-stage configs were below the local baseline controller row in this run.

### Which `near_tie_margin` region worked best?
`0.06` was the least harmful region on average in this sweep (smallest negative near-tie pair delta), but still not positive.

### Which lightweight tie-breaker worked best?
The **decision stump** (`margin=0.06`, compact features) was the least harmful overall among tested tie-breakers in this run.

### Can we improve near-tie slice without losing overall gain?
**Not yet in this sweep.**
Near-tie pair deltas remained negative for all tested configs (best was close to flat, but still negative).

### Is two-stage architecture now the best lightweight improvement branch?
**Not confirmed by this calibration pass.**
Given instability and regression here, keep it as a diagnostic branch, not default.

### What default two-stage settings (if any)?
If forced to keep a default for further debugging, use the least harmful config from this run:
- decision stump
- `near_tie_margin=0.06`
- compact feature set
- all near-tie training subset

But this should be considered provisional and not production-default.

## Conservative conclusion

- The architecture is still plausible, but gains were **not robust** under this cheap stress test.
- Diagnostics are currently stronger than the method improvement itself.
- Recommended next bounded step: keep architecture fixed, add 2-3 seed repeats and tie-activation-rate diagnostics before deciding to keep/drop.
