# Claim-Evidence Map (Post Evaluation-Science Rewrite)

Updated 2026-07-24 after manuscript rewrite. Primary numerical sources:

- Pooled-4 / FTA: `outputs/rejection_risk_offline_campaign_20260724T000000Z/p1_majority_analysis/`
- FIX-2/4: `.../p2_fix24_ablation/`
- Repair: `.../p6_repair_quantification/`
- Chronology: `.../p7_overfitting_audit/`
- 4×4 matrix: `outputs/final_4x4_matrix_conclusive_audit_20260717T223631Z/`
- Compute: corrected compute-metrics reconstruction archived in the private working record; summarized in manuscript resource-accounting tables.

See also `outputs/rejection_risk_offline_campaign_20260724T000000Z/CLAIM_VERIFICATION_POST_REWRITE.md` for the full claim-by-claim table.

| Claim | Value | Source |
|---|---|---|
| Completed cells | 15/16 | conclusive audit `summary.json` |
| Blocked cell | Fireworks×GPQA `BLOCKED_PROTOCOL_NONCONVERGENCE` | `blocked_cells.csv` |
| n | 3394 | P1 + compute CSV |
| B, seed | 6, 71 | conclusive audit README |
| FTA / Pooled-4 | 65.00% / 66.53%; −1.53pp; p=0.00027; 73/125/3196; ≥13/15 | `p1_majority_analysis/summary.json` |
| Frontier pooled | 64.11% (2176/3394) | P1 per-example |
| FTA vs Frontier | 8/6/1 | conclusive audit |
| FIX-2 / FIX-4 switches | 606 / 21; overlap 0 | `p2_fix24_ablation/summary.json` |
| Azure FIX-2 harm | 2/18 and 7/31 | selector_behavior / gate table |
| Repair Frontier differs | 151 | `p6_repair_quantification/summary.json` |
| External winner flips | 0 | same |
| Cost ratios | Frontier/L1 1.22–2.56×; Frontier/TALE 1.13–2.93× | corrected compute CSV |
| Discovery–delta r | −0.185 | selector_behavior_by_cell.csv |
| Azure×GPQA FTA | offline replay | CANONICAL_STATE / conclusive audit |
| TALE citation | Han et al., arXiv:2412.18547 | refs.bib (corrected) |
| Frontier controller identity (correction, 2026-07-24) | Every promoted Frontier result executes `DirectReserveFrontierGateV2Controller` (runtime alias `direct_reserve_frontier_gate_v2`) with gate thresholds `(gate_top_support_threshold, gate_top2_gap_threshold, gate_entropy_threshold)=(2.0,2.0,-1.0)`. Since top support is bounded in [0,1], the early-commit gate is unsatisfiable at 2.0, so every reported decision executes challenger expansion, never early commit. Manuscript previously stated `(0.75,0.50,0.55)` and described a confidence-triggered gate; corrected in abstract (`main.tex`), `01_introduction.tex`, `02_related_work.tex`, `04_method.tex`, and `appendix.tex` (Path A: prose corrected to match the executed algorithm; no data, numbers, or reported accuracies changed). The value `(0.70,0.35,0.78)`, registered under the same manuscript-facing method name in `experiments/semantic_diversity_diagnostic_strategies.py`, was never on the executed code path and is not the source of any reported result. | `outputs/repository_consolidation_audit_20260724T220807Z/FRONTIER_THRESHOLD_PROVENANCE_AUDIT.md`; `experiments/frontier_matrix_core.py:1358-1392`; `scripts/run_cohere_real_model_cost_normalized_validation.py:76,1574-1597` |
