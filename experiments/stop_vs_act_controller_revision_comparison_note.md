# Stop-vs-act targeted revision bounded comparison note

## Revision tested
- Baseline setup: `downweight`
- Revised setup: `downweight_nonpositive` (uncertain STOP downweight only; uncertain ACT kept at full weight)
- Grid: seeds `31,32,33`, budgets `10,14`
- Episodes per cell: `700`, eval episodes per run: `280`

## Bounded result summary
- Baseline vs heuristic win/loss/tie: `{'wins': 4, 'losses': 2, 'ties': 0, 'total': 6}`.
- Revised vs heuristic win/loss/tie: `{'wins': 5, 'losses': 1, 'ties': 0, 'total': 6}`.
- Mean margin vs heuristic: baseline `+0.0232`, revised `+0.0315`.
- Revised minus baseline delta on margin vs heuristic: mean `+0.0083`, std `0.0215`, W/L/T `{'wins': 4, 'losses': 2, 'ties': 0, 'total': 6}`.

## Conservative interpretation
- Treat this as bounded evidence only.
- If revised beats baseline in both mean and win/loss counts with reduced failures, it is a lightweight improvement worth carrying forward.
- If not, keep current direction mixed and prioritize label-quality revisions.

## Recommendation
- **keep but focus next on label construction**.
