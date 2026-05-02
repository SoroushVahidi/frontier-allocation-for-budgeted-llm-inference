# L1 Loss Decomposition — Local status

- Method-wise partial run `20260502T040119Z` had 128 records, only `external_l1_max`, and 0 paired cases.
- Paired-case batch mode exists.
- Prior best_available paired-batch attempt (`20260502T045453Z`) did not finish one triple in the interactive window.
- New smoke policies implemented: `drv2_only_diagnostic`, `selection_fix_only`, `best_available`.

## Smoke result (latest)
- Stamp: `20260502T051323Z`
- Policy: `drv2_only_diagnostic`
- Paired rows completed: 0
- Claim safety: `diagnostic_plumbing_only`
- Interpretation: plumbing attempt still blocked by runtime window before first complete case.

EXP-L1-DECOMP-100 remains open until 100 best_available paired cases complete.
