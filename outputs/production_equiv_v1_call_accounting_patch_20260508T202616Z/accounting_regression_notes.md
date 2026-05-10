# accounting regression notes
- Previous issue: per-case counters under-reported total run consumption in cap-truncated runs.
- Guardrail: run-level consumption is taken from global logical budget snapshot and optionally error inference.
- Expected invariant: `actual_cohere_calls_run_level >= actual_cohere_calls_completed_rows`.
- If strict cap triggers, `global_cap_reached=true` and `cap_error_count>0` should align.
