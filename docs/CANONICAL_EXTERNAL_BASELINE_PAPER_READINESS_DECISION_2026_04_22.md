# Canonical external baseline paper-facing readiness decision package

- Generated (UTC): `2026-04-22T20:30:39.209741+00:00`
- Registry entries audited: `27`
- Runtime artifact bundle: `outputs/canonical_external_baseline_paper_readiness_decision_20260422T203039Z/`

## Canonical recommendation buckets
- **main_table_ready** (3): `l1_length_control_rl`, `s1_simple_test_time_scaling`, `tale_token_budget_aware_reasoning`
- **appendix_only** (8): `best_route_microsoft`, `cascade_routing`, `lets_verify_step_by_step`, `mob_majority_of_bests`, `openr`, `rest_mcts`, `tree_plv`, `when_solve_when_verify`
- **repo_only_not_paper_facing_yet** (5): `conformal_thinking_mode_a`, `efficient_contextual_llm_cascades`, `learning_how_hard_to_think_mode_a`, `qstar_style_adapter`, `training_free_difficulty_proxies_mode_a`
- **discuss_only** (11): `adaptive_test_time_compute_allocation_training_free_proxies`, `best_arm_identification_fixed_budget`, `compute_optimal_tts`, `conformal_thinking`, `learning_how_hard_to_think`, `llm_tree_search_waterhorse`, `mcts_llm_community`, `pgts`, `qstar_deliberative_planning`, `rational_metareasoning_llm`, `scaling_automated_process_verifiers`

## MODE A additions (explicit decision)
- `learning_how_hard_to_think_mode_a`: **repo_only_not_paper_facing_yet**.
- `training_free_difficulty_proxies_mode_a`: **repo_only_not_paper_facing_yet**.
- Rationale: both remain mixed/early and currently lack audited run artifacts on this repo state.

## Concise recommendation
- **Main table (safe now):** near-direct MODE A comparators with canonical matched ranking rows: `l1_length_control_rl`, `tale_token_budget_aware_reasoning`, `s1_simple_test_time_scaling`.
- **Appendix only:** auditable adjacent import-validated/runnable-adjacent comparators.
- **Keep out of empirical tables:** all `repo_only_not_paper_facing_yet` + `discuss_only` baselines.

## Strongest external baseline ranking (near-direct practical lane)
1. `l1_length_control_rl` (canonical ranking signal mean_accuracy: 0.497222)
2. `tale_token_budget_aware_reasoning` (canonical ranking signal mean_accuracy: 0.477778)
3. `s1_simple_test_time_scaling` (canonical ranking signal mean_accuracy: 0.433333)

## Files
- `docs/external_baseline_paper_readiness_decision_matrix.json`
- `docs/external_baseline_paper_readiness_decision_matrix.csv`
- `outputs/external_baseline_readiness/paper_readiness_decision_matrix.json`
- `outputs/external_baseline_readiness/paper_readiness_decision_matrix.csv`

## Audit evidence fields included per baseline
- registry status/class/blocker
- runner/config/doc existence
- status artifact pattern count and found artifact count
- adjacent bundle status (when present)
- canonical ranking signal (for near-direct mode-A comparators)
- explicit claim boundary and fairness label

This report is canonical for manuscript writing until superseded by a newer dated decision package.
