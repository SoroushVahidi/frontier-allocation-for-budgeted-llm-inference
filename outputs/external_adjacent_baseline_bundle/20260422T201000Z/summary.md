# External adjacent baseline bundle summary

Generated UTC: `2026-04-22T03:13:20.500370+00:00`
Run ID: `20260422T201000Z`

## Scope

This bundle aggregates manuscript-safe status for the strengthened **official adjacent** baselines:
- BEST-Route
- when_solve_when_verify
- Let's Verify Step by Step
- ReST-MCTS*
- Tree-PLV

These remain **adjacent** (not control-equivalent direct frontier-allocation baselines).

## Manuscript-safe matrix

| baseline id | official vs unofficial | status | control equivalence | current safest comparison scope | artifact-backed now | repo command available | paper-safe now | key limitation |
|---|---|---|---|---|---|---|---|---|
| best_route_microsoft | official | import_validated | adjacent | adjacent_only (Import-validated adjacent neighbor only; routing action space ≠ frontier expand/verify.) | yes | yes | yes | full_official_stack_still_heavy_even_after_two_lane_stabilization_partial_runnable_only |
| when_solve_when_verify | official | import_validated | adjacent | adjacent_only (Strict import validation for adjacent SC-vs-GenRM budget comparisons only.) | yes | yes | yes | adjacent_import_validated_only_not_direct_frontier_allocation_equivalent |
| lets_verify_step_by_step | official | discuss_only | ingredient_only | adjacent_only (Adjacent ingredient / completion-aware evidence family; not integrated as runnable stack.) | yes | no | yes | full_faithful_reproduction_out_of_scope_stable_partial_runnable_adjacent_contract_lane_only |
| tree_plv | official_paper_and_paper_cited_repo | import_validated | adjacent | adjacent_only | yes | yes | yes | full_faithful_reproduction_out_of_scope_partial_runnable_adjacent_contract_lane_only |
| rest_mcts | official | import_validated | adjacent | adjacent_only (Clone + import validation only; no full ReST-MCTS training reproduction claim.) | yes | yes | yes | full_self_training_reproduction_out_of_scope_stable_adjacent_contract_lane_only |

## Out of scope

- Full official upstream training/inference reproduction for all included adjacent baselines.
- Reframing adjacent baselines as direct control-equivalent branch-allocation methods.
- Taxonomy changes beyond conservative aggregation on top of current status artifacts.

## Backing artifacts

- `best_route_microsoft`: docs/best_route_integration.md, outputs/external_baseline_completeness/best_route_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json, outputs/best_route_adjacent_integration/20260422T004457Z/status.json
- `when_solve_when_verify`: docs/when_solve_when_verify_integration.md, outputs/external_baseline_completeness/when_solve_when_verify_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json
- `lets_verify_step_by_step`: docs/lets_verify_step_by_step_integration.md, outputs/external_baseline_completeness/lets_verify_step_by_step_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json, outputs/lets_verify_step_by_step_adjacent_integration/20260422T181500Z/status.json
- `tree_plv`: docs/tree_plv_integration.md, outputs/external_baseline_completeness/tree_plv_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json, outputs/tree_plv_adjacent_integration/20260422T200500Z/status.json
- `rest_mcts`: docs/rest_mcts_integration.md, outputs/external_baseline_completeness/rest_mcts_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json, outputs/rest_mcts_adjacent_integration/20260422T022200Z/status.json
