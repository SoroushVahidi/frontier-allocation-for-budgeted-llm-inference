# Test report (PAL port)

Environment: `HF_HUB_OFFLINE=1`, `HF_DATASETS_OFFLINE=1` (no API calls during tests).

Interpreter: `.venv/bin/python` with working directory ``.

## Commands

```bash
cd 
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  .venv/bin/python -m pytest -q \
  tests/test_pal_executor.py \
  tests/test_pal_variant.py \
  tests/test_pal_smoke_postprocess.py \
  tests/test_method_validation_pal_tiebreak_registry.py \
  tests/test_api_branch_generator_json_parsing.py \
  tests/test_output_layer_frontier_surfacing.py \
  tests/test_guarded_k1_frontier4_method.py
```

## Result

**82 passed** in ~3s (2026-05-06 run).

## validate-methods-only

```bash
cd 
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
  .venv/bin/python \
  scripts/run_cohere_real_model_cost_normalized_validation.py \
  --providers cohere \
  --datasets openai/gsm8k \
  --budgets 6 \
  --seeds 20260501 \
  --methods external_l1_max,direct_reserve_diverse_root_frontier_v1_guarded_k1_frontier4_frontier_tiebreak_pal \
  --max-examples 1 \
  --target-scored-per-slice 1 \
  --validate-methods-only
```

Exit code **0**. Output included `validated_rows=2 bad_rows=0` and wrote `outputs/cohere_real_model_cost_normalized_validation_20260506T012727Z/method_validation_report.csv`.
