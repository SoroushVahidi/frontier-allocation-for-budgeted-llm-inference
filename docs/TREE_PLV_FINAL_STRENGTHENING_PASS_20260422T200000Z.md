# Tree-PLV final strengthening pass (2026-04-22T20:00:00Z)

## Objective

Upgrade Tree-PLV from discuss-only framing to a conservative, artifact-backed, manuscript-safe adjacent lane with explicit provenance and scope boundaries.

## Official and paper-cited links used

- Canonical paper page: https://aclanthology.org/2024.emnlp-main.125/
- Official paper PDF: https://aclanthology.org/2024.emnlp-main.125.pdf
- DOI: https://doi.org/10.18653/v1/2024.emnlp-main.125
- arXiv: https://arxiv.org/abs/2407.00390
- Paper-cited repo: https://github.com/Hareta-Leila/Tree-PLV

## Direct cited-repo audit summary

Audit source: direct clone/inspection of `Hareta-Leila/Tree-PLV`.

Observed:

- Repository is publicly accessible and clonable.
- Audited snapshot contains `LLMs-Planning/` and `dschat/` trees with non-trivial structure.
- Planning README files include runnable command surfaces.

Not observed in this pass:

- root `LICENSE` file,
- clearly documented official checkpoint releases,
- one-command benchmark-faithful full Tree-PLV reproduction workflow.

## Implemented assets

### Canonical adjacent comparison contract

- `configs/tree_plv_adjacent_comparison_contract_v1.json`

### Canonical validator

- `scripts/verify_tree_plv_import.py`

Checks:

- contract completeness,
- paper↔repo mapping constraints,
- optional cited-repo path/layout/license-visibility checks,
- dataset/split and schema checks,
- adjacent-only scope enforcement.

### Canonical runner

- `scripts/run_tree_plv_adjacent_integration.py`

Provides a stable partial-runnable adjacent lane and canonical output export with explicit failure modes.

### Status generator

- `scripts/generate_tree_plv_status_report.py`

Writes machine-readable status docs for cross-repo status navigation.

### Stable fixture slice

- `tests/fixtures/tree_plv_import_valid/metadata.json`
- `tests/fixtures/tree_plv_import_valid/results.csv`

## Canonical output artifact family

- `outputs/tree_plv_adjacent_integration/<run_id>/`

Includes:

- `status.json`
- `comparison_readiness.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `config_snapshot.json`
- `commands_snapshot.txt`
- `comparison_ready_rows.csv`
- `verification_report.json`
- `official_repo_structure.json`
- `validation_status.csv`

## Final classification and safety boundary

- Matrix status: `import_validated`
- Operational lane strength: `partial_runnable_adjacent`
- Control-equivalence: `adjacent`

Safe:

- official-paper-cited adjacent baseline with artifact-backed partial-runnable lane.

Unsafe:

- full faithful in-repo Tree-PLV reproduction claim,
- direct control-equivalent branch-allocation claim,
- checkpoint-faithful replication claim.

## Remaining out of scope

- full official checkpoint training/eval reproduction,
- legal/licensing certainty beyond what was directly visible in audited repo snapshot,
- converting verifier/preference-learning behavior into direct frontier-allocation equivalence.

## Paper-phase readiness judgment

For the current paper phase, Tree-PLV is now effectively **done** as a stable, honest, reviewer-defensible **adjacent partial-runnable lane**.
