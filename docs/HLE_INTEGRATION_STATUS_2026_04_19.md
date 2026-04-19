# HLE integration status (2026-04-19)

## What was added

- Canonical HLE dataset integration is now wired to `cais/hle` in the HF dataset registry.
- Conservative subset keys were added for pipeline-safe usage:
  - `cais/hle_text_only`
  - `cais/hle_exact_answer`
  - `cais/hle_mcq`
  - `cais/hle_auto_gradable`
- Aliases now resolve:
  - `hle` / `HLE` -> `cais/hle`
  - `hle_text_only` / `hle_text` -> `cais/hle_text_only`
  - `hle_exact_answer` -> `cais/hle_exact_answer`
  - `hle_mcq` -> `cais/hle_mcq`
  - `hle_auto_gradable` -> `cais/hle_auto_gradable`

## Scope and readiness

- **Status:** partially added.
- **Experiment readiness in this repo right now:** partially ready.
  - Ready: text-only + auto-gradable slices (`cais/hle_auto_gradable`, and related text-only exact/MCQ subsets).
  - Not yet ready: full multimodal HLE usage (prompt/rationale images), because this repository does not yet include multimodal evaluation plumbing in the adaptive compute pipeline.

## Why partial (honest limitation)

`cais/hle` contains mixed modality data (text + image-bearing rows). This pass integrates canonical access and safe filtering, but does **not** claim full multimodal evaluation readiness.

## Best next step

Add explicit multimodal inference/evaluation policy (image loading, model IO contract, and score normalization) before claiming full HLE experiment readiness.
