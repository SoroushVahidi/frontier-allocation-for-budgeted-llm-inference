# PAL execution-pool offline validation (2026-05-06)

- total_rows=600
- pal_rows_seen=300
- pal_rows_changed=0
- candidates_added=0

## Dominant signature check
- external_only `gold_absent_cb|overlay_cb`: 7 -> 7 (unchanged)
- both_wrong `gold_absent_cb|overlay_cb`: 19 -> 19 (unchanged)

## Headline exact rates
- external exact: 0.8133 (unchanged)
- PAL exact: 0.84 (unchanged)

## Conclusion
- execution-pool merge does not reduce dominant failure mode on this 300-case artifact.
- API calls: none (local files only)
