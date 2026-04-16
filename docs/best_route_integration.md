# BEST-Route integration note (reviewer-defensible)

## Scope

This note defines the conservative integration level used in this repository for **BEST-Route**.

## Upstream artifacts audited

- Repo: https://github.com/microsoft/best-route-llm
- README: https://github.com/microsoft/best-route-llm/blob/main/README.md
- Paper: https://arxiv.org/abs/2506.22716
- Microsoft Research page: https://www.microsoft.com/en-us/research/publication/best-route-adaptive-llm-routing-with-test-time-optimal-compute/

Upstream workflow (as documented upstream and respected here):

1. mixed multi-dataset prompt construction,
2. multi-sample response generation per model,
3. armoRM scoring,
4. proxy reward model training/scoring,
5. router training.

Candidate actions in upstream BEST-Route are model+best-of-n arms (e.g., bo1..bo5), which are adjacent—not identical—to this repo's frontier/action control substrate.

## Integration decision in this repository

**Status: `runnable_adjacent` (verified import only).**

What is now unblocked:

- This repo provides a strict import validator for externally produced BEST-Route outputs:
  - `scripts/verify_best_route_import.py`
- This repo provides machine-readable BEST-Route status artifacts:
  - `outputs/external_baseline_completeness/best_route_status.json`
  - `outputs/external_baseline_completeness/best_route_status.md`

What is still intentionally not claimed:

- Direct in-repo reproduction of the full upstream BEST-Route training/scoring pipeline.
- Apples-to-apples control-space equivalence with this repo's frontier/action methods.

## Import contract (conservative)

Required package files:

- `metadata.json`
- `results.csv`

Validator requires:

- explicit upstream workflow-stage declarations,
- candidate-arm schema with model+best-of-n identity,
- presence of bo1 and at least one bo>1,
- explicit `adjacent_only` comparability scope,
- dataset/split/budget consistency checks,
- numeric sanity checks on reported metrics.

This contract is designed to make adjacent comparison auditable without overclaiming direct reproducibility.

## Manuscript-safe wording

Safe now:

- "BEST-Route is integrated as a validated adjacent import protocol in this repo."
- "Comparisons using imported BEST-Route outputs are adjacent and must be reported as such."

Not safe now:

- "BEST-Route is fully reproduced in-repo."
- "BEST-Route and frontier-action methods are direct control-equivalent baselines."
