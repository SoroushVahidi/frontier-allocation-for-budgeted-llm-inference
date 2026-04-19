# Dataset experiment-readiness status (integration-to-usable pass)

This note distinguishes **dataset registry integration** from **actual experiment readiness** for the newly integrated datasets.

## Scope covered

- MathArena/aime_2025
- MathArena/hmmt_feb_2025
- MathArena/brumo_2025
- TIGER-Lab/MMLU-Pro
- livecodebench/code_generation (+ execution-v2 alias path)
- lmms-lab/HLE-Verified (included because it is present in the current dataset registry)

## Canonical runner assumptions verified in this repo

- Current pilot/frontier runners consume examples in a simple `(question, answer)` shape and compute correctness by normalized exact-answer matching.
- Math-style extraction (`extract_final_answer`) is primary; MCQ and code-generation-specific scoring paths are not yet first-class in the main runner stack.
- Loader-side sampling already preserves optional dataset metadata (for example MMLU-Pro options/category and LiveCodeBench test-case fields), but runner-time usage of those fields is limited.

## Status summary

### experiment_ready

- `MathArena/aime_2025`
- `MathArena/hmmt_feb_2025`
- `MathArena/brumo_2025`

Why: these datasets align with exact-answer math assumptions, normalize cleanly into `(question, answer)`, and fit current runner/evaluation behavior.

### partially_ready

- `TIGER-Lab/MMLU-Pro`
  - Load/normalization is available and metadata is preserved.
  - Blocker: current runner is not MCQ-native (option-constrained decoding/evaluation not explicit).

- `livecodebench/code_generation`
- `livecodebench/execution-v2`
  - Load/normalization and metadata retention are available.
  - Blocker: repository does not yet provide an end-to-end, production-safe code-generation execution grader for benchmark claims.

- `lmms-lab/HLE-Verified`
  - Text-first loading works.
  - Blocker: multimodal/image-aware evaluation path is not wired in the current pilot runner family.

### not_ready

- None in this scoped pass (for datasets already integrated into this repo registry).

## Added readiness invocation bundles

See `configs/dataset_experiment_readiness_bundles.json` for:

- `exact_answer_math_expansion`
- `breadth_control_mcq`
- `code_generation_partial`

## Machine-readable report

- `docs/reports/dataset_experiment_readiness_report.json`
- `docs/reports/dataset_experiment_readiness_report.csv`

## Best next steps

1. Add an MCQ-native runner/evaluator path that consumes `options` + `answer_index` for MMLU-Pro.
2. Add a hardened code-execution benchmark path for LiveCodeBench with deterministic testcase grading and safety boundaries.
3. Add explicit text-only vs multimodal policy support for HLE-Verified.
