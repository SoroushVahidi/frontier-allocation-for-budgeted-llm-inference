# External baseline paper-readiness decision package

- Generated (UTC): `2026-04-22T20:05:13.868431+00:00`
- Scope: full audit of all current external baseline entries in `configs/external_baselines_registry.json`.
- Decision labels: `main_table_ready`, `appendix_only`, `repo_only_not_paper_facing_yet`, `discuss_only`.

## Canonical decisions (conservative)
- **main_table_ready** (3): `l1_length_control_rl`, `s1_simple_test_time_scaling`, `tale_token_budget_aware_reasoning`
- **appendix_only** (9): `best_route_microsoft`, `cascade_routing`, `efficient_contextual_llm_cascades`, `lets_verify_step_by_step`, `mob_majority_of_bests`, `openr`, `rest_mcts`, `tree_plv`, `when_solve_when_verify`
- **repo_only_not_paper_facing_yet** (4): `conformal_thinking_mode_a`, `learning_how_hard_to_think_mode_a`, `qstar_style_adapter`, `training_free_difficulty_proxies_mode_a`
- **discuss_only** (11): `adaptive_test_time_compute_allocation_training_free_proxies`, `best_arm_identification_fixed_budget`, `compute_optimal_tts`, `conformal_thinking`, `learning_how_hard_to_think`, `llm_tree_search_waterhorse`, `mcts_llm_community`, `pgts`, `qstar_deliberative_planning`, `rational_metareasoning_llm`, `scaling_automated_process_verifiers`

## MODE A additions (explicit decision)
- `learning_how_hard_to_think_mode_a`: **repo_only_not_paper_facing_yet** (no auditable run artifacts found; keep caveated).
- `training_free_difficulty_proxies_mode_a`: **repo_only_not_paper_facing_yet** (no auditable run artifacts found; query-level control mismatch).
- Conservative manuscript guidance now: keep both out of manuscript-facing empirical tables in this repository state.

## Strongest baseline ranking for this paper state

### Direct / near-direct practical comparators
1. `l1_length_control_rl` (canonical ranking signal mean_accuracy: 0.497222)
2. `tale_token_budget_aware_reasoning` (canonical ranking signal mean_accuracy: 0.477778)
3. `s1_simple_test_time_scaling` (canonical ranking signal mean_accuracy: 0.433333)

### Adjacent but reviewer-useful comparators
- `tree_plv`, `rest_mcts`, `lets_verify_step_by_step`, `best_route_microsoft`, `when_solve_when_verify`, `cascade_routing`, `mob_majority_of_bests`, `openr`.

### Framing-only / discuss-only references
- `qstar_deliberative_planning`, `rational_metareasoning_llm`, `best_arm_identification_fixed_budget`, `pgts`, `scaling_automated_process_verifiers`, `compute_optimal_tts`, `mcts_llm_community`, `llm_tree_search_waterhorse`, `learning_how_hard_to_think`, `adaptive_test_time_compute_allocation_training_free_proxies`.

## Machine-readable matrix
- `docs/external_baseline_paper_readiness_decision_matrix.json`
- `docs/external_baseline_paper_readiness_decision_matrix.csv`
- (runtime copy) `outputs/external_baseline_readiness/paper_readiness_decision_matrix.json`
- (runtime copy) `outputs/external_baseline_readiness/paper_readiness_decision_matrix.csv`

## Concise recommendation
- **Main table (safe now):** `l1_length_control_rl`, `tale_token_budget_aware_reasoning`, `s1_simple_test_time_scaling` (MODE A adapter rows only).
- **Appendix only:** adjacent import-validated/partial-runnable baselines listed above.
- **Keep out of empirical tables for now:** all `repo_only_not_paper_facing_yet` and `discuss_only` rows (including both new MODE A additions).

## Evidence fields audited per baseline
- registry entry
- integration docs / runners / configs when present
- status artifact presence
- adjacent bundle integration status (when available)
- canonical ranking signal availability (near-direct MODE A families)
