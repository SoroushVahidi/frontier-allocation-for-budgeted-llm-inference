# Semantic diversity controller diagnostic (20260428T185326Z)

## Status

Experimental / diagnostic only — **not** manuscript-grade evidence unless replicated and reviewed.

## Case volume

- **Loss / selected cases evaluated (unique example_ids in manifest):** 30
- **Per-method rows in per_case_results.csv:** 720

## Headline comparisons

- **Best accuracy (method_accuracy_summary.csv):** `direct_reserve_semantic_frontier_v2` at 0.8000

### vs strict_f3

- **Paired rows with delta > 0 vs strict_f3:** 110 (non-experimental methods excluded from paired_summary)
- **Any experimental method beat strict_f3 on at least one paired row:** yes

### vs external_l1_max

- **Paired deltas ≥ 0 vs external_l1_max:** 395 rows with numeric delta
- **Paired deltas > 0 vs external_l1_max:** 60

### Direct reserve / semantic maturation (directional)

- **Did direct reserve help?** Compare `direct_reserve_semantic_frontier_v1` vs `strict_f3` in `paired_summary.csv` and `method_accuracy_summary.csv`.
- **Did semantic minimum maturation help?** Compare `semantic_minimum_maturation_frontier_v1_d3` vs `strict_f3`.
- **Did combined semantic maturation + direct reserve help?** Compare `semantic_minimum_maturation_plus_direct_reserve_v1` vs baselines.

### Cost / action penalty

Mean actions_used by method (from per_case_results, diagnostic only):

- `direct_reserve_semantic_frontier_v2`: 2.33
- `external_l1_exact`: 1.01
- `external_l1_max`: 1.06
- `self_consistency_3`: 5.46
- `strict_f3`: 2.87
- `tot_beam_matched_budget`: 1.31
- `tot_bfs_matched_budget`: 1.28
- `tot_dfs_matched_budget`: 1.37

### Absent-from-tree / rescue

- **absent_from_tree_rescue_audit rows flagged as rescue:** 0
- Review `failure_taxonomy.csv` and `absent_from_tree_rescue_audit.csv` for bad seeding vs selection vs trace gaps.

### Failure taxonomy (post hoc)

- **Dominant category:** `trace_sparse_or_truncated` (count 479)

### Token / latency / cost proxy

- **Rows in token_cost_latency_summary.csv:** 720

## Artifacts

- Output directory: `outputs/semantic_diversity_controller_diagnostic_20260428T185326Z`
- Key files: `selected_cases.jsonl`, `per_case_results.csv`, `paired_summary.csv`, `method_accuracy_summary.csv`, `token_cost_latency_summary.csv`, `semantic_family_summary.csv`, `*_audit.csv`, `failure_taxonomy.csv`, `full_traces/` (if emitted), `manifest.json`, `candidate_next_steps.md`.

## Scale-up judgment

- **Larger run justified?** Only if paired deltas and taxonomy show a consistent, interpretable pattern; runs beyond 30 cases require explicit approval.
- **Manuscript change warranted?** Default **no** unless evidence is strong and reproducible.

