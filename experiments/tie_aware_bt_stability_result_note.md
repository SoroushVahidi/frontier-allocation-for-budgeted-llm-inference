# Tie-aware BT stability + calibration audit result note (new-paper track)

Date: 2026-04-14  
Run: `outputs/new_paper/tie_aware_bt_stability/20260414T202738Z`

## Scope
Bounded multi-seed follow-up focused on the existing tie-aware BT pipeline (no heavy training, no API eval).

## Setup (cheap, matched)
- Seeds: 71, 72, 73, 74
- Ranking episodes per seed: 130
- Controller eval subset per seed: 18
- Compared methods:
  - proxy BT baseline
  - tie-aware Davidson (`tie_or_uncertain`)
  - tie-aware Rao-Kupper (`tie_or_uncertain`)
  - hard-oversample + two-stage references (context)
  - oracle reference row
- Small Rao-Kupper sweep on seed 71:
  - tie supervision: `none`, `tie_or_uncertain`, `strict_tie`
  - min-confidence: `0.0`, `0.1`, `0.2` (small calibration perturbation)

## Main findings
- **Rao-Kupper was the strongest tie-aware variant overall** on controller accuracy mean.
- Rao-Kupper beat proxy BT on controller accuracy in **3/4 seeds**, but variance was non-trivial (fragile/mixed).
- **Near-tie slice did not improve** for Rao-Kupper on average; it remained below proxy BT.
- Sweep result: best run-local setting was **Rao-Kupper + `tie_or_uncertain` + min_confidence=0.0**.
- `none` and `strict_tie` behaved similarly here (as expected with effectively zero exact ties in this dataset build).

## Key question: why overall up but near-tie not up?
- Rao-Kupper changed only a small fraction of pair decisions overall, but those changes were often near-tie and **quality-mixed across seeds**.
- Regime slices indicate gains are concentrated in selected regimes (seed-dependent), consistent with **global/partial calibration effects** rather than a robust fix to hardest near-tie ambiguity.

## Required decision answers
- Was Rao-Kupper gain robust? **Partially; positive but fragile (likely not yet stable enough for default).**
- Which tie-aware variant is best? **Rao-Kupper.**
- Which tie supervision mode is best? **`tie_or_uncertain` (this bounded sweep).**
- Should tie-aware BT remain main lightweight experimental branch? **Yes (experimental branch), but not default.**
- Why helps overall without hardest near-tie gains? **Selective calibration/regime effects, not a universal near-tie fix.**
- Should proxy BT remain default? **Yes, proxy BT should remain the default baseline for now.**

## Conservative conclusion
Keep Rao-Kupper tie-aware BT as the next lightweight experimental branch to track, but do **not** promote it over proxy BT yet.
