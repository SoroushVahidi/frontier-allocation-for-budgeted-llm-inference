# ReST-MCTS integration note (final stabilized adjacent lane)

## Scope and status

This repo integrates **ReST-MCTS\*** as an **official adjacent** baseline with a contract-bound runnable lane.

- **Current classification:** `partial_runnable_adjacent`
- **Control equivalence:** `adjacent` (not direct frontier-allocation equivalence)
- **Primary lane:** contract-validated import + official repo layout verification + canonical artifact family export

## Official provenance set

- Official repo: https://github.com/THUDM/ReST-MCTS
- Official project page: https://rest-mcts.github.io
- NeurIPS 2024 page: https://proceedings.neurips.cc/paper_files/paper/2024/hash/76ec4dc30e9faaf0e4b6093eaa377218-Abstract-Conference.html
- arXiv: https://arxiv.org/abs/2406.03816
- PDF: https://arxiv.org/pdf/2406.03816.pdf

## Canonical contract

- `configs/rest_mcts_adjacent_comparison_contract_v2.json`

The contract defines:
- official source mapping,
- benchmark subset and required split,
- declared budget/compute normalization fields,
- model/path requirements,
- required artifact family,
- success criteria,
- allowed vs disallowed claims.

## Canonical scripts

- Import/asset verifier: `scripts/verify_rest_mcts_import.py`
- Adjacent runner: `scripts/run_rest_mcts_adjacent_integration.py`
- Legacy wrapper: `scripts/run_rest_mcts_partial_runnable_integration.py`

## Canonical output family

- `outputs/rest_mcts_adjacent_integration/<run_id>/`

Expected artifacts:
- `status.json`
- `comparison_readiness.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `config_snapshot.json`
- `commands_snapshot.txt`
- `comparison_ready_rows.csv`

## Runnable lane definition

Minimum stable lane for this phase:
1. verify the contract-defined subset package,
2. enforce `adjacent_only` comparability scope,
3. verify official repo layout (if local path present/clone succeeds),
4. export standardized artifacts for downstream reporting.

This lane is intentionally conservative and robust for reviewer-defensible adjacent reporting.

## Explicit out-of-scope items

Not claimed in this phase:
- full faithful in-repo reproduction of the complete ReST-MCTS self-training loop,
- direct control-equivalent comparison to branch-level marginal budget-allocation methods,
- unqualified benchmark SOTA claims from this adjacent lane.

## Manuscript-safe wording

> ReST-MCTS* is integrated in this repository as an official adjacent baseline through a contract-validated, artifact-backed lane. We use it for adjacent-only comparison context with explicit scope guardrails, and we do not claim full in-repo faithful reproduction of the complete upstream self-training pipeline.
