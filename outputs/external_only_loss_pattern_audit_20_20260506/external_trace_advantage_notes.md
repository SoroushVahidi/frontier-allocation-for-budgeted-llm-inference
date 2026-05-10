# External trace advantage notes

- External-only losses analyzed: 20
- Cases flagged `L1_P9_external_trace_advantage_unknown`: 10
- Interpretation: these cases usually show PAL candidate pool missing the gold-equivalent answer while external path still finds it; root cause remains underspecified without richer reasoning traces.

## PAL-only wins comparison (if available)
- PAL-only wins rows: 44
- external-only `gold_absent` rate vs PAL-only: 0.700 vs 0.000
- external-only `present_not_selected` rate vs PAL-only: 0.250 vs 0.000
- external-only `pal_exec_ok` rate vs PAL-only: 0.750 vs 1.000
