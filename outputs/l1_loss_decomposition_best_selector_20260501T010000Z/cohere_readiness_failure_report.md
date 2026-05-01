# Cohere readiness failure report

- failure_type: `incomplete_artifacts`
- model_requested: `command-a-03-2025`
- sdk_import_status: `ok`
- COHERE_API_KEY present: `True`
- sanitized_error_message: `Cohere readiness passed but full paired 100-case selector artifacts are not yet implemented in this wrapper.`

- rerun_command: `python scripts/run_l1_loss_decomposition_for_best_selector.py --timestamp 20260501T010000Z --provider cohere --dataset openai/gsm8k --split test --seed 20260501 --budget 4 --target-scored 100 --cohere-model command-a-03-2025 --allow-api --max-calls 600 --output-dir outputs/l1_loss_decomposition_best_selector_20260501T010000Z --resume`

No model-performance conclusion can be drawn because Cohere execution did not run.
