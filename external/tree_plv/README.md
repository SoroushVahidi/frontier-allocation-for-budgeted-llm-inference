# Tree-PLV external baseline note (official paper-cited adjacent lane)

## Canonical identity

- **Canonical title:** *Advancing Process Verification for Large Language Models via Tree-Based Preference Learning*
- **Canonical paper URL:** https://aclanthology.org/2024.emnlp-main.125/
- **Official paper PDF:** https://aclanthology.org/2024.emnlp-main.125.pdf
- **DOI:** https://doi.org/10.18653/v1/2024.emnlp-main.125
- **arXiv:** https://arxiv.org/abs/2407.00390
- **Paper-cited repository:** https://github.com/Hareta-Leila/Tree-PLV

## Current repo-side classification

- **Normalized matrix status:** `import_validated`
- **Operational strengthened lane:** `partial_runnable_adjacent`
- **Control equivalence:** `adjacent`

Tree-PLV is reviewer-relevant and officially paper-backed, but it is **not** treated as a direct control-equivalent frontier branch-allocation baseline.

## What was directly verified in this pass

From direct audit of the cited repository (`Hareta-Leila/Tree-PLV`) and canonical paper links:

- Canonical paper identity and publication metadata are publicly verifiable via ACL Anthology and DOI.
- The paper-cited GitHub repository is publicly accessible and clonable.
- The audited repository snapshot contains directories and docs that expose command-level runnable surfaces in `LLMs-Planning/*` READMEs.

## Important negative findings (honesty guardrails)

- No root `LICENSE*`/`COPYING` file was visible in the audited repository snapshot.
- No official pretrained checkpoints were clearly documented in the audited root README.
- No single end-to-end, benchmark-faithful Tree-PLV reproduction command was identified in the cited repo during this pass.

These negative findings are why the lane stays **adjacent** and **partial-runnable**, not full faithful reproduction.

## Canonical in-repo integration assets

- Contract: `configs/tree_plv_adjacent_comparison_contract_v1.json`
- Validator: `scripts/verify_tree_plv_import.py`
- Runner: `scripts/run_tree_plv_adjacent_integration.py`
- Status generator: `scripts/generate_tree_plv_status_report.py`
- Integration note: `docs/tree_plv_integration.md`

## Canonical output family

- `outputs/tree_plv_adjacent_integration/<run_id>/`

Expected artifacts:

- `status.json`
- `comparison_readiness.json`
- `summary.json`
- `summary.md`
- `manifest.json`
- `config_snapshot.json`
- `commands_snapshot.txt`
- `comparison_ready_rows.csv`

## Safe and unsafe claims

Safe now:

- Tree-PLV is integrated as an **official-paper-cited adjacent** baseline with a stable artifact-backed partial-runnable lane.
- This lane validates provenance and contract constraints and exports machine-readable outputs for adjacent-only tables.

Unsafe now:

- Claiming full faithful in-repo reproduction of the complete Tree-PLV paper stack.
- Claiming direct control equivalence to branch-level marginal budget-allocation methods.
- Claiming verified official checkpoint reproduction from this lane.
