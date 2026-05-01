# Cohere readiness failure report

- failure_type: `sdk_missing`
- model_requested: `command-a-03-2025`
- sdk_import_status: `missing`
- COHERE_API_KEY present: `True`
- sanitized_error_message: `No module named 'cohere'`

- rerun_command: `python scripts/run_l1_loss_decomposition_for_best_selector.py --timestamp 20260501T000000Z --provider cohere --dataset openai/gsm8k --split test --seed 20260501 --budget 4 --target-scored 100 --cohere-model command-a-03-2025 --allow-api --max-calls 600 --output-dir outputs/l1_loss_decomposition_best_selector_20260501T000000Z --resume`

No model-performance conclusion can be drawn because Cohere execution did not run.
