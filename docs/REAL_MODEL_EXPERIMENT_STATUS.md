# Real-Model Experiment Status (Cohere/OpenAI diagnostic track)

## Scope reminder
Real-model runs are diagnostic/supporting unless and until explicitly promoted by canonical evidence documents.

## Completed small diagnostic runs
- Small preflights and bounded checks have been executed to validate method wiring and provider readiness.
- These include tiny slices (including 10-example style checks) and are **not manuscript-level evidence**.

## Targeted reruns and method-resolution checks
- `--validate-methods-only` path exists and is used to ensure selected methods are registered and runtime-resolvable.
- Validated runnable set used for recent Cohere diagnostics:
  - `strict_f3,strict_gate1_cap_k6,strict_f2,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3`.

## Partial launch attempts
- Historical launch attempts (including Wulver/Slurm-oriented docs) are provenance unless completed and promoted.
- Codex-local continuation logs show resumable but still incomplete execution toward 100-scored-per-slice targets.

## Completed meaningful runs (if any)
- No fully completed Codex-local full grid run at 100 scored per slice is currently recorded in this cleanup pass.
- Any partial pairwise rows should be treated as provisional diagnostic signals only.

## Planned but not completed
- Full chunk grid:
  - datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`
  - budgets: `2,4,6,8`
  - seeds: `11,13,17`
  - methods: validated runnable set above
  - target: 100 scored per slice

## Codex-local chunk system status
Implemented and present:
- planner: `scripts/plan_cohere_real_model_chunks.py`
- runner: `scripts/run_cohere_chunk.py`
- status: `scripts/status_cohere_chunk_progress.py`
- aggregation: `scripts/aggregate_cohere_chunks.py`
- runbook: `docs/CODEX_LOCAL_RESUMABLE_COHERE_EXPERIMENT_RUNBOOK_20260429.md`

## Explicit exclusion
- `direct_reserve_semantic_frontier_v2_thresholded_ordered` remains diagnostic-only and excluded from live full comparisons unless runner support is intentionally extended later.
