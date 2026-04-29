# Codex-local resumable Cohere experiment runbook (2026-04-29)

**Status: diagnostic (active operational runbook).**

Validated runnable methods:
`strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3`

Excluded diagnostic-only method:
`direct_reserve_semantic_frontier_v2_thresholded_ordered` (not runtime-present in live `build_frontier_strategies(...)`).

## Durable data policy
- Durable continuation source: compact ledger under `outputs/cohere_compact_ledgers/`.
- Raw `per_example_records.jsonl` inside ignored `outputs/cohere_real_model_cost_normalized_validation_*` folders is non-durable unless exported.

## Script map (current canonical script names)
- `scripts/plan_cohere_real_model_chunks.py`
- `scripts/run_cohere_chunk.py`
- `scripts/status_cohere_chunk_progress.py`
- `scripts/aggregate_cohere_chunks.py`
- `scripts/export_compact_cohere_ledger.py`

## Next Action (exact continuation workflow)
```bash
python scripts/status_cohere_chunk_progress.py --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX && \
python scripts/run_cohere_chunk.py --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv --chunk-id <MISSING_CHUNK_ID> --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX --max-walltime-minutes 20 && \
python scripts/export_compact_cohere_ledger.py --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX --output-root outputs && \
python scripts/status_cohere_chunk_progress.py --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX && \
python scripts/aggregate_cohere_chunks.py --chunk-plan outputs/codex_local_chunk_plan_20260429_cohere_full_accuracy.csv --timestamp 20260429T_COHERE_FULL_ACCURACY_CODEX
```

## Historical note
- Wulver/Slurm-oriented docs are historical/provenance-only for the current Codex-local workflow.
