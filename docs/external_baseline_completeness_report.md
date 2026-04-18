# External baseline completeness report

- Generated (UTC): `2026-04-18T00:00:00+00:00`
- Scope: external baseline completeness for reviewer-defensible reporting in the fixed-budget next-step branch-allocation paper phase.

## Classification taxonomy
- `runnable_direct`
- `runnable_adjacent`
- `adapter_based`
- `import_validated`
- `mode_a_only`
- `mode_b_partial`
- `link_only`
- `discuss_only`
- `blocked`

## Required family status (paper-phase critical)

| Family | Canonical paper | Class | Status | Essential now? | Equivalence note |
|---|---|---|---|---|---|
| Q* deliberative planning | Q*: Improving Multi-step Reasoning for LLMs with Deliberative Planning | direct | discuss_only (implementation gap) | yes | Direct family target; currently not runnable in-repo. |
| Completion-aware PRM/verifier | Let's Verify Step by Step | adjacent | discuss_only | yes (adjacent) | Verifier/process-signal family, not direct branch-allocation control space. |
| Stop-vs-continue adaptive compute | Rational Metareasoning for Large Language Models | adjacent | discuss_only | yes (adjacent) | Value-of-computation framing; action space differs from frontier branch allocation. |
| Routing/cascade | Efficient Contextual LLM Cascades through Budget-Constrained Policy Learning | adjacent | import_validated / runnable_adjacent | optional unless scope broadens | Routing/cascade policy differs from branch expansion allocation. |
| Small-gap fixed-budget allocation | Best Arm Identification: A Unified Approach to Fixed Budget and Fixed Confidence | ingredient-adjacent boundary | discuss_only | yes (framing) | Strong near-tie framing, but not direct empirical LLM baseline stack. |

## Baseline status table

| Baseline | Category | Direct vs adjacent | Usable now | MODE A | MODE B |
|---|---|---|---|---|---|
| s1 (`s1_simple_test_time_scaling`) | mode_b_partial | direct | yes_mode_a | runnable | blocked_without_official_results_import |
| TALE (`tale_token_budget_aware_reasoning`) | mode_b_partial | adjacent | yes_mode_a | runnable | blocked_without_official_results_import |
| L1 (`l1_length_control_rl`) | mode_b_partial | direct | yes_mode_a | runnable | blocked_without_official_results_import |
| BEST-Route (`best_route_microsoft`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Compute-optimal TTS (`compute_optimal_tts`) | blocked | adjacent | no | not_applicable | not_applicable |
| When To Solve, When To Verify (`when_solve_when_verify`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Cascade routing (`cascade_routing`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| MoB (`mob_majority_of_bests`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| ReST-MCTS* (`rest_mcts`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| OpenR (`openr`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Tree-PLV (`tree_plv`) | discuss_only | adjacent/ingredient | no | not_applicable | not_applicable |
| PGTS (`pgts`) | discuss_only | adjacent/ingredient | no | not_applicable | not_applicable |
| Scaling Automated Process Verifiers (`scaling_automated_process_verifiers`) | discuss_only | adjacent/ingredient | no | not_applicable | not_applicable |
| Q* (`qstar_deliberative_planning`) | discuss_only | direct | no | not_applicable | not_applicable |
| Let's Verify Step by Step (`lets_verify_step_by_step`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| Rational Metareasoning (`rational_metareasoning_llm`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| Efficient Contextual LLM Cascades (`efficient_contextual_llm_cascades`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Best Arm Identification (`best_arm_identification_fixed_budget`) | discuss_only | ingredient-adjacent boundary | no | not_applicable | not_applicable |

## Notes
- Adjacent import-validated baselines are comparison-usable only with explicit adjacent-only claims.
- Discuss-only families are included intentionally for completeness and reviewer honesty; they are not represented as runnable.
- Near-tie disagreement slices should always mention the best-arm-identification framing family as ingredient/boundary context, not as direct empirical LLM baseline execution.
