# External baseline completeness report

- Generated (UTC): `2026-04-17T01:31:15.027658+00:00`
- Scope: external baseline completeness for reviewer-defensible reporting.

## Classification taxonomy
- `runnable_direct`
- `runnable_adjacent`
- `mode_a_only`
- `mode_b_partial`
- `link_only`
- `discuss_only`
- `blocked`

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
| MCTS-LLM (community) (`mcts_llm_community`) | link_only | adjacent | no | not_applicable | not_applicable |
| OpenR (`openr`) | runnable_adjacent | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Tree-PLV (`tree_plv`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| PGTS (`pgts`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| Scaling Automated Process Verifiers (`scaling_automated_process_verifiers`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| LLM Tree Search (Waterhorse) (`llm_tree_search_waterhorse`) | discuss_only | adjacent | no | not_applicable | not_applicable |

## Currently usable in comparisons
- s1 MODE A (`inference_only`) through `scripts/run_s1_budget_forcing_baseline.py`.
- TALE MODE A (`prompt_budgeting_inference_only`) through `scripts/run_tale_baseline.py`.
- L1 MODE A (`inference_only_adapter`) through `scripts/run_l1_baseline.py`.
- BEST-Route adjacent import path through `scripts/verify_best_route_import.py` (strict validator; adjacent-only claims).
- when_solve_when_verify adjacent import path through `scripts/verify_when_solve_when_verify_import.py` (strict validator; adjacent-only claims).
- Cascade Routing adjacent import path through `scripts/verify_cascade_routing_import.py` (strict validator; adjacent-only claims).
- MoB adjacent import path through `scripts/verify_mob_import.py` (strict validator; adjacent-only claims).
- ReST-MCTS adjacent import path through `scripts/verify_rest_mcts_import.py` (strict validator; adjacent-only claims).
- OpenR adjacent import path through `scripts/verify_openr_import.py` (strict validator; adjacent-only claims).

## Partially usable
- s1 / TALE / L1 MODE B paths are adapter-reporting only and remain blocked unless official/full externally-produced outputs are provided via `official.results_path`.

## BEST-Route integration decision in this pass
- Status: `runnable_adjacent` (verified import protocol available).
- Interpretation: usable for adjacent comparisons only; not a direct control-space-equivalent reproduction.
- Guardrail: imported outputs must pass `scripts/verify_best_route_import.py` and be labeled `adjacent_only`.

## when_solve_when_verify integration decision in this pass
- Status: `runnable_adjacent` (verified import protocol available).
- Interpretation: usable for adjacent comparisons only; not a direct control-space-equivalent reproduction.
- Guardrail: imported outputs must pass `scripts/verify_when_solve_when_verify_import.py` and be labeled `adjacent_only`.

## Cascade Routing integration decision in this pass
- Status: `runnable_adjacent` (verified import protocol available).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_cascade_routing_import.py` and be labeled `adjacent_only`.

## MoB integration decision in this pass
- Status: `runnable_adjacent` (verified import protocol available).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_mob_import.py` and be labeled `adjacent_only`.

## ReST-MCTS integration decision in this pass
- Status: `runnable_adjacent` (verified import protocol available).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_rest_mcts_import.py` and be labeled `adjacent_only`.

## OpenR integration decision in this pass
- Status: `runnable_adjacent` (verified import protocol available).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_openr_import.py` and be labeled `adjacent_only`.

## Single next highest-priority baseline after this pass
- `mcts_llm_community` (next high-priority baseline still at link-only after unblocking OpenR).

## Machine-readable companion artifacts
- `outputs/external_baseline_completeness_summary.json`
- `outputs/external_baseline_completeness_summary.csv`
