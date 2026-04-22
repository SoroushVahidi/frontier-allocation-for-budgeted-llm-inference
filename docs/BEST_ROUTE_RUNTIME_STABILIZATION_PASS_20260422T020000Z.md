# BEST-Route runtime stabilization pass (2026-04-22)

## Purpose
Execute the next high-value BEST-Route modification pass as a strict two-lane baseline:
- **Lane A:** stable paper-usable adjacent import lane.
- **Lane B:** runtime stabilization lane with explicit tokenizer/runtime crash isolation and a tiny synthetic router execution attempt.

## Script and run artifact
- Runner: `scripts/run_best_route_runtime_stabilization_pass.py`
- Run artifact: `outputs/best_route_runtime_stabilization/<run_id>/`

## Stage 1 audit summary
- Upstream official repository is present at `external/best_route_microsoft/upstream/best-route-llm/`.
- Upstream files inspected in this pass: `requirements.txt`, `notebooks/requirements_data_preparation.txt`, `train_router.py`.
- Existing repository adjacent lane remains operational (`scripts/run_best_route_adjacent_integration.py`).

## Stage 2 crash isolation results (10 tests)
The pass ran and logged all required tests in `crash_isolation_matrix.csv`:
1. `import torch` ✅
2. `import transformers` ✅
3. `import tokenizers` ✅
4. `import sentencepiece` ✅
5. `import llm_blender` ✅
6. `AutoTokenizer.from_pretrained(...)` for router backbone ✅
7. same with `use_fast=False` ✅
8. smallest model init ✅
9. `llm_blender` tokenizer-build path ✅
10. smallest synthetic BEST-Route router path ✅

No exit-139 segmentation fault was observed in this run.

## Stage 3 conservative stabilization actions
This pass used a rational order and logged each action in `run_attempt_log.txt` and `install_commands.txt`:
- preferred isolated conservative runtime when available (`python3.12` venv in this environment),
- CPU-only tiny run (`CUDA_VISIBLE_DEVICES=''`),
- explicit compatibility pin (`transformers==4.50.0`, `tokenizers==0.21.4`),
- dependency completion for `llm_blender` runtime chain,
- re-run full crash matrix + tiny synthetic router run.

## Lane outcomes
- **Lane A (adjacent): pass** — adjacent integration and row export succeeded.
- **Lane B (runtime): pass** — tiny synthetic router train/eval/predict path succeeded and the crash matrix passed.

## Honest classification after this pass
Current strongest honest state is now:
- **stable partial-runnable adjacent baseline**.

Still not claimed:
- full benchmark-faithful BEST-Route reproduction (full upstream multi-stage pipeline),
- direct control-equivalence with this repository’s frontier allocation method.

## Key artifacts
- `outputs/best_route_runtime_stabilization/<run_id>/manifest.json`
- `outputs/best_route_runtime_stabilization/<run_id>/environment_check.json`
- `outputs/best_route_runtime_stabilization/<run_id>/stage_status.csv`
- `outputs/best_route_runtime_stabilization/<run_id>/crash_isolation_matrix.csv`
- `outputs/best_route_runtime_stabilization/<run_id>/comparison_readiness.json`
- `outputs/best_route_runtime_stabilization/<run_id>/run_attempt_log.txt`
- `outputs/best_route_runtime_stabilization/<run_id>/install_commands.txt`
- `outputs/best_route_runtime_stabilization/<run_id>/blockers.json`
