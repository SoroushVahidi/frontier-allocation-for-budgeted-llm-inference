# Commands / assumptions / caveats

- Command: `scripts/run_completion_aware_decision_experiment.py --run-id worst_real_failure_observability_20260418T015924Z --output-run-id completion_aware_decision_eval_20260418`
- This pass is bounded to one observability-enabled worst-failure run and does not retrain canonical multistep models.
- `multistep_k3_current` is included as an external reference from the canonical validation aggregate file.
- Completion signal is explicit/rule-based and conservative: absent evidence defaults to zero evidence.
- Correctness by branch answer is only computed when normalized branch answers are recoverable.
