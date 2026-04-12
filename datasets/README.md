# Datasets directory policy

This folder is reserved for dataset access instructions, manifests, and controlled derived artifacts.

## Policy

- Raw datasets are **not** committed to this repository by default.
- Data-fetch scripts/instructions should retrieve data from official sources only.
- Processed artifacts should be written to controlled subfolders with clear provenance metadata.
- Licensing and usage terms must be respected per dataset.
- If a dataset is gated or terms-restricted, do not redistribute its raw contents in this repo.

## Current dataset access status (working plan)

- Public (expected): GSM8K, MATH, AIME (source-path verification pending), OlympiadBench, NaturalPlan, LiveCodeBench.
- May require approval/terms acceptance: GPQA Diamond.

## TODO

- Add machine-readable manifests for dataset versions/snapshots used in experiments.
- Add fetch scripts that pin revisions and log source URLs/checksums where possible.
- Add per-dataset license/terms notes once each source path is finalized.
