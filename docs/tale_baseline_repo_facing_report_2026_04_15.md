# TALE baseline integration report (2026-04-15)

## Implemented

- Added a canonical TALE integration spec separating:
  - MODE A (`prompt_budgeting_inference_only`): faithful in-repo prompt-level adaptive token-budgeting adapter.
  - MODE B (`official_full_adapter`): official/full adapter reporting path with explicit non-equivalence caveat.
- Added runnable TALE baseline scripts and TALE configs.
- Extended external-style comparison integration to include TALE adapter in local matched comparisons.

## Added files

- `docs/tale_baseline_integration.md`
- `docs/tale_baseline_repo_facing_report_2026_04_15.md`
- `configs/tale_prompt_budgeting_v1.json`
- `configs/tale_official_adapter_v1.json`
- `scripts/run_tale_baseline.py`
- `scripts/run_tale_comparison_bundle.py`
- `external/tale_token_budget_aware_reasoning/README.md`

## Modified files

- `experiments/controllers.py`
- `experiments/frontier_matrix_core.py`
- `scripts/run_light_external_style_baseline_comparison.py`
- `docs/main_baselines.md`
- `external/README.md`
- `configs/README.md`
- `configs/external_baselines_registry.json`
- `scripts/README.md`

## Runnable status

- MODE A: fully runnable in this repository.
- MODE B: partial adapter path; complete only when official/full TALE outputs are supplied/imported.

## TALE-PT status

- TALE-PT is **not** implemented as an in-repo full reproduction.
- TALE-PT is treated as part of MODE B official/full external path only.

## Remaining assumptions and blockers

- Prompt-level budget estimator is adapted (`char_length_linear`) to fit this repo’s environment.
- This repo does not automatically reproduce TALE-PT training/eval stack from official code.
- Perfect full reproduction requires external official assets and dedicated reproduction workflow.

## Safe manuscript wording

- "We include a faithful in-repo TALE-style prompt token-budgeting adapter (MODE A) under matched-compute reporting."
- "We separately report official/full TALE results when available (MODE B), and do not claim strict control-space equivalence with frontier stop-vs-act policies."
