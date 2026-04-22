# lets_verify_step_by_step

## Canonical identity

- Canonical title: **Let's Verify Step by Step**
- Canonical paper URL: https://arxiv.org/abs/2305.20050
- Canonical PDF: https://arxiv.org/pdf/2305.20050.pdf
- DOI: https://doi.org/10.48550/arXiv.2305.20050
- Official repository: https://github.com/openai/prm800k

## Repository classification (after final strengthening pass)

- Provenance level in this repository: **official** (paper + official code repository identified)
- Baseline family: **process verifier / process-supervision**
- Control-space relation to this repo’s primary method: **adjacent (not direct control-equivalent)**
- Current strongest honest classification: **partial_runnable_adjacent**
- Normalized matrix status row remains conservative as **import_validated + adjacent** (with partial-runnable lane evidence)

## What public official artifacts are available

From the official `openai/prm800k` repository:

- PRM800K data files and MATH split files (e.g., `prm800k/data/*.jsonl`, `prm800k/math_splits/*.jsonl`)
- Grading/evaluation utilities (e.g., `prm800k/eval/eval.py`, `prm800k/grading/grader.py`)
- Project documentation/instructions under the repo tree

## What is runnable now in this repository

This repository now provides a stable adjacent contract lane:

- Contract: `configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json`
- Validator: `scripts/verify_lets_verify_step_by_step_import.py`
- Runner: `scripts/run_lets_verify_step_by_step_adjacent_integration.py`
- Canonical outputs: `outputs/lets_verify_step_by_step_adjacent_integration/<run_id>/`

The lane verifies:

1. official-source mapping and contract integrity,
2. official repo layout/public artifact presence (when available locally or cloned),
3. a stable MATH import subset under explicit `adjacent_only` comparability scope,
4. machine-readable artifacts for paper-safe reporting.

## What is *not* runnable now

- Full faithful, end-to-end in-repo reproduction of the complete paper-scale training/evaluation stack.
- Reproduction claims that require unreleased internal checkpoints or internal infrastructure.
- Direct branch-allocation control-equivalent experiments.

## Safe claims vs unsafe claims

### Safe now

- We integrate *Let's Verify Step by Step* as an **official, paper-backed adjacent baseline family**.
- We provide a **stable partial-runnable adjacent lane** using public PRM800K assets and strict contract checks.
- We enforce explicit adjacent-only comparison scope and export auditable artifacts.

### Unsafe now

- Claiming full faithful in-repo reproduction of the complete original paper pipeline.
- Claiming direct control-equivalence to branch-level marginal budget-allocation methods.
- Using API-based substitutes as if they were the official baseline.

## Why adjacent rather than control-equivalent

This baseline centers on process-supervision / verifier scoring over reasoning traces and completion-aware evidence.
The primary method in this repository centers on branch-level marginal budget allocation over active reasoning frontiers.
Those action spaces are related but not equivalent, so this baseline must remain adjacent-labeled.

## Canonical command examples

```bash
python scripts/verify_lets_verify_step_by_step_import.py \
  --results-path tests/fixtures/lets_verify_step_by_step_import_valid \
  --expected-dataset math \
  --expected-split test \
  --contract-config configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json
```

```bash
python scripts/run_lets_verify_step_by_step_adjacent_integration.py \
  --contract-config configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json
```

## Out-of-scope statement for current paper phase

For this phase, this baseline lane is considered **done enough** when used as an adjacent, reviewer-defensible, artifact-backed comparator.
A future upgrade to full faithful reproduction would require additional official assets and auditable end-to-end execution that are out of scope here.
