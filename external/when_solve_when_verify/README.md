# When To Solve, When To Verify (Singhi et al.)

- **Canonical title:** *When To Solve, When To Verify: Compute-Optimal Problem Solving and Generative Verification for LLM Reasoning*
- **Paper:** https://arxiv.org/abs/2504.01005
- **Official code (linked from arXiv abstract):** https://github.com/nishadsinghi/sc-genrm-scaling
- **License (upstream repo):** **Apache-2.0**
- **Import status in this repo:** **`RUNNABLE_ADJACENT` via verified import protocol only**.

## Why this is adjacent (not direct) here

Upstream SC-vs-GenRM evaluation relies on a specific generation + verification + evaluation stack (vLLM-heavy workflows and upstream data/model conventions). This repo does not reproduce that full stack end-to-end as native methods.

Therefore, this baseline is integrated as an adjacent import protocol with explicit claim boundaries.

## What is now unblocked

A strict import-validation protocol now exists:

- validator: `scripts/verify_when_solve_when_verify_import.py`
- canonical integration note: `docs/when_solve_when_verify_integration.md`
- status artifacts:
  - `outputs/external_baseline_completeness/when_solve_when_verify_status.json`
  - `outputs/external_baseline_completeness/when_solve_when_verify_status.md`

## Non-overclaim boundary

Safe:

- reviewer-auditable adjacent import comparisons after validation.

Not safe:

- claiming full in-repo reproduction,
- claiming direct control-equivalent comparability with frontier/action-native controllers.
