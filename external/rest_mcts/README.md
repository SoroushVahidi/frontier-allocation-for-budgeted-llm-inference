# ReST-MCTS* external baseline note (official adjacent lane)

- **Canonical title:** ReST-MCTS*: LLM Self-Training via Process Reward Guided Tree Search
- **Official repository:** https://github.com/THUDM/ReST-MCTS
- **Official project page:** https://rest-mcts.github.io
- **NeurIPS 2024 page:** https://proceedings.neurips.cc/paper_files/paper/2024/hash/76ec4dc30e9faaf0e4b6093eaa377218-Abstract-Conference.html
- **arXiv abstract:** https://arxiv.org/abs/2406.03816
- **arXiv PDF:** https://arxiv.org/pdf/2406.03816.pdf

## Integration status in this repository

**Current classification:** `partial_runnable_adjacent` (official-source + contract-verified adjacent lane).

This repository does **not** claim full faithful in-repo reproduction of the full upstream self-training stack.

## Canonical adjacent contract and runnable lane

- Contract: `configs/rest_mcts_adjacent_comparison_contract_v2.json`
- Validator: `scripts/verify_rest_mcts_import.py`
- Canonical runner: `scripts/run_rest_mcts_adjacent_integration.py`
- Backward-compatible wrapper: `scripts/run_rest_mcts_partial_runnable_integration.py`
- Canonical output family: `outputs/rest_mcts_adjacent_integration/<run_id>/`

## Required scope guardrails

Allowed now:
- Official-source provenance reporting.
- Adjacent benchmark rows under explicit `adjacent_only` scope.
- Stable contract-based artifact generation for paper tables.

Not allowed now:
- Claiming full in-repo reproduction of complete ReST-MCTS training/self-training pipeline.
- Claiming direct control-equivalence to branch-level frontier-allocation controllers.

## Verification protocol summary

1. Validate import package (`metadata.json` + `results.csv`) against the contract.
2. Check required upstream workflow-stage declarations and search-budget fields.
3. Verify optional official repo path layout (`MCTS/task.py`, `evaluate.py`, self-train and PRM entrypoints).
4. Export machine-readable status, readiness, summary, manifest, and CSV rows in canonical output family.

## License caveat

As with other external integrations in this repo, users must verify upstream license terms directly before vendoring or redistribution.
