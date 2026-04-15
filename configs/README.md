# Configs

YAML and JSON configuration for experiments and tooling.

## Current files

| File | Purpose |
|------|---------|
| [`pilot_gsm8k.yaml`](pilot_gsm8k.yaml) | Default GSM8K pilot (`scripts/run_pilot_gsm8k.py`) |
| [`external_baselines_registry.json`](external_baselines_registry.json) | Machine-readable external baseline URLs and status (no vendored code) |
| [`external_reasoning_datasets_registry.json`](external_reasoning_datasets_registry.json) | New-paper external reasoning supervision candidates (HF IDs + supervision taxonomy) |
| [`oracle_label_generator_interface_contract_v1.json`](oracle_label_generator_interface_contract_v1.json) | Machine-readable heavy-generator input/output/invariant contract for oracle-label pilot v1 |
| [`stop_vs_act_oracle_selective_distillation_v1.json`](stop_vs_act_oracle_selective_distillation_v1.json) | Selective distillation policy (accepted/borderline/rejected buckets, weights, soft-target settings) for post-pilot oracle labels |
| [`stop_vs_act_oracle_distilled_student_train_v1.json`](stop_vs_act_oracle_distilled_student_train_v1.json) | Default settings for first oracle-distilled stop-vs-act student train/eval path (post-pilot) |
| [`s1_budget_forcing_inference_only_v1.json`](s1_budget_forcing_inference_only_v1.json) | MODE A primary fair baseline: s1-style inference budget forcing on unchanged base model family |
| [`s1_full_or_official_adapter_v1.json`](s1_full_or_official_adapter_v1.json) | MODE B secondary path: full/official s1 reporting adapter (includes post-training caveat) |
| [`tale_prompt_budgeting_v1.json`](tale_prompt_budgeting_v1.json) | MODE A TALE baseline: faithful in-repo prompt-level adaptive token budgeting adapter |
| [`tale_official_adapter_v1.json`](tale_official_adapter_v1.json) | MODE B TALE baseline: official/full adapter reporting path (separately labeled, may include TALE-PT) |
| [`l1_inference_adapter_v1.json`](l1_inference_adapter_v1.json) | MODE A L1 baseline: inference-only L1-style length-conditioned adapter (Exact + Max variants) |
| [`l1_official_full_adapter_v1.json`](l1_official_full_adapter_v1.json) | MODE B L1 baseline: official/full adapter reporting path (separately labeled, may include RL-trained L1 checkpoints) |

## Conventions

- Prefer **`outputs/`** for all run artifacts (gitignored except `.gitkeep`). The legacy singular `output/` path is deprecated and ignored by git.
- Keep configs small and reproducible; document uncertain parameters in the matching `docs/` or `experiments/` note rather than in comments alone.

## Planned (optional)

Shared defaults and per-benchmark YAML can be added as experiments stabilize—for example `defaults.yaml`, `gsm8k_baselines.yaml`, and dataset-specific overrides.
