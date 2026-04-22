# BEST-Route segfault-fix pass report (2026-04-21T23:59:25Z)

## Purpose
Perform a focused runtime/segfault fix pass for BEST-Route, isolate the failing component with minimal repros, attempt controlled compatibility fixes, and establish the strongest honest runnable state in this environment.

## Current known blocker before this pass
Prior status identified a runtime native failure (reported as segmentation-fault class during tokenizer/model init in previous attempts) after dependency installation and `train_router.py --help` success.

## Official baseline summary
BEST-Route is an adaptive query-level router over `(model, best_of_n)` candidate arms under test-time compute constraints. The official pipeline includes data mixing, response generation, RM scoring, proxy RM training/scoring, and router train/eval.

## Official links
- Paper: https://arxiv.org/abs/2506.22716
- Official repo: https://github.com/microsoft/best-route-llm
- Microsoft page: https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/

## Upstream dependency/runtime structure
Inspected upstream files:
- `requirements.txt` (includes `llm-blender` extras from GitHub)
- `notebooks/requirements_data_preparation.txt` (pins `transformers==4.44.0`, `torch`, `sentencepiece`, etc.)
- `train_router.py` uses:
  - `llm_blender.pair_ranker.model_util.build_tokenizer(...)`
  - HuggingFace `TrainingArguments(...)`
  - hybrid pair-ranker model/data path.

## Crash-isolation plan
Executed staged minimal repros (each in isolated subprocess), covering:
1. import torch
2. import transformers
3. import tokenizers
4. import sentencepiece
5. import llm_blender
6. `AutoTokenizer.from_pretrained("microsoft/deberta-v3-large")`
7. same with `use_fast=False`
8. minimal `AutoModel.from_pretrained("microsoft/deberta-v3-small")`
9. `llm_blender` tokenizer build call
10. smallest synthetic `train_router.py` path.

## Minimal repro scripts created
- `outputs/best_route_segfault_fix_20260421T235925Z/minimal_repros/01_import_torch.py`
- ... through ...
- `outputs/best_route_segfault_fix_20260421T235925Z/minimal_repros/09_llm_blender_build_tokenizer.py`

## Exact commands run
Full command log: `outputs/best_route_segfault_fix_20260421T235925Z/run_attempt_log.txt`.

Install/fix command list: `outputs/best_route_segfault_fix_20260421T235925Z/install_commands.txt`.

## Dependency/version changes attempted
1. CPU torch install (`torch 2.11.0+cpu`).
2. Install baseline dependencies (`sentencepiece`, `dataclasses-json`, `accelerate`, datasets stack, etc.).
3. Install `llm_blender` + required extras.
4. **Attempt official pin** (`transformers==4.44.0`, `tokenizers==0.19.1`) with `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1`.
   - Failed: tokenizers native build against Python 3.14 / PyO3 limitations.
5. **Controlled fallback pin**: `transformers==4.50.0` + `tokenizers==0.21.4` (installable on Python 3.14).

Before/after snapshots:
- `dependency_versions_before.json`
- `dependency_versions_after.json`

## What failed before
- Official stack pin attempt (`4.44.0` + `0.19.1`) failed to install on Python 3.14 due tokenizers/PyO3 native-ABI incompatibility.

## What now works
- All 10 crash-isolation tests now run without exit 139.
- Tiny synthetic router train/eval/predict run succeeds (`exit_code=0`) and writes predictions/labels.
- Artifacts:
  - `tiny_router_run_status.json`
  - `tiny_router_predictions.json`
  - `comparison_ready_rows.csv`

## Whether `use_fast=False` helped
- Not required for stability in final working environment; both fast and slow tokenizer loads pass.

## Whether version pinning helped
- Yes. Non-upstream compatibility pinning to `transformers==4.50.0` + `tokenizers==0.21.4` enabled the tiny synthetic router run on Python 3.14.

## Most likely exact crash source
Most likely root cause is native runtime incompatibility between Python 3.14 and the upstream pinned tokenizer stack (`transformers==4.44.0` requiring `tokenizers==0.19.x`, which fails to build against the current PyO3/Python ABI constraints). This creates forced version drift and unstable runtime behavior in prior attempts.

## Strongest remaining blocker
- Full faithful upstream reproduction remains blocked by environment/version mismatch with official pins and heavy full pipeline requirements. Current successful path is a tiny synthetic compatibility lane, not canonical upstream benchmark reproduction.

## What is safe to claim now
- BEST-Route now has a **stable tiny synthetic router run** in this repository environment (artifact-backed).
- This is an **adjacent partial-runnable** state beyond import-only validation.
- It is not a claim of full end-to-end official reproduction.

## Final status classification
- Full reproduced baseline: **No**
- Partial runnable baseline: **Yes** (tiny synthetic router run succeeds)
- Import-validated only: **No** (stronger than import-only)

## Artifact paths
- `outputs/best_route_segfault_fix_20260421T235925Z/manifest.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/environment_check.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/dependency_versions_before.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/dependency_versions_after.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/install_commands.txt`
- `outputs/best_route_segfault_fix_20260421T235925Z/crash_isolation_matrix.csv`
- `outputs/best_route_segfault_fix_20260421T235925Z/minimal_repro_results.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/run_attempt_log.txt`
- `outputs/best_route_segfault_fix_20260421T235925Z/stage_status.csv`
- `outputs/best_route_segfault_fix_20260421T235925Z/blockers.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/comparison_readiness.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/tiny_router_run_status.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/tiny_router_predictions.json`
- `outputs/best_route_segfault_fix_20260421T235925Z/comparison_ready_rows.csv`
