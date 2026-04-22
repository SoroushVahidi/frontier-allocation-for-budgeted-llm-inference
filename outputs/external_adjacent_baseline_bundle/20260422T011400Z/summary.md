# External adjacent baseline bundle summary

Generated UTC: `2026-04-22T01:14:54.231743+00:00`
Run ID: `20260422T011400Z`

## Scope

This bundle aggregates manuscript-safe status for the strengthened **official adjacent** baselines:
- BEST-Route
- when_solve_when_verify
- ReST-MCTS*

These remain **adjacent** (not control-equivalent direct frontier-allocation baselines).

## Manuscript-safe matrix

| baseline id | official vs unofficial | status | control equivalence | current safest comparison scope | artifact-backed now | repo command available | paper-safe now | key limitation |
|---|---|---|---|---|---|---|---|---|
| best_route_microsoft | official | import_validated | adjacent | adjacent_only (Import-validated adjacent neighbor only; routing action space ≠ frontier expand/verify.) | yes | yes | yes | full_official_stack_still_heavy_even_after_two_lane_stabilization_partial_runnable_only |
| when_solve_when_verify | official | import_validated | adjacent | adjacent_only (Strict import validation for adjacent SC-vs-GenRM budget comparisons only.) | yes | yes | yes | adjacent_import_validated_only_not_direct_frontier_allocation_equivalent |
| rest_mcts | official | import_validated | adjacent | adjacent_only (Clone + import validation only; no full ReST-MCTS training reproduction claim.) | yes | yes | yes | full_self_training_heavy_partial_runnable_official_search_eval_only |

## Out of scope

- Full official upstream training/inference reproduction for all three baselines.
- Reframing adjacent baselines as direct control-equivalent branch-allocation methods.
- Taxonomy changes beyond conservative aggregation on top of current status artifacts.

## Backing artifacts

- `best_route_microsoft`: docs/best_route_integration.md, outputs/external_baseline_completeness/best_route_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json, outputs/best_route_adjacent_integration/20260422T004457Z/status.json
- `when_solve_when_verify`: docs/when_solve_when_verify_integration.md, outputs/external_baseline_completeness/when_solve_when_verify_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json
- `rest_mcts`: docs/rest_mcts_integration.md, outputs/external_baseline_completeness/rest_mcts_status.json, outputs/baseline_repair_and_status_audit_20260420T225833Z/baseline_status_matrix.json
