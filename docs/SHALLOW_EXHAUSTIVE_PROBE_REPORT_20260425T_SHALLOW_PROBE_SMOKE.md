# SHALLOW_EXHAUSTIVE_PROBE_REPORT_20260425T_SHALLOW_PROBE_SMOKE

- Output directory: `outputs/shallow_exhaustive_probe_20260425T_SHALLOW_PROBE_SMOKE/`
- Dataset slice: strict_f3-loss cases where external_l1_max was correct (n=6).
- Mode: `dry-run (offline)`

## Explicit answers
1. Did exhaustive depth-2 exploration reduce absent-from-tree failures? **No or neutral** (delta=-0.3333).
2. Did exhaustive depth-3 exploration reduce absent-from-tree failures? **No or neutral** (delta=+0.0000).
3. Did the correct answer usually appear shallowly once breadth was forced, or remain absent?
   - Depth-2 first-appearance-after-forced-depth2 share: 0.0000
   - Depth-3 first-appearance-after-forced-depth3 share: 0.0000
4. Was the main limitation root diversity, depth-2 sibling coverage, depth-3 continuation, or final selection?
   - Use `paired_transition_summary.csv`, `coverage_depth_summary.csv`, and `budget_truncation_summary.csv` for this decomposition.
5. Should this become a new method, or remain only a diagnostic?
   - Recommendation: keep as **diagnostic-only** pending broader cross-dataset and cross-provider validation.

## Notes
- Budgets remain fixed at 4/6/8 (no budget inflation).
- Truncation is logged via `exhaustive_probe_budget_truncated` and unexpanded shallow-node lower bound.
