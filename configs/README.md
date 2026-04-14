# Configs

YAML and JSON configuration for experiments and tooling.

## Current files

| File | Purpose |
|------|---------|
| [`pilot_gsm8k.yaml`](pilot_gsm8k.yaml) | Default GSM8K pilot (`scripts/run_pilot_gsm8k.py`) |
| [`external_baselines_registry.json`](external_baselines_registry.json) | Machine-readable external baseline URLs and status (no vendored code) |
| [`external_reasoning_datasets_registry.json`](external_reasoning_datasets_registry.json) | New-paper external reasoning supervision candidates (HF IDs + supervision taxonomy) |

## Conventions

- Prefer **`outputs/`** for all run artifacts (gitignored except `.gitkeep`). The legacy singular `output/` path is deprecated and ignored by git.
- Keep configs small and reproducible; document uncertain parameters in the matching `docs/` or `experiments/` note rather than in comments alone.

## Planned (optional)

Shared defaults and per-benchmark YAML can be added as experiments stabilize—for example `defaults.yaml`, `gsm8k_baselines.yaml`, and dataset-specific overrides.
