# Tie-aware BT result note (new-paper track)

Date: 2026-04-14  
Run: `outputs/new_paper/tie_aware_bt/20260414T200450Z`

## Goal
Run a bounded, cheap tie-aware ranking comparison against the current proxy BT baseline and recent diagnostic alternatives.

## What was tested
- Baseline proxy BT (`objective=bt`)
- Tie-aware Davidson-style BT (`objective=davidson`, `tie_supervision=tie_or_uncertain`)
- Tie-aware Rao-Kupper-style BT (`objective=raokupper`, `tie_supervision=tie_or_uncertain`)
- Hard-pair oversampling reference (near-tie score-gap based)
- Two-stage tie-breaker reference (baseline BT + lightweight near-tie tie-break logistic)

## Main observations (this run)
- Near-tie pair slice: **both tie-aware variants were worse than baseline proxy BT**.
- Overall controller accuracy: Rao-Kupper tie-aware improved over baseline in this single bounded run.
- However, the strongest overall performer in this run was still a diagnostic alternative (hard-pair oversampling), with two-stage also beating baseline on near-tie pair accuracy.

## Required answers (run-local)
- Does tie-aware BT handle near-tie pairs better than plain BT? **No (in this run).**
- Does it improve the near-tie slice? **No (in this run).**
- Does it preserve/improve overall controller accuracy? **Rao-Kupper yes; Davidson no.**
- Better than hard-pair oversampling? **No.**
- Better than two-stage tie-breaker branch? **No.**
- Should tie-aware BT be next lightweight branch? **Keep as diagnostic-only for now; baseline proxy BT remains safest default.**

## Caution
Tie labels used here are proxy-derived (`tie_or_uncertain`) and should not be interpreted as oracle human tie truth.
