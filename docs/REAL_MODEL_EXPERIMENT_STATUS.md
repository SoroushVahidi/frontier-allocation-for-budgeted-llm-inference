# Real-Model Experiment Status (Cohere/OpenAI)

**Status: diagnostic (supporting evidence only).**

## Scope
- Real-model runs are not manuscript headline evidence by default.
- They support diagnostics, wiring validation, and continuation planning.

## Durable source of truth for Codex-local Cohere continuation
- `outputs/cohere_compact_ledgers/20260429T_COHERE_FULL_ACCURACY_CODEX_compact_per_example_ledger.csv`
- Older markdown-only progress statements are not authoritative unless ledger-backed.

## Current Cohere full-accuracy state
- Plan dimensions: datasets `openai/gsm8k`, `HuggingFaceH4/MATH-500`; budgets `2,4,6,8`; seeds `11,13,17`; 9 runnable methods.
- `openai/gsm8k`, budget `2`, seed `11`, 9-method matched slice: **incomplete** according to current durable workflow status.

## Historical/provenance-only inputs
- Tiny (10-example) checks.
- Interrupted launch attempts.
- Wulver/Slurm handoff docs and legacy launch notes for non-Codex-local workflows.

## Excluded method reminder
- `direct_reserve_semantic_frontier_v2_thresholded_ordered` remains diagnostic-only and excluded from live runner method set.
