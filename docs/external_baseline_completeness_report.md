# External baseline completeness report

- Generated (UTC): `2026-04-22T01:40:21.469074+00:00`
- Scope: external baseline completeness for reviewer-defensible reporting.

## Canonical taxonomy (v1, paper-safe)

Machine-readable matrix (normalized fields): `outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json`.

### `status` (v1)
- `runnable_direct`
- `runnable_adjacent`
- `adapter_based`
- `import_validated`
- `discuss_only`
- `blocked`
- `broken_needs_repair`

### `control_equivalence` (v1)
- `direct`
- `near_direct`
- `adjacent`
- `ingredient_only`

### Legacy tokens (still appear in some CSV/JSON rows)
- `category` column values like `mode_b_partial` and `runnable_adjacent` are **legacy row labels**; prefer `status_v1_mode_a` / `status_v1_mode_b` for paper-facing claims.
- Per-baseline `outputs/external_baseline_completeness/*_status.json` may still say `runnable_adjacent` where v1 says `import_validated` (verified import protocol only).

## Baseline status table

| Baseline | legacy category | status_v1 (MODE A / primary) | status_v1 (MODE B) | control_v1 (A) | control_v1 (B) | Direct vs adjacent | Usable now | MODE A | MODE B |
|---|---|---|---|---|---|---|---|---|---|
| s1 (`s1_simple_test_time_scaling`) | mode_b_partial | adapter_based | import_validated | near_direct | adjacent | direct | yes_mode_a | runnable | blocked_without_official_results_import |
| TALE (`tale_token_budget_aware_reasoning`) | mode_b_partial | adapter_based | import_validated | near_direct | adjacent | adjacent | yes_mode_a | runnable | blocked_without_official_results_import |
| L1 (`l1_length_control_rl`) | mode_b_partial | adapter_based | import_validated | near_direct | adjacent | direct | yes_mode_a | runnable | blocked_without_official_results_import |
| BEST-Route (`best_route_microsoft`) | import_validated | import_validated | not_applicable | adjacent | not_applicable | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Compute-optimal TTS (`compute_optimal_tts`) | blocked | blocked | not_applicable | adjacent | not_applicable | adjacent | no | not_applicable | not_applicable |
| When To Solve, When To Verify (`when_solve_when_verify`) | import_validated | import_validated | not_applicable | adjacent | not_applicable | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Q* (`qstar_deliberative_planning`) | discuss_only | discuss_only | not_applicable | direct | not_applicable | direct | no | not_applicable | not_applicable |
| Cascade routing (`cascade_routing`) | runnable_adjacent | import_validated | not_applicable | adjacent | not_applicable | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| MoB (`mob_majority_of_bests`) | runnable_adjacent | import_validated | not_applicable | adjacent | not_applicable | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| ReST-MCTS* (`rest_mcts`) | runnable_adjacent | import_validated | not_applicable | adjacent | not_applicable | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| MCTS-LLM (community) (`mcts_llm_community`) | discuss_only | discuss_only | not_applicable | adjacent | not_applicable | adjacent | no | not_applicable | not_applicable |
| OpenR (`openr`) | runnable_adjacent | import_validated | not_applicable | adjacent | not_applicable | adjacent | yes_verified_import | adjacent_import_validator | not_applicable |
| Tree-PLV (`tree_plv`) | discuss_only | discuss_only | not_applicable | adjacent | not_applicable | adjacent | no | not_applicable | not_applicable |
| PGTS (`pgts`) | discuss_only | discuss_only | not_applicable | adjacent | not_applicable | adjacent | no | not_applicable | not_applicable |
| Scaling Automated Process Verifiers (`scaling_automated_process_verifiers`) | discuss_only | discuss_only | not_applicable | adjacent | not_applicable | adjacent | no | not_applicable | not_applicable |
| LLM Tree Search (Waterhorse) (`llm_tree_search_waterhorse`) | discuss_only | discuss_only | not_applicable | adjacent | not_applicable | adjacent | no | not_applicable | not_applicable |

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
- s1 / TALE / L1 MODE B paths are **import-validated** official/full reporting only: blocked at run time unless externally produced outputs are supplied via `official.results_path`, then checked by `verify_*_mode_b_import.py` (including `scripts/verify_l1_mode_b_import.py` for L1).

## BEST-Route integration decision in this pass
- Canonical v1 status: `import_validated` (verified import protocol; legacy JSON may still say `runnable_adjacent`).
- Interpretation: usable for adjacent comparisons only; not a direct control-space-equivalent reproduction.
- Guardrail: imported outputs must pass `scripts/verify_best_route_import.py` and be labeled `adjacent_only`.

## when_solve_when_verify integration decision in this pass
- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).
- Interpretation: usable for adjacent comparisons only; not a direct control-space-equivalent reproduction.
- Guardrail: imported outputs must pass `scripts/verify_when_solve_when_verify_import.py` and be labeled `adjacent_only`.

## Cascade Routing integration decision in this pass
- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_cascade_routing_import.py` and be labeled `adjacent_only`.

## MoB integration decision in this pass
- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_mob_import.py` and be labeled `adjacent_only`.

## ReST-MCTS integration decision in this pass
- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_rest_mcts_import.py` and be labeled `adjacent_only`.

## OpenR integration decision in this pass
- Canonical v1 status: `import_validated` (legacy JSON may still say `runnable_adjacent`).
- Interpretation: usable for adjacent comparisons only; not a direct in-repo full-stack reproduction.
- Guardrail: imported outputs must pass `scripts/verify_openr_import.py` and be labeled `adjacent_only`.

## Single next highest-priority baseline after this pass
- `mcts_llm_community` (v1 `discuss_only`; optional community reference — confirm paper mapping before any adapter work).

## Machine-readable companion artifacts
- `outputs/external_baseline_completeness_summary.json`
- `outputs/external_baseline_completeness_summary.csv`
