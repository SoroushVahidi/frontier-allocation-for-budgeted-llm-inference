# Cohere full accuracy Codex-local progress (2026-04-29)

Timestamp: `20260429T_COHERE_FULL_ACCURACY_CODEX`

## Scope and constraints
- Provider: Cohere only.
- Method set: `strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3`.
- Excluded diagnostic-only method: `direct_reserve_semantic_frontier_v2_thresholded_ordered`.
- Codex-local execution only (no Slurm/Wulver/Cursor).

## Validation
- `--validate-methods-only` executed with the full method set; `validated_rows=36`, `bad_rows=0`.

## Chunk plan
- Plan file: `outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv`
- Planned chunks: 216 (2 datasets × 4 budgets × 3 seeds × 9 methods).
- Target scored per chunk: 100.

## Real chunks executed in this session
Execution command (batch):
```bash
for id in 6 4 1 2 5 7 8 9 3; do
  python scripts/run_cohere_chunk.py \
    --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv \
    --chunk-id "$id" \
    --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX \
    --max-walltime-minutes 20
done
```

Observed: the run advanced through multiple methods for `openai/gsm8k`, budget `2`, seed `11`, with completed 100-example runs logged for at least `strict_gate1_cap_k6` in current persisted slice summary.

## Current persisted status snapshot
From `chunk_progress_status.csv` after rerunning status/aggregate:
- completed: 1
- incomplete: 0
- failed: 0
- planned_not_started: 215

Completed chunk ID currently reflected by persisted `slice_summary.csv`: `2`.

## Completed-slice metrics currently persisted
From `outputs/cohere_real_model_cost_normalized_validation_20260429T_COHERE_FULL_ACCURACY_CODEX/slice_summary.csv`:

| dataset | budget | seed | method | scored | accuracy | total_tokens | estimated_cost | failures | skips |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| openai/gsm8k | 2 | 11 | strict_gate1_cap_k6 | 100 | 0.53 | 47708 | 0.239784 | 0 | 0 |

## Pairwise vs external_l1_max
- No persisted matched pairwise row is currently available in `pairwise_comparisons.csv` for this snapshot.

## Important operational limitation discovered
The current underlying runner output behavior for repeated single-method invocations under one timestamp appears to persist only the latest method row in `slice_summary.csv` for the timestamp directory, which prevents durable accumulation of multi-method chunk progress across sequential chunk IDs using a shared timestamp.

This is a reliability limitation for long resumable chunk campaigns and should be addressed before claiming full-grid progress.

## Safe continuation command
Use the same plan and timestamp to continue, rerunning status and aggregate after each batch:
```bash
python scripts/status_cohere_chunk_progress.py \
  --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv \
  --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX

python scripts/aggregate_cohere_chunks.py \
  --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv \
  --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX
```

Next planned chunk IDs from current status begin with: `1,3,4,5,6,7,8,9,10,...`.

## Evidence boundary
These are diagnostic/supporting real-model outputs and are not manuscript claims.


## Accumulation root cause and fix
- Root cause: `run_cohere_chunk.py` invoked the core runner for a single `(dataset,budget,seed,method)` slice, and the core runner rewrote `slice_summary.csv` for only the CLI-provided slice set on each invocation.
- Recovery: earlier spent Cohere calls were recoverable from `per_example_records.jsonl` (424 records found across 5 method slices).
- Fix: after each chunk run, `run_cohere_chunk.py` now executes a second `--summarize-only` pass over the *full chunk plan scope* (all datasets/budgets/seeds/methods from plan) so summary CSVs are rebuilt durably from the full per-example ledger.
- Regenerated summaries via summarize-only and restored completed chunk accounting (`1,2,4,6` completed; `5` still incomplete as of last status snapshot).


