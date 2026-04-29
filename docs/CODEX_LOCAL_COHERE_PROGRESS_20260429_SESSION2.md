# Codex-local Cohere progress report (session 2, 2026-04-29)

## Scope and constraints
- Method set used (validated runnable only): `strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3`.
- Explicitly excluded: `direct_reserve_semantic_frontier_v2_thresholded_ordered` (diagnostic-only, not runtime-present in `build_frontier_strategies(...)`).
- Timestamp: `20260429T_CODEX_LOCAL_REAL`.

## Pre-run status snapshot
From `outputs/cohere_real_model_cost_normalized_validation_20260429T_CODEX_LOCAL_REAL/chunk_progress_status.csv` before this continuation block:
- Total planned chunks: 216
- Completed: 0
- Incomplete: 0
- Failed: 0
- Planned: 216

## Chunks executed in this session
Attempted with bounded walltime using `scripts/run_cohere_chunk.py`:
- chunk `6` (`openai/gsm8k`, budget `2`, seed `11`, method `external_l1_max`) in resumed mode.

Observed behavior:
- API calls succeeded repeatedly and produced additional per-example scored records.
- Execution was bounded/interrupted before the slice hit target scored count (100), so no slice finalized in this session.

## Post-run status snapshot
After `--summarize-only`, status, and aggregate refresh:
- Total planned chunks: 216
- Completed: 0
- Incomplete: 216
- Failed: 0
- Planned: 0

## Next chunk IDs to run
Priority sequence to maximize early matched evidence on same slices:
1. `6` then `4` for (`openai/gsm8k`, budget `2`, seed `11`) to pair `external_l1_max` and `direct_reserve_semantic_frontier_v2`.
2. Then `1`, `2`, `7`, `8`, `9` to add strict/internal + external comparators for the same slice.
3. Then repeat the same ordering for seeds 13 and 17 (`15/13`, `24/22`, then corresponding strict/tale/s1/sc3 IDs).

## Completed-slice-only results
- No completed slices yet at target scored count 100.
- Therefore no completed-slice accuracy/cost summary is reported in this session.

## Artifacts updated
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_CODEX_LOCAL_REAL/chunk_progress_status.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_CODEX_LOCAL_REAL/codex_per_slice_finality.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_CODEX_LOCAL_REAL/codex_method_summary_final_only.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_CODEX_LOCAL_REAL/codex_pairwise_vs_external_l1_max.csv`
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_CODEX_LOCAL_REAL/codex_failed_or_incomplete_slices.csv`

Diagnostic-only progress; no manuscript claim updates.
