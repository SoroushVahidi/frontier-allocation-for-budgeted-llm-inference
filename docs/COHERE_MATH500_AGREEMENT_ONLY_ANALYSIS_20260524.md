# COHERE_MATH500_AGREEMENT_ONLY_ANALYSIS_20260524

## 1. Executive summary
Official Cohere MATH-500 Scenario 4 confirms `agreement_only` (33.0%) is above pooled4/beta/C1d (~29.33%). The edge comes from external 2-of-3 defer regions, with meaningful but bounded regressions.

## 2. Data source and caveats
- Official Scenario 4 case table + selector replay only.
- Offline replay diagnostics; no new generation/API calls.
- C1d/C1a_t005/beta here remain diagnostic full-artifact replays, not fold-safe promotion evidence.

## 3. Exact agreement-only rule
See `agreement_only_rule_description.md` (generated from canonical policy in `experiments/support_aware_selector.py`).

## 4. Why agreement-only wins on official Cohere MATH
- recoveries vs pooled4: 20
- regressions vs pooled4: 9
- net recovery vs pooled4: 11
- wins in external-majority-against-frontier regions: 20

## 5. Pairwise recovery/regression analysis
- Pairwise CSVs: agreement vs pooled4/beta/C1d/sources are exported.

## 6. Failure/recovery casebooks
- Recovery and regression CSV + markdown casebooks exported.

## 7. Feature/pattern analysis
- Win/loss pattern tables exported with support, precision, regressions, and net benefit.

## 8. Mechanism diagnosis
- agreement_only accuracy: 0.3300
- pooled4 accuracy: 0.2933
- beta accuracy: 0.2933
- C1d accuracy: 0.2933

## 9. Official four-scenario workbench refresh
- Refreshed bundle: `outputs/failure_pattern_workbench_official4_20260524`
- Report: `docs/FAILURE_PATTERN_WORKBENCH_OFFICIAL4_20260524.md`

## 10. Candidate fixes
- Candidate A: agreement-only gate (test-first).
- Candidate B: hard near-peer fallback selector.
- Candidate C: pattern-specific action table.

## 11. Router-v2 implications
- Include agreement_only as action.
- Keep official and auxiliary domains separated in evaluation summaries.

## 12. Recommended next implementation query
Implement AG-01 as a conservative agreement-only gate with explicit regression guard, then run paired official4 replay against beta/C1d.

## 13. Safety confirmation
- offline only
- no API calls
- no active-job interference
- no commit/push