## Continued batch run (same timestamp, post-fix)
- Ran status before batch: completed=4, incomplete=212, failed=0.
- Ran chunk batch command: `for id in 5 3 7; do python scripts/run_cohere_chunk.py --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv --chunk-id $id --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX --max-walltime-minutes 20; done`.
- Observed durable accumulation after rerun of status/aggregate: completed=6, incomplete=210, failed=0.
- Newly completed chunk IDs in this session: `3` and `5` (with prior completed `1,2,4,6` still preserved).
- Chunk `7` was started and remained incomplete at snapshot time.

### Completed-slice table (diagnostic, partial grid)
| dataset | budget | seed | method | scored | accuracy | total_tokens | estimated_cost_usd | failures | skips |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| openai/gsm8k | 2 | 11 | external_l1_max | 100 | 0.68 | 48573 | 0.268263 | 0 | 0 |
| openai/gsm8k | 2 | 11 | direct_reserve_semantic_frontier_v2 | 100 | 0.50 | 96881 | 0.504507 | 0 | 0 |
| openai/gsm8k | 2 | 11 | strict_f3 | 100 | 0.51 | 48724 | 0.247392 | 0 | 0 |
| openai/gsm8k | 2 | 11 | strict_gate1_cap_k6 | 100 | 0.53 | 47708 | 0.239784 | 0 | 0 |
| openai/gsm8k | 2 | 11 | direct_reserve_semantic_frontier_v2_selection_fix_v1 | 100 | 0.56 | 97296 | 0.509436 | 0 | 0 |
| openai/gsm8k | 2 | 11 | strict_f2 | 100 | 0.56 | 47672 | 0.244764 | 0 | 0 |

### Pairwise deltas currently available
- `strict_f3_vs_external_l1_max`: mean delta = `-0.17` on `100` matched examples.
- `best_frontier_vs_external_l1_max`: mean delta = `-0.12` on `100` matched examples.

This run remains diagnostic and incomplete (not all 216 chunks complete).


## Follow-up attempt to complete matched GSM8K(2,11) residual methods
- Recreated missing plan file `outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv` (it was not present in this environment snapshot).
- Ran status first; with missing historical `per_example_records.jsonl` for this timestamp in current environment snapshot, status initialized as planned.
- Mapped chunk IDs for residual methods on `(dataset=openai/gsm8k,budget=2,seed=11)`: `tale=7`, `s1=8`, `self_consistency_3=9`.
- Ran bounded batch: `for id in 7 8 9; do python scripts/run_cohere_chunk.py --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv --chunk-id $id --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX --max-walltime-minutes 20; done`.
- At snapshot time: `tale` reached 100/100 complete; `s1` had begun scoring but was not complete in persisted status; `self_consistency_3` not yet reached in-loop snapshot.

### Current slice state for openai/gsm8k,budget=2,seed=11
- complete: `tale`
- incomplete: `strict_f3, strict_gate1_cap_k6, strict_f2, direct_reserve_semantic_frontier_v2, direct_reserve_semantic_frontier_v2_selection_fix_v1, external_l1_max, s1, self_consistency_3`

### Diagnostic note
This environment snapshot did not contain prior historical `per_example_records.jsonl` state that earlier runs referenced, so only newly executed records in this session were available for status/aggregate recomputation.


## Cross-session persistence policy update
- Root cause of disappearing progress across Codex tasks: real-model run artifacts under `outputs/cohere_real_model_cost_normalized_validation_*` are ignored by default (`outputs/*` in `.gitignore`) unless explicitly whitelisted and committed.
- Historical completed slices disappeared in later tasks because local task filesystem snapshots did not retain untracked ignored output files (`per_example_records.jsonl`, `slice_summary.csv`, etc.).
- New durable source: compact ledger CSV exported from raw per-example JSONL with only non-sensitive summary fields required for status/aggregate/pairwise rebuild.
- Export command: `python scripts/export_compact_cohere_ledger.py --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX --output-root outputs`.
- Durable copy path (tracked): `outputs/cohere_compact_ledgers/20260429T_COHERE_FULL_ACCURACY_CODEX_compact_per_example_ledger.csv`.
- In this session, only currently present records were exportable (`120` rows); earlier missing records were not recoverable because they were absent from local filesystem snapshot.
