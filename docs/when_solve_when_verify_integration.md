# when_solve_when_verify integration note (reviewer-defensible)

## Scope

This note defines the conservative integration level used in this repository for **When To Solve, When To Verify** (SC vs GenRM under fixed inference budget).

## Upstream artifacts audited

- Repo: https://github.com/nishadsinghi/sc-genrm-scaling
- README: https://github.com/nishadsinghi/sc-genrm-scaling/blob/main/README.md
- Paper: https://arxiv.org/abs/2504.01005
- Hugging Face org: https://huggingface.co/sc-genrm-scaling

Upstream workflow shape (as documented upstream):

1. generate solution samples,
2. generate verification samples/scores,
3. evaluate success-rate curves under fixed compute tradeoffs between solution scaling and verification scaling.

## Integration decision in this repository

**Status: `runnable_adjacent` (verified import only).**

What is now unblocked:

- Strict import validator:
  - `scripts/verify_when_solve_when_verify_import.py`
- Machine-readable status artifacts:
  - `outputs/external_baseline_completeness/when_solve_when_verify_status.json`
  - `outputs/external_baseline_completeness/when_solve_when_verify_status.md`

What is still intentionally not claimed:

- Direct in-repo reproduction of the full upstream generation + verification stack.
- Control-space equivalence between upstream SC/GenRM allocation and this repo's frontier/action controllers.

## Import contract (conservative)

Required package files:

- `metadata.json`
- `results.csv`

Validator requires:

- explicit upstream workflow-stage declarations,
- fixed-budget metadata fields,
- strategy coverage including `self_consistency` and at least one `genrm_*` strategy,
- dataset/split consistency,
- numeric sanity checks for solution/verifier counts, compute budget, and success rate,
- explicit `adjacent_only` comparability scope.

This protocol enables reviewer-auditable adjacent comparisons without overclaiming direct reproduction.

## Manuscript-safe wording

Safe now:

- "When To Solve, When To Verify is integrated through a validated adjacent import protocol."
- "Imported SC-vs-GenRM fixed-budget outputs are used only as adjacent comparisons."

Not safe now:

- "When To Solve, When To Verify is fully reproduced in this repository."
- "This baseline is directly control-equivalent to frontier/action-native methods."
