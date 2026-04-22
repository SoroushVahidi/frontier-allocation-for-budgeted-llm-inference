# Let's Verify Step by Step final strengthening pass (2026-04-22T18:00:00Z)

## Objective

Upgrade the baseline from discuss-only framing to a stable, conservative, artifact-backed adjacent integration lane suitable for manuscript-safe reporting in the current paper phase.

## Canonical provenance locked

- Canonical paper: https://arxiv.org/abs/2305.20050
- Canonical PDF: https://arxiv.org/pdf/2305.20050.pdf
- DOI: https://doi.org/10.48550/arXiv.2305.20050
- Official repository: https://github.com/openai/prm800k

## Implemented assets

### New contract

- `configs/lets_verify_step_by_step_adjacent_comparison_contract_v1.json`

Defines official source mapping, benchmark subset rules, compute normalization rules, required artifacts, exercised vs non-reproduced ingredients, and allowed/forbidden claims.

### New validator

- `scripts/verify_lets_verify_step_by_step_import.py`

Checks:

- contract completeness,
- official repo mapping/layout expectations,
- package structure (`metadata.json`, `results.csv`),
- benchmark split expectations,
- schema/column validity,
- adjacent-only scope and numeric sanity.

### New canonical runner

- `scripts/run_lets_verify_step_by_step_adjacent_integration.py`

Provides a stable partial-runnable adjacent lane with explicit failure modes and canonical artifact export.

### New status generator

- `scripts/generate_lets_verify_step_by_step_status_report.py`

Produces machine-readable completeness status artifacts under `outputs/external_baseline_completeness/`.

### Integration fixture

- `tests/fixtures/lets_verify_step_by_step_import_valid/metadata.json`
- `tests/fixtures/lets_verify_step_by_step_import_valid/results.csv`

Provides a stable contract-valid import slice for repeatable checks.

## Canonical output artifact family

- `outputs/lets_verify_step_by_step_adjacent_integration/<run_id>/`

Contains:

- `status.json`
- `comparison_readiness.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `config_snapshot.json`
- `commands_snapshot.txt`
- `comparison_ready_rows.csv`
- `validation_status.csv`
- `verification_report.json`
- `official_repo_structure.json`

## Final classification and guardrails

- Final strengthened classification: **`partial_runnable_adjacent`**
- Matrix-safe normalized status: **`import_validated` + `adjacent`**

Safe:

- official, reviewer-relevant adjacent baseline lane with auditable artifacts.

Unsafe:

- full faithful reproduction claims,
- direct control-equivalence claims with branch-level marginal budget allocation,
- API-substitute behavior presented as official baseline behavior.

## Remaining out of scope

- full paper-scale training/evaluation reproduction,
- internal/non-public model assets,
- cross-method claims that erase action-space mismatch between process-verifier methods and frontier allocation methods.

## Paper-phase readiness judgment

For the current paper phase this baseline is effectively **done** as an adjacent comparator lane: stable, explicit, machine-readable, and manuscript-safe.
