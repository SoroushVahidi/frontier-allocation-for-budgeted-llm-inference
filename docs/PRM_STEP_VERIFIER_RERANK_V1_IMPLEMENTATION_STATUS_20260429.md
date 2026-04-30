# PRM step-verifier rerank v1 — implementation status (2026-04-29)

## Summary

Method ID: **`direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`**.

- **Code status:** implemented and registered as a **live-runnable** runtime strategy (DR-v2 candidate generation + PRM-style step verifier + answer-group aggregation).
- **Evidence status:** **no completed real-model result** in this handoff; implementation is considered production-complete for wiring only **after** local tests and `--validate-methods-only` succeed on your checkout.
- **Default backend:** **`mock`** (`DR_V2_PRM_STEP_VERIFIER_BACKEND` defaults to `mock` when unset). This avoids accidental Cohere spend and is **not** substitute evidence for a Cohere-backed verifier run.
- **Cohere backend:** set **`DR_V2_PRM_STEP_VERIFIER_BACKEND=cohere`** and optionally **`DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL`** (default `command-r-plus-08-2024`). Requires **`COHERE_API_KEY`** in the environment (never print or commit the key).

## Files

| Area | Path |
|------|------|
| Step verifier + selection | `experiments/prm_step_verifier_rerank.py` |
| Controller | `experiments/controllers.py` (`DirectReserveFrontierGateV2PRMStepVerifierRerankV1Controller`) |
| Runtime registration | `experiments/frontier_matrix_core.py` |
| Validation runner `METHODS` | `scripts/run_cohere_real_model_cost_normalized_validation.py` |
| Per-row / manifest env snapshot | same script (`prm_step_verifier_*_env`, `prm_step_verifier_environment` in `manifest.json`) |
| Tests | `tests/test_prm_step_verifier_rerank.py`, `tests/test_method_validation_prm_step_verifier_rerank.py` |
| Live comparison set (consistency check) | `scripts/check_repository_status_consistency.py` |

## Operational rules (from project policy)

1. **Do not submit a Wulver / Slurm job** for this method until the user **explicitly** requests it after validation.
2. **Do not interrupt or overwrite** the active / in-flight OV rerank Cohere run under  
   `outputs/cohere_real_model_cost_normalized_validation_20260429T_OV_RERANK_100CASE_COHERE_BACKEND/`.
3. Short local pytest and `--validate-methods-only` are the intended preflight steps.

## Suggested future full validation command (do not run as default)

When you are ready for a **new** timestamped output directory (example only; adjust `--target-scored-per-slice` and budgets to study design):

```bash
DR_V2_PRM_STEP_VERIFIER_BACKEND=cohere \
DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL=command-r-plus-08-2024 \
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260429T_PRM_STEP_RERANK_100CASE_COHERE_BACKEND \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k \
  --budgets 4 \
  --seeds 11 \
  --methods direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1 \
  --target-scored-per-slice 100 \
  --max-examples 0
```

**This document does not constitute approval to submit that job** — wait for explicit user go-ahead.

## Cross-links

- Wulver / validation tracking (historical “not runnable” audit superseded by code): `docs/PRM_STEP_VERIFIER_RERANK_V1_WULVER_RUN_STATUS_20260429.md`
- Selector narrative: `docs/SELECTOR_REGISTRY_CANONICAL_20260429.md` §4.2
- Method table: `docs/METHOD_REGISTRY_CANONICAL_20260429.md`
