# Defer calibration + label-audit pass (2026-04-19)

## What likely caused decomposed defer collapse
Primary issue appears to be **label scarcity / degenerate labels** in the decomposed target regime (`defer_target_mode=value_aware`) rather than threshold miscalibration.

In run `value_aware_defer_audit_20260419_pass2`:
- decomposed defer positives are `0/220` overall, and `0/27` on test,
- near-tie defer positives are also `0` (with nonzero near-tie count),
- threshold sweep across 0.05..0.95 still yields zero accepted coverage.

This indicates the model is trained/evaluated on an effectively empty defer-positive target under this bounded setting.

## What was implemented
- Added label-audit diagnostics in learning-table construction and eval outputs:
  - total/positive/negative defer labels,
  - class balance,
  - counts by ambiguity bucket,
  - counts by best-action metadata,
  - counts by delta-expand-commit and regret buckets,
  - near-tie defer-positive counts.
- Added per-example defer-score artifact for decomposed evaluation:
  - state/example id, gold defer label, predicted defer probability, predicted class,
  - ambiguity bucket, delta-expand-commit, regret, best-action metadata.
- Added threshold sweep diagnostics for defer evaluation:
  - accepted-only accuracy, coverage, accepted count, defer precision/recall/F1 per threshold.
- Added conservative threshold-selection option:
  - `fixed` (default), or
  - `val_defer_f1` selected on validation split only (no test leakage).

## Result after this pass
- Decomposition did **not** recover nonzero defer coverage in this bounded run.
- Diagnostics show collapse is dominated by **defer-label emptiness** in decomposed targets, not by a single bad threshold.
- Near-tie defer behavior remains unhelpful in this run.

## Conclusion
**Partially fixed (diagnostics/calibration visibility fixed; decomposition quality not fixed).**

Next minimal step should be to revisit decomposed defer label construction thresholds/semantics so positive defer labels are present in train/val/test without leakage, then re-run the same bounded comparison.
