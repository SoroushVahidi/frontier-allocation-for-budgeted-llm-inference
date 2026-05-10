# Internal Current Baseline Notes

## Implementation map
- `S1BudgetForcingController` in `experiments/controllers.py`:
  - Existing method id: `external_s1_budget_forcing`
  - Behavior: branch done-state reopen + `Wait (forced-continue)` with `num_ignore_think_end` and `min_thinking_steps`.
- `TALEPromptBudgetingController` in `experiments/controllers.py`:
  - Existing method id: `external_tale_prompt_budgeting`
  - Behavior: char-length token budget estimate + budget prompt injection + action-budget conversion.
- `L1LengthControlController` in `experiments/controllers.py`:
  - Existing method ids: `external_l1_exact`, `external_l1_max`
  - Behavior: length-controlled prompt instruction (exact or max token budget).

## Registration points
- Runtime registration: `experiments/frontier_matrix_core.py` (`build_frontier_strategies`).
- Evaluation method registry: `scripts/run_cohere_real_model_cost_normalized_validation.py` (`METHODS`).

## Existing caveats (pre-change)
- S1/TALE/L1 are adapter-style implementations under repository action-budget + local harness.
- `best_external` is an oracle aggregation from precomputed columns, not a runnable single method.
