# BEST-Route full integration attempt (20260421T221721Z)

## Purpose
Execute a real BEST-Route integration attempt with iterative dependency installation and repeated reruns, and determine the strongest honest runnable state this repository can currently support.

## Baseline summary
BEST-Route is a cost-aware adaptive routing framework for LLM inference. It chooses both which model to use and how many responses to sample (best-of-n), based on query difficulty and quality thresholds, to reduce cost while preserving answer quality.

## Paper link
- https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/

## Repo link
- https://github.com/microsoft/best-route-llm

## Current in-repo status before this pass
Before this pass, this repo already had official adjacent import validation and comparison-row export for BEST-Route (`scripts/verify_best_route_import.py`, `scripts/run_best_route_adjacent_integration.py`) but no proven full upstream runnable lane in this environment.

## Upstream execution requirements
From upstream README + entrypoints, faithful BEST-Route execution requires:
1. dependency installation (`requirements.txt`, `notebooks/requirements_data_preparation.txt`),
2. dataset mixing (`notebooks/dataset_mixer.ipynb`),
3. multi-sample generation (`notebooks/generate_llm_responses.py`),
4. armoRM scoring (`notebooks/scoring_per_model_armoRM.py`),
5. token-cost augmentation,
6. train/validation/test splitting,
7. proxy RM training/scoring (`notebooks/reward_modeling.py`, `notebooks/scoring_per_model_ourRM.py`),
8. router prep (`notebooks/data_preparation_hybridllm_mapping.ipynb`),
9. router training/eval (`train_router.py`),
10. interpretation/export (`results_interpretation.ipynb`).

## Dependencies discovered
Core runtime deps needed to get upstream router entrypoint running in this environment included:
- `torch`
- `transformers==4.37.2` (explicit downgrade to resolve llm-blender incompatibility against newer transformers)
- `llm-blender` from upstream GitHub source
- additional llm-blender runtime deps (`prettytable`, `tabulate`, `spacy`, `bert_score`, `evaluate`, `sacrebleu`, `rouge_score`, `nltk`, `pycocoevalcap`, `wandb`).

## Exact install commands run
All install commands are recorded in:
- `outputs/best_route_full_integration_attempt_20260421T221721Z/install_commands.txt`

Installed sequence:
1. `python -m pip install py-cpuinfo`
2. `python -m pip install torch`
3. `python -m pip install transformers==4.37.2 accelerate huggingface_hub datasets tqdm trl==0.10.1 scikit-learn pandas sentencepiece`
4. `python -m pip install git+https://github.com/yuchenlin/LLM-Blender.git`
5. `python -m pip install prettytable tabulate spacy bert_score evaluate sacrebleu rouge_score nltk pycocoevalcap wandb`

## Stage-by-stage execution results
From `stage_status.csv`:
1. local repo-side config validation: **pass**
2. upstream clone/access marker validation: **pass**
3. dependency install + import verification: **pass**
4. dataset contract validation: **fail** (missing canonical import packages for MATH-500, AIME-2024, OlympiadBench)
5. upstream smoke-run (`train_router.py --help`): **pass**
6. minimal synthetic tiny train/eval/predict run: **fail** (exit 139, segmentation fault)
7. adjacent comparison-row export: **pass**
8. artifact export validation: **pass**

## Which blockers were solved
Solved in this pass:
- missing `torch` blocker from prior attempt,
- llm-blender/transformers import incompatibility by pinning transformers,
- missing llm-blender transitive runtime imports (prettytable/tabulate/spacy/bert_score/evaluate/wandb/etc.),
- upstream router help-entrypoint now runnable.

## Exact final blocker, if any
Primary hard blocker for moving beyond partial runnable state in this environment:
- **Tokenizer/runtime segmentation fault under Python 3.14 stack during real tokenizer/model initialization** (exit 139), reproduced both in tiny BEST-Route run and in a direct `AutoTokenizer.from_pretrained('microsoft/deberta-v3-small')` diagnostic.
- Evidence artifacts:
  - `run_attempt_log.txt` (stage 6 exact command + stderr `Segmentation fault`),
  - `tokenizer_crash_diagnostic.txt` (faulthandler crash trace; exit 139).

## What is safe to claim now
- BEST-Route is now **partially runnable** here with a stronger lane than before: upstream access validated, dependencies installed, upstream router script imports and help execution pass, and adjacent comparison rows are exportable.
- This repository still provides adjacent/import-validated comparison rows reproducibly.

## What is not safe to claim now
- Not safe to claim full faithful BEST-Route end-to-end reproduction in this environment.
- Not safe to claim benchmark-level BEST-Route results for MATH-500/AIME-2024/OlympiadBench from this run.

## Whether BEST-Route is now usable in the main paper table
It is usable only as an **adjacent import-validated** external comparator (with explicit caveats), not yet as a fully reproduced in-repo end-to-end baseline.

## Exact artifact paths
- `outputs/best_route_full_integration_attempt_20260421T221721Z/manifest.json`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/environment_check.json`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/dependency_check.json`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/install_commands.txt`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/dataset_contract_check.json`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/run_attempt_log.txt`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/stage_status.csv`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/blockers.json`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/comparison_readiness.json`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/comparison_ready_rows.csv`
- `outputs/best_route_full_integration_attempt_20260421T221721Z/tokenizer_crash_diagnostic.txt`
