# When To Solve, When To Verify (official adjacent import lane)

- **Canonical title:** *When To Solve, When To Verify: Compute-Optimal Problem Solving and Generative Verification for LLM Reasoning*
- **Official paper:** https://arxiv.org/abs/2504.01005
- **Official code:** https://github.com/nishadsinghi/sc-genrm-scaling
- **Import config in this repo:** `configs/when_solve_when_verify_official_import_v1.json`
- **Validator in this repo:** `scripts/verify_when_solve_when_verify_import.py`

## Provenance and claim boundary

This repository tracks this baseline as:

- `official`
- `import_validated`
- `adjacent`

This baseline is **not** treated as a direct frontier-allocation comparator.

## What to clone

Clone the official upstream repository to the expected path:

- `external/when_solve_when_verify/upstream/sc-genrm-scaling`

(Or pass another local clone path to the validator with `--official-repo-path`.)

## What this repository expects from upstream

This repo does not run the full upstream paper pipeline end-to-end. Instead, it expects imported result packages with:

- `metadata.json`
- `results.csv`

and metadata proving solve-generation / verification-generation / fixed-budget-evaluation workflow coverage.

## What is validated here

The validator checks (conservatively):

- official provenance references,
- required workflow stage declarations,
- strategy-space coverage (`self_consistency` + at least one `genrm_*` strategy),
- dataset/split consistency,
- numeric and schema sanity for imported result rows,
- `adjacent_only` comparability scope,
- optional local official clone markers and entrypoint families.

## What is not claimed here

- full faithful in-repo reproduction of the paper stack,
- direct frontier-allocation equivalence,
- claims that this baseline allocates compute across active branch frontiers.

## Import workflow

```bash
python scripts/verify_when_solve_when_verify_import.py \
  --config configs/when_solve_when_verify_official_import_v1.json \
  --results-path tests/fixtures/when_solve_when_verify_import_valid \
  --expected-dataset math128 \
  --expected-split test
```

Use imported results only if validator returns:

- `status: "valid"`
- `verdict: "import_validated"`

## Expected artifacts/results shape

- `metadata.json`: source/upstream identifiers, workflow stages, fixed-budget interpretation, strategy space, provenance.
- `results.csv`: rows with generator/verifier models, solution/verification counts, compute budget tokens, success rate, and adjacent-only comparability tags.

## Caution

This baseline is highly relevant to fixed-budget reasoning-control framing (solve-vs-verify compute allocation), but it remains an **adjacent** baseline relative to this repository’s direct frontier-allocation objective.
