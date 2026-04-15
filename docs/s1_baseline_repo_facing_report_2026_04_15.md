# s1 baseline integration report (2026-04-15)

## Implemented

- Added a new canonical integration spec that separates:
  - MODE A inference-only s1 budget forcing (primary, fair, same-base-model comparison), and
  - MODE B full/official path (secondary, separately labeled, post-training caveat).
- Added runnable scripts for:
  - per-run s1 baseline execution + artifact emission,
  - multi-run comparison bundle aggregation.
- Added explicit MODE A / MODE B config files.
- Updated baseline and external docs to reflect the fair split and conservative claim policy.

## Files added/modified

### Added
- `docs/s1_baseline_integration.md`
- `docs/s1_baseline_repo_facing_report_2026_04_15.md`
- `configs/s1_budget_forcing_inference_only_v1.json`
- `configs/s1_full_or_official_adapter_v1.json`
- `scripts/run_s1_budget_forcing_baseline.py`
- `scripts/run_s1_baseline_comparison_bundle.py`

### Modified
- `docs/main_baselines.md`
- `external/README.md`
- `external/s1_simple_test_time_scaling/README.md`
- `configs/README.md`
- `configs/external_baselines_registry.json`
- `scripts/README.md`

## Run readiness by mode

- **MODE A (`inference_only`)**: fully runnable in this repository.
- **MODE B (`full_or_official`)**: partial adapter/reporting path; complete only when official/full s1 outputs are provided/imported.

## Remaining assumptions

- Action-budget to token-budget conversion is reported via explicit token-equivalent mapping.
- Inference-only adapter captures the core budget-forcing behavior, not exact tokenizer/serving internals from upstream vLLM.

## Current blockers for perfect full reproduction

- Official s1 post-training and evaluation stack is not automatically reproduced in this repository.
- Full MODE B completion depends on externally produced official/full artifacts (or future dedicated in-repo reproduction work).
