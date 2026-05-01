# Commands / assumptions / caveats

## Command
- python scripts/run_canonical_real_model_validation.py --timestamp 20260424T_COHERE_REAL_MAIN_PATCH_20260424T163922Z_cohere_11_4_openai_gsm8k

## Assumptions + caveats
- Canonical bounded real-model validation using APIBranchGenerator.
- Provider/model: cohere/command-r-plus-08-2024.
- Evaluation correctness uses choose_repair_answer + canonicalize_answer as manuscript-facing contract.
- Failure decomposition categories: absent_from_tree, present_not_selected, output_layer_mismatch.
- Errors are logged in retry_error_log.csv and excluded from accuracy denominators.
