# Let's Verify Step by Step integration note (official adjacent partial-runnable lane)

## Canonical identification

- **Paper title:** *Let's Verify Step by Step*
- **Paper URL:** https://arxiv.org/abs/2305.20050
- **Paper PDF:** https://arxiv.org/pdf/2305.20050.pdf
- **DOI:** https://doi.org/10.48550/arXiv.2305.20050
- **Official code repository:** https://github.com/openai/prm800k

## Problem class and safest repository classification

- **Native method class:** process-supervision / process-verifier guidance using step-level reasoning traces.
- **Provenance level (this repo):** `official`
- **Normalized status (matrix):** `import_validated`
- **Operational strengthened classification:** `partial_runnable_adjacent`
- **Control-equivalence label (this repo):** `adjacent`

This means the baseline is highly reviewer-relevant and paper-backed, but it is not treated as direct control-equivalent to branch-level marginal frontier allocation.

## Canonical contract and scripts

- Contract: `configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json`
- Validator: `scripts/verify_lets_verify_step_by_step_import.py`
- Runner: `scripts/run_lets_verify_step_by_step_adjacent_integration.py`
- Status generator: `scripts/generate_lets_verify_step_by_step_status_report.py`

## Canonical output family

- `outputs/lets_verify_step_by_step_adjacent_integration/<run_id>/`

Required artifacts:

- `status.json`
- `comparison_readiness.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `config_snapshot.json`
- `commands_snapshot.txt`
- `comparison_ready_rows.csv`

## What official public artifacts are exercised

This lane explicitly checks and uses public official artifacts from `openai/prm800k`, including:

- PRM800K data files,
- MATH split files,
- grading/evaluation utility files,
- repository-level provenance mapping to the canonical paper.

## What is not reproduced

Not claimed in this lane:

- full faithful end-to-end reproduction of original paper-scale model training/evaluation,
- use of non-public internal checkpoints or hidden infrastructure,
- direct control-equivalent frontier-allocation behavior.

## Safe manuscript wording

> We integrate *Let's Verify Step by Step* as an official, paper-backed adjacent process-verifier baseline through a conservative, contract-validated partial-runnable lane using public PRM800K artifacts. This lane supports reviewer-defensible adjacent comparisons, but it is not presented as a full faithful in-repo reproduction or as a direct control-equivalent substitute for branch-level marginal budget allocation.
