# When To Solve, When To Verify integration note (official import-validated adjacent lane)

## Canonical identification

- **Paper title:** *When To Solve, When To Verify: Compute-Optimal Problem Solving and Generative Verification for LLM Reasoning*
- **Paper URL:** https://arxiv.org/abs/2504.01005
- **Official code repository:** https://github.com/nishadsinghi/sc-genrm-scaling
- **Canonical config in this repo:** `configs/when_solve_when_verify_official_import_v1.json`
- **Canonical validator in this repo:** `scripts/verify_when_solve_when_verify_import.py`

## Problem class and safest repo classification

- **Native method class:** fixed-budget allocation between candidate-solution generation and generated verification.
- **Provenance level (this repo):** `official`
- **Normalized status (this repo):** `import_validated`
- **Control-equivalence label (this repo):** `adjacent`

This means the baseline is relevant to fixed-budget reasoning-control, but it is **not** treated as a direct frontier-allocation baseline.

## What is safe to compare

Safe now (after validator pass):

- fixed-budget SC-vs-GenRM import comparisons,
- solve-vs-verify allocation trade-off behavior,
- adjacent comparative discussion against branch/frontier allocation methods.

## What is *not* safe to compare

Not safe now:

- direct claims that this baseline allocates the next unit of compute across active branches,
- direct control-equivalence claims against frontier-allocation policies,
- full in-repo reproduction claims for the entire upstream training/inference stack.

## Why this is stronger to integrate now than Q*

At the current repository state, this baseline is a stronger immediate integration target than Q* because:

1. official paper↔code linkage is clear,
2. the upstream stack exposes concrete generation/verification/evaluation lanes that map to an import contract,
3. adjacent fixed-budget relevance is high while overclaim risk remains controllable through strict import validation.

Q* remains important, but current reproducibility/provenance uncertainty makes it less suitable as the immediate next strengthened official external baseline.

## Why this is the next baseline after BEST-Route

- BEST-Route is already established as an official import-validated adjacent baseline.
- This baseline is the next strongest official import candidate with clearer fixed-budget reasoning-control relevance than routing-only neighbors.
- It is closer to our reasoning-control narrative than BEST-Route while still honestly classified as `adjacent`.

## Minimum viable integration path

1. Add/refresh canonical config: `configs/when_solve_when_verify_official_import_v1.json`.
2. Validate import packages (`metadata.json` + `results.csv`) using:

```bash
python scripts/verify_when_solve_when_verify_import.py \
  --config configs/when_solve_when_verify_official_import_v1.json \
  --results-path tests/fixtures/when_solve_when_verify_import_valid \
  --expected-dataset math128 \
  --expected-split test
```

3. Accept imports for reporting **only** when validator verdict is `import_validated`.
4. Publish status artifacts in `outputs/external_baseline_completeness/`.

## Manuscript-safe wording

Safe wording:

> We integrate *When To Solve, When To Verify* as an **official import-validated fixed-budget solve-vs-verify adjacent baseline**. It is closer to our reasoning-control story than BEST-Route, but it is not a direct frontier-allocation comparator.

Unsafe wording:

- “This is a direct frontier allocation baseline.”
- “This repository fully reproduces the complete paper stack end-to-end.”

## Optional future lane (separate, if added later)

A same-substrate wrapper/adapter can be added later, but it must be labeled separately as `adapter_based` (unofficial repo-side wrapper lane) and must not be conflated with the official baseline lane above.
