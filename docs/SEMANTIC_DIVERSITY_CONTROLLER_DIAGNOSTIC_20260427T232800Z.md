# Semantic diversity controller diagnostic (20260427T232800Z)

## Status

Experimental / diagnostic only — **not** manuscript-grade evidence unless replicated and reviewed.

## Case volume

- **Loss / selected cases evaluated (unique example_ids in manifest):** 9
- **Per-method rows in per_case_results.csv:** 162

## Headline comparisons

- **Best accuracy (method_accuracy_summary.csv):** `direct_reserve_semantic_frontier_v1` at 0.7407

### vs strict_f3

- **Paired rows with delta > 0 vs strict_f3:** 34 (non-experimental methods excluded from paired_summary)
- **Any experimental method beat strict_f3 on at least one paired row:** yes

### vs external_l1_max

- **Paired deltas ≥ 0 vs external_l1_max:** 78 rows with numeric delta
- **Paired deltas > 0 vs external_l1_max:** 13

### Direct reserve / semantic maturation (directional)

- **Did direct reserve help?** Compare `direct_reserve_semantic_frontier_v1` vs `strict_f3` in `paired_summary.csv` and `method_accuracy_summary.csv`.
- **Did semantic minimum maturation help?** Compare `semantic_minimum_maturation_frontier_v1_d3` vs `strict_f3`.
- **Did combined semantic maturation + direct reserve help?** Compare `semantic_minimum_maturation_plus_direct_reserve_v1` vs baselines.

### Cost / action penalty

Mean actions_used by method (from per_case_results, diagnostic only):

- `branching_necessity_gate_v1`: 3.11
- `direct_reserve_semantic_frontier_v1`: 4.56
- `external_l1_max`: 1.00
- `semantic_minimum_maturation_frontier_v1_d3`: 2.85
- `semantic_minimum_maturation_plus_direct_reserve_v1`: 4.67
- `strict_f3`: 3.26

### Absent-from-tree / rescue

- **absent_from_tree_rescue_audit rows flagged as rescue:** 0
- Review `failure_taxonomy.csv` and `absent_from_tree_rescue_audit.csv` for bad seeding vs selection vs trace gaps.

### Failure taxonomy (post hoc)

- **Dominant category:** `unknown_unclassified` (count 81)

### Token / latency / cost proxy

- **Rows in token_cost_latency_summary.csv:** 162

## Artifacts

- Output directory: `outputs/semantic_diversity_controller_diagnostic_20260427T232800Z`
- Key files: `selected_cases.jsonl`, `per_case_results.csv`, `paired_summary.csv`, `method_accuracy_summary.csv`, `token_cost_latency_summary.csv`, `semantic_family_summary.csv`, `*_audit.csv`, `failure_taxonomy.csv`, `full_traces/` (if emitted), `manifest.json`, `candidate_next_steps.md`.

## Scale-up judgment

- **Larger run justified?** Only if paired deltas and taxonomy show a consistent, interpretable pattern; runs beyond 30 cases require explicit approval.
- **Manuscript change warranted?** Default **no** unless evidence is strong and reproducible.

