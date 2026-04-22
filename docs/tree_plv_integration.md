# Tree-PLV integration note (official paper-cited adjacent partial-runnable lane)

## Canonical identification

- **Paper title:** *Advancing Process Verification for Large Language Models via Tree-Based Preference Learning*
- **Paper URL:** https://aclanthology.org/2024.emnlp-main.125/
- **Paper PDF:** https://aclanthology.org/2024.emnlp-main.125.pdf
- **DOI:** https://doi.org/10.18653/v1/2024.emnlp-main.125
- **arXiv:** https://arxiv.org/abs/2407.00390
- **Paper-cited repository:** https://github.com/Hareta-Leila/Tree-PLV

## Problem class and safest repository classification

- **Native method class:** tree-based process verification / preference learning for reasoning verification.
- **Provenance level (this repo):** `official_paper_and_paper_cited_repo`
- **Normalized matrix status (this repo):** `import_validated`
- **Operational strengthened classification:** `partial_runnable_adjacent`
- **Control-equivalence label (this repo):** `adjacent`

Tree-PLV is an important reviewer-facing verifier/search-adjacent baseline, but it is not treated as direct control-equivalent to branch-level marginal allocation.

## Canonical contract and scripts

- Contract: `configs/tree_plv_adjacent_comparison_contract_v1.json`
- Validator: `scripts/verify_tree_plv_import.py`
- Runner: `scripts/run_tree_plv_adjacent_integration.py`
- Status generator: `scripts/generate_tree_plv_status_report.py`

## Canonical output family

- `outputs/tree_plv_adjacent_integration/<run_id>/`

Required artifacts:

- `status.json`
- `comparison_readiness.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `config_snapshot.json`
- `commands_snapshot.txt`
- `comparison_ready_rows.csv`

Optional artifacts:

- `verification_report.json`
- `official_repo_structure.json`
- `validation_status.csv`

## What this lane exercises now

- Canonical paper identity checks (ACL/DOI/arXiv).
- Paper-cited repository mapping and repository-layout checks.
- Contract-bound benchmark import validation for a stable adjacent slice.
- Machine-readable adjacent-only export for aggregation/bundle scripts.

## What this lane does not reproduce

- Full Tree-PLV training and complete benchmark reproduction.
- Official checkpoint-based metric replication.
- Direct branch-allocation control behavior.

## Direct audit findings used for classification

From direct inspection of `https://github.com/Hareta-Leila/Tree-PLV` in this pass:

- Repository is publicly clonable and contains meaningful code/doc structure.
- Root README in audited snapshot is effectively empty/minimal.
- No root license file was visible in the audited snapshot.
- No explicit checkpoint-release documentation was identified during audit.

Given these facts, an honest, stable lane is **partial_runnable_adjacent**, not full faithful reproduction.

## Safe manuscript wording

> We integrate Tree-PLV as an official-paper-cited adjacent baseline through a conservative contract-validated partial-runnable lane. This lane validates provenance and import/structure requirements with machine-readable artifacts, while remaining explicitly adjacent-only and not a full faithful in-repo reproduction.
