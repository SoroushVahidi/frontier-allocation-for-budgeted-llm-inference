# COHERE direct_reserve_semantic_frontier_v2 vs external_l1_max scale-up (supporting/diagnostic)

Status: **not executed on Wulver in this environment** (`sbatch` unavailable).

- Prepared batch script: `batch/run_cohere_direct_reserve_v2_vs_external_l1_scaleup_20260428T221840Z.sbatch`.
- Completed interactive readiness/smoke with live Cohere calls at tiny scale (`max-examples=2` per slice) to verify method resolution and API viability.
- Added method alias mapping so `direct_reserve_semantic_frontier_v2` resolves to runtime `direct_reserve_frontier_gate_v2` and `direct_reserve_semantic_frontier_v1` resolves to `direct_reserve_frontier_gate_v1` in real-model validator.
- Added post-processing script to normalize requested output filenames.

## Required questions (pending full batch completion)
1. Raw paired accuracy DR-v2 vs external_l1_max: **pending full run**.
2. Unique-example accuracy DR-v2 vs external_l1_max: **pending full run**.
3. Per-budget (4/6/8) result: **pending full run**.
4. Per-dataset result: **pending full run**.
5. Cost-normalized comparison: **pending full run**.
6. Pareto status: **pending full run**.
7. Unique example count used: **pending full run**.
8. Duplicate/cycle fallback slots: **pending full run**.
9. Methods excluded: **pending full run**.
10. Evidence tier: **supporting/diagnostic only until full batch + replication**.

## Local Codex partial validation update (2026-04-28)
- Wulver scale-up is prepared but **not submitted** from this environment.
- A local Codex partial validation was run on Cohere (smoke + partial bounded slice).
- Current local partial signal is unfavorable to `direct_reserve_semantic_frontier_v2` vs `external_l1_max` (paired delta negative on observed matched cases).
- Full conclusion requires completing/resuming the paired run, ideally with the prepared Wulver scale-up execution.
