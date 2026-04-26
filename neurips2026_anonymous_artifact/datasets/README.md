# Datasets directory policy

This directory is for dataset policy/manifests and controlled derived metadata.
Raw dataset dumps are not committed.

## Role split

1. **Main evaluation datasets** (benchmark-facing): see `docs/main_datasets.md`.
2. **External reasoning-supervision datasets** (new-paper prep): see `docs/DATASET_STATUS.md` and `configs/external_reasoning_datasets_registry.json`.
3. **Readiness/preparation artifacts**: generated under `outputs/` by scripts, not checked in.

## Core policy

- Fetch from official sources only.
- Respect licensing and gating restrictions.
- Keep download-on-demand behavior.
- Keep provenance in small metadata/report files.
- Do not present integration status as equivalent to final method performance.

## Useful commands

```bash
# Main evaluation dataset access status
python scripts/verify_hf_dataset_access.py --output-dir outputs/hf_dataset_access

# Main dataset integration report
python scripts/generate_dataset_integration_report.py

# External reasoning-supervision integration report
python scripts/generate_external_reasoning_dataset_integration_report.py

# External reasoning-supervision readiness ranking/previews
python scripts/prepare_external_reasoning_datasets.py
```
