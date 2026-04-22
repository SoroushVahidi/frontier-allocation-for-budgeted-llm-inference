# ReST-MCTS final strengthening pass (2026-04-22T12:00:00Z)

## Purpose

This artifact records the final-quality stabilization pass for ReST-MCTS* as an **official adjacent** baseline lane in this repository.

## Official links used

- Official repo: https://github.com/THUDM/ReST-MCTS
- Official project page: https://rest-mcts.github.io
- NeurIPS 2024 page: https://proceedings.neurips.cc/paper_files/paper/2024/hash/76ec4dc30e9faaf0e4b6093eaa377218-Abstract-Conference.html
- arXiv abstract: https://arxiv.org/abs/2406.03816
- arXiv PDF: https://arxiv.org/pdf/2406.03816.pdf

## Repository resources used in this pass

- `external/rest_mcts/README.md`
- `docs/rest_mcts_integration.md`
- `configs/rest_mcts_adjacent_comparison_contract_v2.json`
- `scripts/verify_rest_mcts_import.py`
- `scripts/run_rest_mcts_adjacent_integration.py`
- `scripts/run_rest_mcts_partial_runnable_integration.py` (compatibility wrapper)
- `tests/fixtures/rest_mcts_import_valid/{metadata.json,results.csv}`

## Runnable lane exercised

Canonical command used:

```bash
python scripts/run_rest_mcts_adjacent_integration.py --contract-config configs/rest_mcts_adjacent_comparison_contract_v2.json
```

Lane behavior:
1. validates contract-defined import subset,
2. checks contract completeness,
3. checks official repo layout when available,
4. exports canonical output artifacts.

## Benchmark subset / contract used

- Contract subset: `math_test_import_contract`
- Dataset/split: `math` / `test`
- Package path: `tests/fixtures/rest_mcts_import_valid`
- Scope: `adjacent_only`

## Artifacts/checkpoints verified

- Import package integrity (`metadata.json`, `results.csv`) and required fields.
- Required workflow stages and `mcts` search coverage.
- Optional official repo layout checks:
  - `MCTS/task.py`
  - `evaluate.py`
  - `self_train/self_train_dpo.py`
  - `PRM/train_VM_mistral.py`

## Outputs produced

Canonical output family:

- `outputs/rest_mcts_adjacent_integration/<run_id>/status.json`
- `outputs/rest_mcts_adjacent_integration/<run_id>/comparison_readiness.json`
- `outputs/rest_mcts_adjacent_integration/<run_id>/summary.json`
- `outputs/rest_mcts_adjacent_integration/<run_id>/summary.md`
- `outputs/rest_mcts_adjacent_integration/<run_id>/manifest.json`
- `outputs/rest_mcts_adjacent_integration/<run_id>/config_snapshot.json`
- `outputs/rest_mcts_adjacent_integration/<run_id>/commands_snapshot.txt`
- `outputs/rest_mcts_adjacent_integration/<run_id>/comparison_ready_rows.csv`

## Justified classification after this pass

- **Classification:** `partial_runnable_adjacent`
- **Why justified:** stable contract-bound lane is runnable and emits auditable machine-readable artifacts, while preserving explicit adjacent-only scope and official-source mapping.

## Out of scope after this pass

- Full faithful end-to-end in-repo reproduction of complete ReST-MCTS self-training pipeline.
- Direct control-space equivalence claims against frontier/action-native branch-allocation methods.
- Any unqualified performance claims beyond adjacent import-contract evidence.

## Paper-safe wording (approved)

> ReST-MCTS* is integrated as an official adjacent baseline via a stable contract-validated lane with auditable artifacts. This supports adjacent-only comparison context and does not constitute full in-repo faithful reproduction of the complete upstream self-training stack.
