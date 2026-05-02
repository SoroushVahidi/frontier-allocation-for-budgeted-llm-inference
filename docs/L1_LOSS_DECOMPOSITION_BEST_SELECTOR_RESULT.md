# L1 Loss Decomposition — Local status

- Method-wise run `20260502T040119Z` produced 128 records with only L1 lane, so paired cases were 0.
- Paired-case batch mode was added, but fastest paired smoke still yielded 0 paired rows (`20260502T051323Z`).
- Lane-level checkpoint/resume plumbing was added to preserve lane progress across short sessions.

## Latest lane-smoke (L1-only)
- Stamp: `20260502T052744Z`
- Policy: lane-only `external_l1_max`
- Result: no completed paired decomposition row; runtime diagnostics/summaries emitted.
- Claim safety: `diagnostic_lane_only` / `incomplete_not_evidence` for scientific claim purposes.

EXP-L1-DECOMP-100 remains open. Full result needs longer-lived runner (cloud/background/Wulver-like environment).
