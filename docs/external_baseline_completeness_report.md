# External baseline completeness report

- Generated (UTC): `2026-04-15T23:49:46.038479+00:00`
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
| BEST-Route (`best_route_microsoft`) | blocked | adjacent | no | not_applicable | not_applicable |
| Compute-optimal TTS (`compute_optimal_tts`) | blocked | adjacent | no | not_applicable | not_applicable |
| When To Solve, When To Verify (`when_solve_when_verify`) | link_only | adjacent | no | not_applicable | not_applicable |
| Cascade routing (`cascade_routing`) | link_only | adjacent | no | not_applicable | not_applicable |
| MoB (`mob_majority_of_bests`) | link_only | adjacent | no | not_applicable | not_applicable |
| ReST-MCTS* (`rest_mcts`) | link_only | adjacent | no | not_applicable | not_applicable |
| MCTS-LLM (community) (`mcts_llm_community`) | link_only | adjacent | no | not_applicable | not_applicable |
| OpenR (`openr`) | link_only | adjacent | no | not_applicable | not_applicable |
| Tree-PLV (`tree_plv`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| PGTS (`pgts`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| Scaling Automated Process Verifiers (`scaling_automated_process_verifiers`) | discuss_only | adjacent | no | not_applicable | not_applicable |
| LLM Tree Search (Waterhorse) (`llm_tree_search_waterhorse`) | discuss_only | adjacent | no | not_applicable | not_applicable |

## Currently usable in comparisons
- s1 MODE A (`inference_only`) through `scripts/run_s1_budget_forcing_baseline.py`.
- TALE MODE A (`prompt_budgeting_inference_only`) through `scripts/run_tale_baseline.py`.
- L1 MODE A (`inference_only_adapter`) through `scripts/run_l1_baseline.py`.

## Partially usable
- s1 / TALE / L1 MODE B paths are adapter-reporting only and remain blocked unless official/full externally-produced outputs are provided via `official.results_path`.

## BEST-Route integration decision in this pass
- Status: `blocked` (explicit non-runnable integration record for now).
- Why blocked now: the upstream BEST-Route workflow is multi-stage and relies on external response-bank generation + reward-model scoring + router training that are not yet mapped to this repo's frontier/action substrate in a fair apples-to-apples protocol.
- What is required later: shared prompt set, shared candidate model set, normalized cost accounting, and a common scoring/evaluation interface before claiming comparability.

## Single next highest-priority baseline after this pass
- `when_solve_when_verify` (next adjacent baseline to move beyond link-only after this compute_optimal_tts pass).

## Machine-readable companion artifacts
- `outputs/external_baseline_completeness_summary.json`
- `outputs/external_baseline_completeness_summary.csv`
