# INTERNAL_METHODS_VS_EXTERNAL_L1_MAX_RICH_FAILURE_TRACES_20260425T054200Z

## Requested questions
1. Matched examples by internal method: {'strict_f3': 35, 'strict_gate1_cap_k6': 35, 'strict_f3_anti_collapse_weak_v1': 11}
2. Internal-loss/external-win cases by internal method: {'strict_f3': 7, 'strict_gate1_cap_k6': 10, 'strict_f3_anti_collapse_weak_v1': 4}
3. Method with least losses: strict_f3
4. Best cost-normalized method (lower cost-per-correct): strict_f3
5. Most useful rich traces for controller design: strict_gate1_cap_k6 (largest loss pool with traces).
6. Failure pattern similarity/difference: see `failure_pattern_summary.csv` (absent-from-tree and nearest-path differences).
7. Absent-from-tree path proximity: see `path_proximity_summary.csv` (gold-in-tree, intermediate fraction, nearest depth/score).
8. Weak anti-collapse impact: compare strict_f3 vs strict_f3_anti_collapse_weak_v1 rows in `failure_pattern_summary.csv` and `path_proximity_summary.csv`.
9. Base method recommendation for next controller: strict_f3 (data-driven from observed loss rate).

## Completeness
See `incomplete_slices.csv` for any shortfall from 500 matched / 100 losses per method and estimated additional runs.
