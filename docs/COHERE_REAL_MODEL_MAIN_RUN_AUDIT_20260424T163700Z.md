# Cohere real-model main-run audit (20260424T163700Z)

## Artifact sources inspected
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_4_HuggingFaceH4_MATH-500`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_4_HuggingFaceH4_aime_2024`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_4_openai_gsm8k`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_6_HuggingFaceH4_MATH-500`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_6_HuggingFaceH4_aime_2024`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_6_openai_gsm8k`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_8_HuggingFaceH4_MATH-500`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_8_HuggingFaceH4_aime_2024`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_11_8_openai_gsm8k`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_4_HuggingFaceH4_MATH-500`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_4_HuggingFaceH4_aime_2024`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_4_openai_gsm8k`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_6_HuggingFaceH4_MATH-500`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_6_HuggingFaceH4_aime_2024`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_6_openai_gsm8k`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_8_HuggingFaceH4_MATH-500`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_8_HuggingFaceH4_aime_2024`
- `outputs/canonical_real_model_validation_20260424T_COHERE_REAL_MAIN_cohere_23_8_openai_gsm8k`
- `outputs/real_model_ours_vs_external_validation_20260424T_COHERE_REAL_MAIN`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_4_HuggingFaceH4_MATH-500.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_4_HuggingFaceH4_aime_2024.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_4_openai_gsm8k.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_6_HuggingFaceH4_MATH-500.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_6_HuggingFaceH4_aime_2024.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_6_openai_gsm8k.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_8_HuggingFaceH4_MATH-500.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_8_HuggingFaceH4_aime_2024.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_11_8_openai_gsm8k.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_4_HuggingFaceH4_MATH-500.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_4_HuggingFaceH4_aime_2024.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_4_openai_gsm8k.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_6_HuggingFaceH4_MATH-500.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_6_HuggingFaceH4_aime_2024.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_6_openai_gsm8k.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_8_HuggingFaceH4_MATH-500.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_8_HuggingFaceH4_aime_2024.md`
- `docs/CANONICAL_REAL_MODEL_VALIDATION_20260424T_COHERE_REAL_MAIN_cohere_23_8_openai_gsm8k.md`
- `docs/REAL_MODEL_OURS_VS_EXTERNAL_VALIDATION_20260424T_COHERE_REAL_MAIN.md`
- `logs/slurm/cohere_real_main_979423.err`
- `logs/slurm/cohere_real_main_979423.out`

## Contract checked
- Provider/model: `cohere/command-r-plus-08-2024`
- Datasets: `['openai/gsm8k', 'HuggingFaceH4/MATH-500', 'HuggingFaceH4/aime_2024']`
- Budgets: `[4, 6, 8]`
- Seeds: `[11, 23]`
- Subset size: `20`
- Methods: `['strict_f3', 'strict_gate1_cap_k6', 'strict_f2', 'external_l1_max', 'self_consistency_3']`

## Claim-safety summary
- A (`strict_f3` > `strict_gate1_cap_k6`): **yes**
- B (frontier-allocation > `external_l1_max`): **no**
- C (competitive not dominant): **yes**
- D (disposition): **appendix-only**

## Missing or incomplete slices
- `openai/gsm8k` seed `11` budget `4`: insufficient_scored_examples:93<100
- `openai/gsm8k` seed `11` budget `6`: insufficient_scored_examples:90<100|severe_retry_error_log:10>=10
- `openai/gsm8k` seed `11` budget `8`: insufficient_scored_examples:97<100
- `openai/gsm8k` seed `23` budget `4`: insufficient_scored_examples:79<100|severe_retry_error_log:21>=10
- `openai/gsm8k` seed `23` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `openai/gsm8k` seed `23` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/MATH-500` seed `11` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/MATH-500` seed `11` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/MATH-500` seed `11` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/MATH-500` seed `23` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/MATH-500` seed `23` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/MATH-500` seed `23` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/aime_2024` seed `11` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/aime_2024` seed `11` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/aime_2024` seed `11` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/aime_2024` seed `23` budget `4`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/aime_2024` seed `23` budget `6`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing
- `HuggingFaceH4/aime_2024` seed `23` budget `8`: insufficient_scored_examples:0<100|insufficient_methods:0<5|missing_methods:strict_f3|strict_gate1_cap_k6|strict_f2|external_l1_max|self_consistency_3|severe_retry_error_log:100>=10|doc_main_bounded_findings_empty_or_missing

## Safe manuscript guidance
Treat Cohere real-model evidence as appendix calibration unless and until dominance over `external_l1_max` is robust across full slices.
