# Retry effect summary (validated from raw PAL metadata)

The `paired_summary.json` field `retry_enabled_count` reads as 0 despite retries running; **`pal_execution.pal_empty_code_retry_enabled`** in raw records shows enabled on all PAL runs. Retry rates below use raw metadata.

- Truth retry-enabled (from metadata): **300/300** (1.000)
- Truth retry ran: **16/300** (0.053)

## Conditional rates among retry-triggered rows

- Code present rate (when retry ran): **0.938**
- Parse OK rate (when retry ran): **0.938**
- Safety OK rate (when retry ran): **0.875**
- Exec OK rate (when retry ran): **0.750**
- Candidate strong rate (when retry ran): **0.750**

- Inferable selected-retry fixes / breaks when `pal_selected_candidate_source=pal_empty_code_retry`: **8 / 4** (net **4**)

## Accuracy conditional on retry

- PAL exact | retry ran (**n=16**): **0.5000**
- PAL exact | retry not ran (**n=284**): **0.8592**

## Contribution assessment
- Retry triggers on **~5.3%** of cases in this slice; even with positive net fixes on selected retries, aggregate movement remains modest.
- Most skips are **`seed_code_present_and_executable`** (expected under policy): retry is inherently rare globally.
