# adaptive-reasoning-budget-allocation

## External baseline code

A license-aware status summary for baseline code resources is available at [`external/README.md`](external/README.md).

## Main datasets

The current research-facing dataset package is documented in [`docs/main_datasets.md`](docs/main_datasets.md) and the practical access/setup workflow is in [`docs/datasets_access.md`](docs/datasets_access.md). Repository data-handling policy and placeholder structure are described in [`datasets/README.md`](datasets/README.md). These documents are conservative by design and explicitly mark uncertain details or access conditions for later manual verification.

## Pilot experiment

The repository now includes a lightweight GSM8K pilot scaffold for testing basic adaptive reasoning-branch allocation ideas against simple baselines.

- Pilot description: [`experiments/pilot_gsm8k.md`](experiments/pilot_gsm8k.md)
- Default config: [`configs/pilot_gsm8k.yaml`](configs/pilot_gsm8k.yaml)
- Run command:
  - `python scripts/run_pilot_gsm8k.py --config configs/pilot_gsm8k.yaml`
- Evaluate command:
  - `python scripts/evaluate_pilot_gsm8k.py outputs/pilot/<run_id>`

This pilot is intentionally provisional and research-friendly: it can run in local simulation mode when no external model API is wired, while keeping controller logic and outputs easy to inspect.
