# Codex-local resumable Cohere experiment runbook (2026-04-29)

Validated runnable methods only:
`strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3`.

Excluded from live Cohere runtime: `direct_reserve_semantic_frontier_v2_thresholded_ordered` (diagnostic-only; not runtime-present in `build_frontier_strategies(...)`).

## 1) Validate exact method list (required)
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260429T_CODEX_LOCAL_VALIDATE \
  --providers cohere \
  --datasets openai/gsm8k,HuggingFaceH4/MATH-500 \
  --budgets 2,4,6,8 \
  --seeds 11,13,17 \
  --methods strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3 \
  --validate-methods-only
```
Require `bad_rows=0`.

## 2) Create plan
```bash
python scripts/plan_cohere_real_model_chunks.py --chunk-plan outputs/codex_local_chunk_plan_20260429.csv
```

## 3) Run one chunk (bounded)
```bash
python scripts/run_cohere_chunk.py --chunk-plan outputs/codex_local_chunk_plan_20260429.csv --chunk-id 1 --timestamp 20260429T_CODEX_LOCAL_REAL --max-walltime-minutes 20
```

## 4) Check progress
```bash
python scripts/status_cohere_chunk_progress.py --chunk-plan outputs/codex_local_chunk_plan_20260429.csv --timestamp 20260429T_CODEX_LOCAL_REAL
```

## 5) Aggregate completed slices only
```bash
python scripts/aggregate_cohere_chunks.py --chunk-plan outputs/codex_local_chunk_plan_20260429.csv --timestamp 20260429T_CODEX_LOCAL_REAL
```

Resume by re-running chunk IDs with `--resume` behavior inherited from the core runner; completed examples are not duplicated.


## 6) Dry run a chunk (no API call)
```bash
python scripts/run_cohere_chunk.py --chunk-plan outputs/codex_local_chunk_plan_20260429.csv --chunk-id 1 --timestamp 20260429T_CODEX_LOCAL_REAL --dry-run
```

## 7) Status/aggregation semantics
- `planned_not_started`: no matching slice row exists yet.
- `incomplete`: matching row exists but scored count is not exactly target.
- `completed`: scored count exactly equals planned target for that exact `(dataset,budget,seed,method)` slice.
- `failed`: matching row exists with zero scored and non-zero failures.
- Pairwise availability is keyed by `(provider,dataset,seed,budget,method_a)` vs `external_l1_max`.
- Aggregation writes valid header-only CSVs when source files are empty/missing.
- Bootstrap CI fields in chunk aggregate are intentionally unavailable unless matched per-example differences are supplied in a future artifact.

No Wulver/Slurm environment is required for this Codex-local chunk workflow.

- Persistence safety: `run_cohere_chunk.py` now runs a post-chunk summarize-only rebuild over all plan dimensions, so `slice_summary.csv`/`method_summary.csv`/`pairwise_comparisons.csv` accumulate durably from `per_example_records.jsonl`.
- If summaries ever look stale, run:
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py --timestamp <TS> --providers cohere --datasets <all datasets> --budgets <all budgets> --seeds <all seeds> --methods <all methods> --target-scored-per-slice 100 --summarize-only
```


## 8) Persist cross-session compact ledger (recommended)
```bash
python scripts/export_compact_cohere_ledger.py --timestamp <TS> --output-root outputs
cp outputs/cohere_real_model_cost_normalized_validation_<TS>/compact_per_example_ledger.csv \
   outputs/cohere_compact_ledgers/<TS>_compact_per_example_ledger.csv
```
`status_cohere_chunk_progress.py` and `aggregate_cohere_chunks.py` now rebuild from `compact_per_example_ledger.csv` when raw `slice_summary.csv` is missing.
