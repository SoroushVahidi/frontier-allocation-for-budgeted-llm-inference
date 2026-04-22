# rest_mcts integration note (reviewer-defensible)

## Scope

This note defines the conservative integration level used in this repository for **ReST-MCTS\***.

## Upstream artifacts audited

- Repo: https://github.com/THUDM/ReST-MCTS
- README: https://github.com/THUDM/ReST-MCTS/blob/main/README.md
- Paper: https://arxiv.org/abs/2406.03816
- Project page: https://rest-mcts.github.io/

Upstream workflow shape (as documented upstream):

1. bootstrap/train a process reward model (value model),
2. run MCTS-guided trace generation (`MCTS/task.py`, `evaluate.py` in `mcts` mode, and generation scripts),
3. run self-training for policy model updates (e.g., `self_train/self_train_dpo.py` plus related generation/vm_critic helpers),
4. evaluate benchmark performance after self-training iterations.

## Integration decision in this repository

**Status: `partial_runnable` (official-code search/eval lane + verified import).**

What is now unblocked:

- Strict import validator:
  - `scripts/verify_rest_mcts_import.py`
- Canonical partial-runnable integration runner:
  - `scripts/run_rest_mcts_partial_runnable_integration.py`
- Canonical comparison contract:
  - `configs/rest_mcts_adjacent_comparison_contract_v1.json`
- Machine-readable status artifacts:
  - `outputs/external_baseline_completeness/rest_mcts_status.json`
  - `outputs/external_baseline_completeness/rest_mcts_status.md`
  - `outputs/rest_mcts_partial_runnable_integration_<run_id>/`

What is still intentionally not claimed:

- Direct in-repo reproduction of the full upstream ReST-MCTS training/evaluation stack.
- Control-space equivalence between upstream process-reward-guided MCTS self-training and this repo's frontier/action-native controllers.

## Import contract (conservative)

Required package files:

- `metadata.json`
- `results.csv`

Validator requires:

- explicit upstream workflow-stage declarations,
- dataset/split consistency,
- declared policy/value model families plus fixed search settings,
- result rows containing `mcts` search mode with numeric sanity checks,
- explicit `adjacent_only` comparability scope.

This protocol enables reviewer-auditable adjacent comparisons without overclaiming direct reproduction.

## Manuscript-safe wording

Safe now:

- "ReST-MCTS is integrated via a validated adjacent import protocol."
- "Imported ReST-MCTS outputs are used only in adjacent-comparison scope."

Not safe now:

- "ReST-MCTS is fully reproduced in this repository."
- "ReST-MCTS is directly control-equivalent to frontier/action-native controllers."
