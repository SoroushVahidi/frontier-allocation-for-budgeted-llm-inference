# Performance Evaluation Claim-Evidence Map

Updated for Pass 6 supplementary packaging.

This map records the manuscript-facing evidence boundary. It is a routing document for frozen
records and audit manifests, not an instruction to run new experiments or live API calls.

## Primary Numerical Sources

- Pooled-4 / FTA identical-pool analysis: `p1_majority_analysis/`.
- FIX-2/FIX-4 gate analysis: `p2_fix24_ablation/`.
- Repair quantification: `p6_repair_quantification/`.
- Researcher-adaptation chronology: `p7_overfitting_audit/`.
- 4x4 provider-by-dataset matrix: final conclusive matrix audit, 2026-07-17.
- Compute accounting: corrected compute-metrics reconstruction CSV.
- Canonical state: `docs/current/CANONICAL_STATE.md`.

## Manuscript Claims

| Claim | Value | Evidence route |
| --- | --- | --- |
| Completed cells | 15/16 | Final conclusive matrix audit summary. |
| Blocked cell | Fireworks x GPQA-Diamond `BLOCKED_PROTOCOL_NONCONVERGENCE` | Blocked-cell audit and canonical state. |
| Paired examples | 3394 | Majority-analysis summary and compute reconstruction. |
| Nominal budget and seed | B=6, seed=71 | Matrix audit README and canonical state. |
| FTA vs Pooled-4 | 65.00% vs 66.53%; McNemar p=0.00027 | Majority-analysis summary. |
| FTA/Pooled-4/tie discordants | 73/125/3196 | Majority-analysis summary. |
| Frontier pooled | 2176/3394 (64.11%) | Per-example majority-analysis records. |
| FTA vs Frontier cell signs | 8/6/1 | Final conclusive matrix audit. |
| FIX-2/FIX-4 switches | 606/21; overlap 0 | Gate-ablation summary. |
| Azure FIX-2 transfer harm | 2/18 and 7/31 rescue/regression patterns | Provider gate table. |
| Repair Frontier differs | 151 rows | Repair quantification summary. |
| External winner flips under uniform repair | 0 | Repair quantification summary. |
| Successful calls | 2.78 uncorrected to 5.38 reconstructed | Corrected compute reconstruction. |
| Discovery-delta correlation | Pearson r=-0.185 | Selector-behavior by-cell table. |
| Azure x GPQA FTA | Offline replay | Canonical state and conclusive audit. |

## Boundary Notes

- Oracle rows are upper bounds only.
- Gold labels are offline-only and are not runtime selector features.
- D6 diagnostic labels are not runtime selector features.
- No paid/live API calls are required for the packaged replay boundary.

