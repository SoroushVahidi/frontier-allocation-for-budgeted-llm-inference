# PRM step-verifier rerank v1 — Wulver / validation status (2026-04-29)

## Verdict: **not live-runnable** (implementation pending)

`direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1` is documented as a **planned** selector in registry/roadmap docs only. It is **not** wired into the live runtime or the Cohere cost-normalized validation runner.

### Evidence (repository audit)

| Location | Finding |
|----------|---------|
| `scripts/run_cohere_real_model_cost_normalized_validation.py` | Method **absent** from `METHODS`; `main()` raises `ValueError: Unknown method: ...` before any `--validate-methods-only` logic runs. |
| `experiments/frontier_matrix_core.py` | No `specs["direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1"]`; PRM-related entries are **branch** partial scorers (`adaptive_prm_partial`, `verifier_guided_search_prm`, …), not this final-answer rerank ID. |
| `experiments/controllers.py` | No controller class for this method ID. |
| `docs/METHOD_REGISTRY_CANONICAL_20260429.md` | Row marks method as **proposed / not implemented** as live final selector. |
| `docs/SELECTOR_REGISTRY_CANONICAL_20260429.md` | Describes PRM rerank as proposed §4.2-style direction. |

### Local validation attempt

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

**Result:** fails immediately with `ValueError: Unknown method: direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1`.

### Wulver / Slurm

- **No Slurm job submitted.**
- **No batch script added** as an executable run path (would imply readiness). Use the command block in `docs/PRM_STEP_LEVEL_VERIFIER_SELECTOR_REFERENCE_20260429.md` + OV rerank implementation as a template **after** code exists.

### Suggested env vars (for future implementation)

The repository **does not** define `PRM_STEP_VERIFIER_BACKEND` or `PRM_STEP_VERIFIER_COHERE_MODEL` today — those names were illustrative. After implementation, either:

- reuse/adapt the OV rerank pattern (`DR_V2_OV_RERANK_VERIFIER_BACKEND`-style names scoped to PRM), or  
- introduce `PRM_STEP_VERIFIER_BACKEND` / `PRM_STEP_VERIFIER_COHERE_MODEL` consistently in controller + runner manifest.

Document the **actual** names in code and in this file when implemented.

**Never commit or print `COHERE_API_KEY`.**

### Active OV rerank run (do not collide)

- Existing completed/provenance timestamp: `20260429T_OV_RERANK_100CASE_COHERE_BACKEND` (and mock provenance `20260429T_OV_RERANK_100CASE`).
- Planned PRM timestamp **when ready**: `20260429T_PRM_STEP_RERANK_100CASE_COHERE_BACKEND` (new directory: `outputs/cohere_real_model_cost_normalized_validation_20260429T_PRM_STEP_RERANK_100CASE_COHERE_BACKEND/` — **outputs remain gitignored by default**).

---

## Implementation / registration TODO (checklist)

Before any Wulver 100-case job:

1. **PRM step verifier module** — Step segmentation + scoring interface (mock + optional Cohere/OpenAI backend); strict JSON or bounded fallback; no gold leakage in prompts.
2. **Controller class** — e.g. wrap DR-v2, extract candidates, run step-level verification, aggregate by answer group (parallel to outcome-verifier rerank controller pattern).
3. **Runtime registration** — `build_frontier_strategies(...)`: `specs["direct_reserve_semantic_frontier_v2_prm_step_verifier_rerank_v1"] = ...`.
4. **Validation runner mapping** — Add entry to `METHODS` in `run_cohere_real_model_cost_normalized_validation.py` with correct `runtime` key matching registry.
5. **Tests** — Mock verifier unit tests; grouping/scoring; `--validate-methods-only` passes with `validation_status=runnable`.
6. **Manifest / row provenance** — Mirror OV rerank: log verifier backend env, model, key presence flag (not value), calls, parse failures, fallbacks.
7. **Documentation** — Update `METHOD_REGISTRY_CANONICAL_20260429.md` and `SELECTOR_REGISTRY_CANONICAL_20260429.md` from “proposed” to “implemented” only when the above is true.
8. **Then** — Local `--validate-methods-only` → optional tiny smoke → Slurm batch with new timestamp.

### Post-completion reporting (when a real run exists)

Use or extend the reporting pattern from `scripts/report_outcome_verifier_rerank_results.py` (or a sibling script) for paired comparisons: PRM rerank vs DR-v2, vs `selection_fix_v1`, vs `external_l1_max`, plus cost/latency and present-not-selected recovery taxonomy. **Do not claim success** until scored rows meet targets and claim-safety notes are written.
