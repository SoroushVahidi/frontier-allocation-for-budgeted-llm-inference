# PRM step-verifier rerank v1 — Wulver / validation status (2026-04-29)

## Current verdict: **implemented (live-runnable in repository)**

The method **`direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`** is now wired end-to-end:

| Location | Status |
|----------|--------|
| `scripts/run_cohere_real_model_cost_normalized_validation.py` | Present in `METHODS` with runtime `direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`. |
| `experiments/frontier_matrix_core.py` | `specs["direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1"]` registered with env-driven verifier backend/model. |
| `experiments/controllers.py` | `DirectReserveFrontierGateV2PRMStepVerifierRerankV1Controller` emits PRM rerank metadata. |
| `experiments/prm_step_verifier_rerank.py` | Step segmentation, trace/group scoring, mock + Cohere verifiers. |

**Historical note:** an earlier audit recorded this method as absent from `METHODS` and strategies; that state is **obsolete** once this commit is on your branch.

## Environment variables (actual names in code)

| Variable | Role |
|----------|------|
| `DR_V2_PRM_STEP_VERIFIER_BACKEND` | `mock` (default) or `cohere`. |
| `DR_V2_PRM_STEP_VERIFIER_COHERE_MODEL` | Cohere chat model when backend is `cohere` (default `command-r-plus-08-2024`). |
| `COHERE_API_KEY` | Required only for **`cohere`** backend. **Never print or commit.** |

## Local no-API validation

```bash
python scripts/run_cohere_real_model_cost_normalized_validation.py \
  --timestamp 20260429T_PRM_STEP_RERANK_VALIDATE \
  --providers cohere \
  --cohere-model command-r-plus-08-2024 \
  --datasets openai/gsm8k \
  --budgets 4 \
  --seeds 11 \
  --methods direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1 \
  --target-scored-per-slice 1 \
  --max-examples 1 \
  --validate-methods-only
```

Expect **`validation_status=runnable`** for cohere/budget slices in `method_validation_report.csv` and process exit code **0**.

## Wulver / Slurm

- **No Wulver job submitted** as part of the implementation handoff.
- **Do not submit** a large real-model job until the user explicitly requests it after validation.
- Suggested **future** batch command and evidence expectations: see **`docs/PRM_STEP_VERIFIER_RERANK_V1_IMPLEMENTATION_STATUS_20260429.md`**.

## Active OV rerank run (do not collide)

- Preserve the existing OV rerank run / directory: **`20260429T_OV_RERANK_100CASE_COHERE_BACKEND`** — do not delete, rename, or reuse that timestamp for PRM.

## Planned PRM evidence timestamp (when you run for real)

- Example output root: `outputs/cohere_real_model_cost_normalized_validation_20260429T_PRM_STEP_RERANK_100CASE_COHERE_BACKEND/` (gitignored by default).

## Implementation detail pointer

- Full checklist, file list, and “future full run” command template: **`docs/PRM_STEP_VERIFIER_RERANK_V1_IMPLEMENTATION_STATUS_20260429.md`**.
