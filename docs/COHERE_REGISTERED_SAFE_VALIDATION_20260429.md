# Cohere Registered-Method Safe Validation (Diagnostic Only)

## Scope and guardrails
- **Purpose:** bounded diagnostic run to validate currently registered methods in `scripts/run_cohere_real_model_cost_normalized_validation.py`.
- **Guardrail:** This run is **diagnostic-only** and **does not update canonical paper tables**.
- **Guardrail:** This run is **not a source of truth** and **does not modify** `docs/PAPER_SOURCE_OF_TRUTH.md`.

## Exact command
```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260429T_REGISTERED_COHERE_SAFE_VALIDATION \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k \
  --budgets 4 \
  --seeds 11 \
  --methods strict_f3,strict_gate1_cap_k6,strict_f3_anti_collapse_weak_v1,direct_reserve_semantic_frontier_v2,direct_reserve_semantic_frontier_v2_selection_fix_v1,external_l1_max,tale,s1,self_consistency_3 \
  --target-scored-per-slice 10 \
  --max-examples 10 \
  --resume \
  --emit-trace-audit
```

## Git commit context
- `git rev-parse --short HEAD`: `bbfc148`
- `git log -1 --oneline`: `bbfc148 Merge pull request #303 from SoroushVahidi/codex/run-cohere-accuracy-comparison-experiment`

## Cohere readiness status
- Readiness check outcome: **ready** (`ready=1`, reason=`ok`).

## Completion status
- Completed slices: **9**
- Incomplete slices: **0**

## Per-method accuracy (openai/gsm8k, seed=11, budget=4)
- `strict_f3`: 0.50 (10 scored)
- `strict_gate1_cap_k6`: 0.30 (10 scored)
- `strict_f3_anti_collapse_weak_v1`: 0.30 (10 scored)
- `direct_reserve_semantic_frontier_v2`: 0.50 (10 scored)
- `direct_reserve_semantic_frontier_v2_selection_fix_v1`: 0.30 (10 scored)
- `external_l1_max`: 0.80 (10 scored)
- `tale`: 0.50 (10 scored)
- `s1`: 0.70 (10 scored)
- `self_consistency_3`: 0.30 (10 scored)

## Pairwise status vs `external_l1_max`
- `strict_f3` vs `external_l1_max`: evaluable, matched=10, mean delta (strict_f3 - external_l1_max) = **-0.30**, wins/ties/losses for strict_f3 = **0/7/3**.
- `best_frontier` vs `external_l1_max`: evaluable, method_a resolved to `strict_f3`, matched=10, mean delta = **-0.30**.

## Artifact location
- `outputs/cohere_real_model_cost_normalized_validation_20260429T_REGISTERED_COHERE_SAFE_VALIDATION/`
