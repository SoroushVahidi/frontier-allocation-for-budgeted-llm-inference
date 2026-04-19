# Dataset addition status note (2026-04-19)

Requested datasets for this pass:
1. AIME 2025
2. LiveCodeBench
3. HMMT
4. BRUMO
5. Humanity's Last Exam (HLE)
6. MMLU-Pro

## Outcome summary

- **Successfully integrated:** AIME 2025, HMMT, BRUMO, MMLU-Pro.
- **Partially integrated:** LiveCodeBench (data loader + normalization only; no execution-grade evaluator wiring yet).
- **Not integrated:** HLE (gated access prevented schema/split inspection in this environment).

See machine-readable audit files for full per-dataset fields:
- `docs/dataset_addability_audit_2026_04_19.json`
- `docs/dataset_addability_audit_2026_04_19.csv`

## Repository-consistent integration details

Code integration was kept inside the existing dataset layer (`experiments/hf_datasets.py`) and existing dataset-registry tests (`tests/test_dataset_registry.py`).

Added canonical dataset specs and aliases:
- `MathArena/aime_2025` (`aime_2025` alias)
- `MathArena/hmmt_feb_2025` (`hmmt`, `HMMT` aliases)
- `MathArena/brumo_2025` (`brumo`, `BRUMO` aliases)
- `TIGER-Lab/MMLU-Pro` (`mmlu-pro`, `MMLU-Pro`, `mmlu_pro` aliases)
- `livecodebench/code_generation` (`livecodebench` alias)

Added role-map and ambiguity-regime tags so these datasets can be tracked consistently in evaluation planning.

Normalization extensions were minimal:
- MMLU-Pro rows now preserve options, answer index, and category metadata.
- LiveCodeBench code-generation rows now preserve public/private testcase metadata fields for future verifier/execution integration.

## Why some outcomes are partial/not-added

### LiveCodeBench — partially integrated

The dataset can be loaded and normalized, but the repo does not yet include the full execution harness and official testcase grading path needed for end-to-end fixed-budget code evaluation. This makes it **dataset-layer ready** but not **evaluation-ready**.

### HLE — not integrated

The canonical source (`cais/hle`) is gated in this environment. Without access, this pass could not safely verify available text-only/auto-gradable subsets or lock schema assumptions. Rather than guessing schema, this pass records a clean not-added status.

## Best next step

1. Obtain HLE access and integrate only text-only + automatically gradable subsets first.
2. Add a bounded LiveCodeBench execution evaluator adapter (sandbox/testcase runner + pass/fail scorer) compatible with current fixed-budget evaluation logging.
3. Keep AIME/HMMT/BRUMO/MMLU-Pro in evaluation-set sweeps to test transfer and branch-allocation behavior under mixed exact-answer and MCQ regimes.
