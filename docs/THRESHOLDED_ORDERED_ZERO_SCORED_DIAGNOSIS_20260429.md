# Thresholded/ordered zero-scored diagnosis (2026-04-29)

- Branch: `work`
- Commit: `7e91267`
- Artifact directory inspected: `outputs/cohere_real_model_cost_normalized_validation_20260429T_BEST_INTERNAL_VARIANTS_COHERE_PREFLIGHT`
- Method ID: `direct_reserve_semantic_frontier_v2_thresholded_ordered`
- Mapped runtime ID: `direct_reserve_semantic_frontier_v2_thresholded_ordered`

## Findings
- In METHODS map: **yes**.
- Runtime returned by runner `build_frontier_strategies(...)`: **no**.
- Runtime exists in semantic-diagnostic registry: **yes**.
- Heartbeat/progress rows: **0**.
- Failure rows: **0** (no failures.jsonl).
- Runtime-missing evidence in slice summary: **yes** (`incomplete_reason=runtime_missing`, attempted=0, scored=0).

## Exact root cause
`--validate-methods-only` previously combined runner specs with semantic-diagnostic specs and therefore incorrectly marked this method runnable. Live execution uses only runner specs from `build_frontier_strategies`; the runtime is absent there, so the method is skipped before attempt/scoring.

## Classification and decision
- Classification: **safe wiring/validation mismatch + diagnostic-only limitation in current runner path**.
- Exclude from full run: **yes** unless runner execution path is intentionally extended.
- Small fix applied: **yes**, validation now reports per-method statuses (`runnable`, `runtime_missing`, `diagnostic_only`, `excluded`).
