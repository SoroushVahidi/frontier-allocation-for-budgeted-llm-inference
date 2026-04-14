# Datasets directory policy

This folder is reserved for dataset access instructions, manifests, and controlled derived artifacts.

## Policy

- Raw datasets are **not** committed to this repository by default.
- Data-fetch scripts/instructions should retrieve data from official sources only.
- Processed artifacts should be written to controlled subfolders with clear provenance metadata.
- Licensing and usage terms must be respected per dataset.
- If a dataset is gated or terms-restricted, do not redistribute its raw contents in this repo.

## Current dataset access status (working plan)

- **Wired in code (`experiments/hf_datasets.py`):** GSM8K, MATH (`hendrycks/competition_math` + `EleutherAI/hendrycks_math`), GPQA Diamond, AIME 2024 card (`HuggingFaceH4/aime_2024`), OlympiadBench (`Hothan/OlympiadBench`), optional LiveCodeBench.
- **Documentation-only (no HF loader):** NaturalPlan — use upstream GitHub per license; pin commit; do not commit raw data.
- May require approval/terms acceptance: GPQA Diamond (HF gated when applicable).

- **New-paper external reasoning-supervision integrations (download-on-demand):** `tasksource/PRM800K`, `peiyi9979/Math-Shepherd` (swap option: `trl-lib/math_shepherd`), `openbmb/UltraInteract_pair`, `openbmb/UltraInteract_sft` via `experiments/external_reasoning_datasets.py`.

See also: `docs/main_datasets.md`, `docs/datasets_access.md`, and `python scripts/generate_dataset_integration_report.py` for a generated status report under `outputs/` (gitignored by default).

## TODO

- Add machine-readable manifests for dataset versions/snapshots used in experiments.
- Add fetch scripts that pin revisions and log source URLs/checksums where possible.
- Add per-dataset license/terms notes once each source path is finalized.

Additional report tooling: `python scripts/generate_external_reasoning_dataset_integration_report.py` writes run-scoped JSON/MD/CSV artifacts under `outputs/external_reasoning_datasets/<run_id>/`.

Expanded new-paper integration now also covers DeepStep-Math-5K, WebInstruct-verified, JudgeLM (both cards), MT-Bench human judgments, Prometheus collections, math_verify-style HF release, and ARCTraj via the same download-on-demand inspection pipeline.
