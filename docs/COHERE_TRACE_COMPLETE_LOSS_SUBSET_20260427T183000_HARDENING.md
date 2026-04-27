# COHERE_TRACE_COMPLETE_LOSS_SUBSET_20260427T183000_HARDENING

- Root cause category for `20260427T183000Z`: post-readiness runtime failure in inner rerun subprocess, not API-key readiness.
- Readiness status: `COHERE_API_KEY` present and smoke test succeeded.
- Inner crash signature: `AttributeError: 'NoneType' object has no attribute 'strip'` from controller answer normalization path.

## Script hardening changes

- `cohere_api_key_issue.md` is now written only for readiness failures (missing key or smoke-test failure).
- Added post-readiness failure path writing `run_failure_issue.md`.
- `run_failure_issue.md` now records:
  - `failure_stage`
  - exception type
  - traceback tail
  - selected/completed case counts
  - partial output files
  - exact rerun command
  - recommended fix
- Added NA-safe parsing helpers and applied them to:
  - seed/budget/method parsing
  - token/cost/latency summaries
  - present-not-selected counters
  - missing/empty trace handling
  - selected-case serialization defaults

## Validation

- `DEBUG4` run passed end-to-end with live readiness and trace outputs.
- `DEBUG10` run is launched with live readiness and writing outputs in progress.
