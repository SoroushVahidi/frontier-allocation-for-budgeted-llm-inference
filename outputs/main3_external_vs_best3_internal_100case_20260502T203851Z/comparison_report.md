# Main3 External vs Best3 Internal (100-case) Report

- Output directory: `outputs/main3_external_vs_best3_internal_100case_20260502T203851Z`
- Runner output directory: `outputs/cohere_real_model_cost_normalized_validation_20260502T203851Z`
- External baselines: `external_l1_max`, `tale`, `s1`
- Internal methods: `strict_f3`, `strict_gate1_cap_k6`, `strict_f2`
- Dataset/slice: `openai/gsm8k` test, fixed seed and matched budget.
- This artifact is diagnostic/supporting evidence; interpret with repository claim-safety docs.

## How to interpret
- `method_level_metrics.csv` provides per-method scored counts, failures, and accuracy.
- `comparison_table.csv` ranks all six methods by accuracy on the matched run settings.
- `per_case_results.jsonl` preserves case-level status and outcomes.
