# Reviewer 10-minute reproduction

Purpose: provide a short, reliable, reviewer-safe reproduction path for anonymous NeurIPS review.

## Exact commands (run from repo root)

```bash
python scripts/check_repo_health.py
python -m pytest -q tests/test_frontier_router.py tests/test_check_repo_health_paths.py
python scripts/paper/run_all_neurips_paper_artifacts.py
```

Equivalent Make targets:

```bash
make health
make reviewer-test
python scripts/paper/run_all_neurips_paper_artifacts.py
```

## Expected outputs

- Health check prints: `Repository health check: OK`.
- Reviewer-safe tests pass on baseline environments.
- Paper artifact runner completes and writes canonical outputs to:
  - `outputs/paper_tables/`
  - `outputs/paper_plot_data/`
  - `outputs/paper_figures/`

## What is intentionally not rerun

- Full raw experiment recomputation.
- Provider/API-dependent long-running jobs (e.g. multi-method Cohere GSM8K validation folders under `outputs/cohere_real_model_cost_normalized_validation_*`).
- Environment-dependent full test suite (`python -m pytest -q`) that may rely on optional/generated artifacts.

Incomplete or in-flight API runs are **not** claim-bearing. For artifact classes and mock vs Cohere-backend OV rerank timestamps, see `docs/OUTPUTS_ARTIFACT_INDEX.md`.

## Interpretation discipline

- `strict_f3` is the manuscript-facing matched-surface representative.
- `strict_gate1_cap_k6` is the broader operational/default method on a distinct surface.
- Real-model/cost-aware validations are supporting/diagnostic unless explicitly promoted by canonical decision docs.
- Do not claim universal superiority over `external_l1_max`.

## What not to claim from this 10-minute path

- No universal or cross-provider dominance claims.
- No promotion of diagnostic/supporting artifacts to headline evidence.
- No collapse of `strict_f3` and `strict_gate1_cap_k6` into a single winner across surfaces.
