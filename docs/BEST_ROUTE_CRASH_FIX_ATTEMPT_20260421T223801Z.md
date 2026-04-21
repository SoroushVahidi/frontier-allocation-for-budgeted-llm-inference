# BEST-Route crash-fix attempt (20260421T223801Z)

## Purpose
Perform crash isolation and stabilization for the current BEST-Route runtime crash (exit 139) and determine whether tiny synthetic router execution can be made stable in this environment.

## Current known blocker before this pass
Prior pass established that packages were installed and `train_router.py --help` worked, but true execution crashed with segmentation fault during tokenizer/model initialization.

## Official baseline summary
BEST-Route is an adaptive routing framework that chooses both model arm and best-of-n sampling budget based on difficulty/quality targets, to improve quality-cost tradeoff.

## Official paper/repo links
- Paper: https://arxiv.org/abs/2506.22716
- Microsoft page: https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/
- Official repo: https://github.com/microsoft/best-route-llm

## Upstream dependency/runtime structure
Official files in upstream:
- `requirements.txt` -> `py-cpuinfo`, `llm-blender[example,train,data,eval]`
- `notebooks/requirements_data_preparation.txt` -> `transformers==4.44.0`, `torch`, `accelerate`, `datasets`, `trl`, `sentencepiece`, etc.
- `train_router.py` imports `llm_blender.pair_ranker.model_util.build_tokenizer(...)`, which calls `AutoTokenizer.from_pretrained(...)`.

## Exact crash-isolation plan
1. Validate base imports individually.
2. Isolate tokenizer behavior with and without fast tokenization.
3. Isolate llm-blender tokenizer path directly.
4. Try targeted mitigations:
   - force CPU env,
   - pin tokenizers version.
5. Rerun tiny synthetic router path.
6. Preserve and re-validate adjacent export lane.

## Minimal repro scripts created
Created under:
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/repro_scripts/`

Scripts:
- `01_python_plain.py`
- `02_import_transformers.py`
- `03_import_tokenizers.py`
- `04_import_sentencepiece.py`
- `05_import_torch.py`
- `06_import_llm_blender.py`
- `07_autotokenizer_default.py`
- `08_autotokenizer_slow.py`
- `09_auto_model_init.py`
- `10_llm_blender_build_tokenizer.py`

## Exact commands run
Primary command:
- `python scripts/run_best_route_crash_fix_attempt.py`

Key sub-commands executed by the runner are captured in:
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/run_attempt_log.txt`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/manifest.json`

## Dependency/version changes attempted
Recorded in:
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/install_commands.txt`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/dependency_versions_before.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/dependency_versions_after.json`

Actual change attempt in this pass:
- `python -m pip install tokenizers==0.15.0`

## What failed before
Before this pass, tiny router run failed with exit 139 during tokenizer initialization path.

## What now works
- plain import chain: pass
- `import transformers`: pass
- `import tokenizers`: pass
- `import sentencepiece`: pass
- `import torch`: pass
- `import llm_blender`: pass
- minimal model init (`AutoModel.from_pretrained` tiny model): pass
- adjacent import-validated export lane: pass

## Whether `use_fast=False` or version pinning helped
- `use_fast=False`: **did not help** (still exit 139)
- forced CPU environment: **did not help**
- pinning `tokenizers==0.15.0`: **did not help** (still exit 139)

## Crash source assessment
Most likely crash source is native tokenizer runtime incompatibility in this environment (Python 3.14 + tokenizers native extension path), observed from stack traces landing in `tokenizers.cpython-314-...so` and triggered through both direct `AutoTokenizer` and `llm_blender` tokenizer builder path.

## Strongest remaining blocker if still not fixed
Tiny synthetic router run remains blocked by segmentation fault (exit 139) in tokenizer initialization; this is not resolved by CPU forcing, `use_fast=False`, or tokenizers pin to 0.15.0.

## What is safe to claim now
- BEST-Route crash is now narrowly isolated with reproducible minimal repro matrix.
- Adjacent import-validated baseline lane remains intact and exportable.
- Full/tiny router execution path is still blocked in this environment.

## Whether BEST-Route is now usable as full/partial/adjacent
- **Full reproduced baseline:** no
- **Partial runnable baseline (tiny synthetic run):** no (tiny run still crashes)
- **Import-validated adjacent baseline:** yes (strong and preserved)

## Exact artifact paths
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/manifest.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/environment_check.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/dependency_versions_before.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/dependency_versions_after.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/install_commands.txt`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/crash_isolation_matrix.csv`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/minimal_repro_results.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/run_attempt_log.txt`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/stage_status.csv`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/blockers.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/comparison_readiness.json`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/comparison_ready_rows.csv`
- `outputs/best_route_crash_fix_attempt_20260421T223801Z/repro_scripts/`
