# Configs

This directory contains configuration files for experiments.

> **Placeholder — configs will be added as experiments are implemented.**

---

## Planned Structure

Experiment configurations will be stored as YAML files, one per experiment or experiment group.

```
configs/
├── README.md               # This file
├── defaults.yaml           # Shared default parameters
├── gsm8k_baselines.yaml    # GSM8K baseline experiments
├── gsm8k_adaptive.yaml     # GSM8K adaptive allocation experiments
└── math_adaptive.yaml      # MATH dataset experiments
```

---

## Configuration Format (Planned)

Each config file will specify:

- `model`: Model name or path.
- `benchmark`: Dataset name and split.
- `budget`: Total inference budget (tokens or calls).
- `strategy`: Allocation strategy name.
- `strategy_params`: Strategy-specific hyperparameters.
- `seed`: Random seed(s).
- `output_dir`: Where to save results.

---

## Notes

- Configs should be self-contained and reproducible.
- Use `configs/defaults.yaml` for shared parameters; override in per-experiment files.
- All configs should be tracked in version control.
