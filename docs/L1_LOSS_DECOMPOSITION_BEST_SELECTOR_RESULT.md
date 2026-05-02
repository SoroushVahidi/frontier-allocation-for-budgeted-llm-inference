# L1 Loss Decomposition (Best Selector) — Status Update

- Prior method-wise partial run (`20260502T040119Z`) produced 128 records but 0 paired cases due to missing non-L1 lanes in recorded artifacts.
- Unpaired diagnostic written to:
  `outputs/l1_loss_decomposition_best_selector_20260502T040119Z/salvaged_decomposition/unpaired_records_diagnostic.json`.
- Paired-case batch mode was added to `scripts/run_l1_loss_decomposition_for_best_selector.py` so each case is executed as L1 -> DR-v2 -> selector and flushed incrementally.

Latest paired-batch attempt: `20260502T045453Z`
- Output dir: `outputs/l1_loss_decomposition_best_selector_20260502T045453Z/`
- Result: runtime blocker before first complete triple in this interactive window.
- Claim safety: `incomplete_not_evidence`.
- EXP-L1-DECOMP-100 remains open.
