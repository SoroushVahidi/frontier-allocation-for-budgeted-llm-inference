# Cohere real accuracy comparison run (2026-04-29, diagnostic)

## Scope requested
- Datasets: `openai/gsm8k`, `HuggingFaceH4/MATH-500`
- Budgets: `4,6,8`
- Seeds: `11,23`
- Provider/model: `cohere/command-r-plus-08-2024`
- Default target: `--target-scored-per-slice 50 --max-examples 50`

## Execution status
- Cohere API readiness passed (authenticated tiny request).
- The requested full run was started, then a reduced run was started for throughput control.
- Both were interrupted before completing all slices due runtime/throughput constraints in this session.
- Current outputs are partial and should be treated as diagnostic only.

## Methods unavailable/excluded
See `docs/methods_excluded_20260429T_REAL_COHERE_FULL_ACCURACY.csv`.

## Notes
- No algorithmic changes were made in this pass.
- Canonical paper tables were not edited.
- `docs/PAPER_SOURCE_OF_TRUTH.md` was not modified.
