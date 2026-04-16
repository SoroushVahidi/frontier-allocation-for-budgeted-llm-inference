# openr integration note (reviewer-defensible)

## Scope

This note defines the conservative integration level used in this repository for **OpenR**.

## Upstream artifacts audited

- Repo: https://github.com/openreasoner/openr
- README: https://github.com/openreasoner/openr/blob/main/README.md
- Paper: https://arxiv.org/abs/2410.09671
- Project page: https://openreasoner.github.io/

Upstream workflow shape (as documented upstream):

1. launch LM/RM services (e.g., scripts under `reason/llm_service/`),
2. run inference evaluation via `reason/evaluation/evaluate.py` with method scripts in `scripts/eval/`,
3. export run artifacts (`config.json`, `record.jsonl`, `avg_result.json`) under `<save_dir>/<task>/<method>/<timestamp>/`,
4. optionally run PRM and RL training stacks (`prm/`, `train/mat/`) for broader framework usage.

## Integration decision in this repository

**Status: `runnable_adjacent` (verified import only).**

What is now unblocked:

- Strict import validator:
  - `scripts/verify_openr_import.py`
- Machine-readable status artifacts:
  - `outputs/external_baseline_completeness/openr_status.json`
  - `outputs/external_baseline_completeness/openr_status.md`

What is still intentionally not claimed:

- Direct in-repo reproduction of the full upstream OpenR serving + inference + training stack.
- Control-space equivalence between OpenR search strategy control and this repo's frontier/action-native controllers.

## Import contract (conservative)

Required package files:

- `metadata.json`
- `results.csv`

Validator requires:

- explicit upstream workflow-stage declarations,
- dataset/split consistency,
- declared generator model and methods evaluated,
- strategy coverage including `cot` and at least one tree-search method,
- numeric sanity checks for `majority_vote` and `total_completion_tokens`,
- explicit `adjacent_only` comparability scope.

This protocol enables reviewer-auditable adjacent comparisons without overclaiming direct reproduction.

## Manuscript-safe wording

Safe now:

- "OpenR is integrated via a validated adjacent import protocol."
- "Imported OpenR outputs are used only in adjacent-comparison scope."

Not safe now:

- "OpenR is fully reproduced in this repository."
- "OpenR is directly control-equivalent to frontier/action-native controllers."
