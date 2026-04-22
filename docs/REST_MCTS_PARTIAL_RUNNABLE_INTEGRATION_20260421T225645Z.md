# ReST-MCTS* partial runnable integration report (2026-04-21T22:56:45Z)

## Purpose
Implement the strongest honest **partial runnable official-code integration lane** for ReST-MCTS* in this repository, going beyond import-only validation while avoiding overclaims about full end-to-end self-training reproduction.

## Baseline summary
ReST-MCTS* combines a policy model, a process reward model (PRM / value model), and MCTS-style search to improve reasoning traces and final answer quality. It uses tree-search-guided process reward learning and self-training, and the official materials provide clear search/evaluation entrypoints while full self-training reproduction is substantially heavier.

## Official links
- Paper: https://arxiv.org/abs/2406.03816
- Official repo: https://github.com/THUDM/ReST-MCTS
- Project page: https://rest-mcts.github.io

## Current in-repo status before this pass
Before this pass, this repository had:
- adjacent import validator: `scripts/verify_rest_mcts_import.py`
- integration note: `docs/rest_mcts_integration.md`
- external reference note: `external/rest_mcts/README.md`
- fixture import package: `tests/fixtures/rest_mcts_import_valid/`

But it did **not** have a canonical partial-runnable official-code integration runner analogous to strengthened BEST-Route / when_solve_when_verify lanes.

## Upstream runnable-path summary
Upstream ReST-MCTS repository audit identified:
- environment files: `requirements_mistral.txt`, `requirements_sciglm.txt`
- search/eval entrypoints: `MCTS/task.py`, `evaluate.py`
- PRM training scripts: `PRM/train_VM_mistral.py`, `PRM/train_VM_chatglm.py`
- policy self-training script: `self_train/self_train_dpo.py`
- data format expectations:
  - README says JSON objects with `content` and optional `answer`
  - `utils/json_operator.py` actually reads line-delimited JSON records
- model-family assumptions:
  - policy: Llama/Mistral/SciGLM
  - value model: Mistral or ChatGLM variants
  - official setup assumes heavyweight checkpoints and model-serving conditions

## What was implemented in this pass
1. New canonical runner:
   - `scripts/run_rest_mcts_partial_runnable_integration.py`
   - performs stage-based audit + setup + execution + artifact export.
2. New comparison contract config:
   - `configs/rest_mcts_adjacent_comparison_contract_v1.json`
3. New artifact family (this run):
   - `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/`
4. New paper-facing report (this file).

## Exact install commands run
From this pass:
- `/root/.pyenv/versions/3.14.0/bin/python -m pip install openai==0.28.1 backoff==2.2.1 pylatexenc==2.10 graphviz==0.20.3`

## Stage-by-stage execution results
1. **current_state_audit**: pass
2. **upstream_audit**: pass
3. **environment_and_dependency**: pass (with explicit pre/post dependency check)
4. **config_validation**: pass (`scripts/verify_rest_mcts_import.py` on fixture)
5. **smoke_and_tiny_slice**: pass
   - official `MCTS/task.py` path executed using deterministic stub policy/value backends
   - official `evaluate.py` path executed on one-question tiny slice
6. **artifact_export**: pass

See: `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/stage_status.csv`.

## What runs now
- Official-code-backed local search smoke path (`MCTS/task.py`) in this environment.
- Official eval script path (`evaluate.py`) on tiny benchmark slice with deterministic mock backend.
- Existing adjacent import validation path (`scripts/verify_rest_mcts_import.py`).
- Artifact-backed export path including `results_summary.json` and `comparison_ready_rows.csv`.

## What does not run yet
- Full upstream end-to-end self-training reproduction (PRM bootstrap + multi-iteration policy updates + benchmark-scale reproduction with real model checkpoints).

## Exact hard blocker (remaining for full reproduction)
- Full reproduction requires heavyweight model checkpoints / training stack / compute and model-family environment provisioning (policy + value models), which is beyond the current lightweight environment lane.

## What is safe to claim now
- ReST-MCTS* is now integrated as a **partial runnable baseline** with an official-code search/evaluation path and reproducible artifact outputs in this repo.
- Comparability remains **adjacent_only** and should not be stated as direct frontier-allocation control equivalence.

## Whether ReST-MCTS* is now usable in the main paper table
- **Yes, as partial runnable adjacent baseline** (not full reproduction), with explicit caveats.

## Exact artifact paths
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/manifest.json`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/environment_check.json`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/dependency_check.json`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/install_commands.txt`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/dataset_contract_check.json`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/run_attempt_log.txt`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/stage_status.csv`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/blockers.json`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/comparison_readiness.json`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/results_summary.json`
- `outputs/rest_mcts_partial_runnable_integration_20260421T225645Z/comparison_ready_rows.csv`
