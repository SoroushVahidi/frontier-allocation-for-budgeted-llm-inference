# production_equiv_v1 50-case live failure diagnosis
## What went wrong
- Run is incomplete: 30/50 rows cap-hit after global logical cap reached.
- Only 20/50 rows completed; metadata present for 20/50 rows.
- Parsing failures are 31/50, inflated by incomplete rows.
- Reported calls (41) undercount inferred actual consumption (80).
## Validity of 16/50
- Treat 16/50 as invalid for final quality comparison because the run was truncated by cap and incomplete rows dominate outcomes.
## Call accounting diagnosis
- Dry-run estimate was 61 calls vs inferred live need around 102.5 (plus safety margin).
- Dry-run abstraction likely underestimates true internal call expansion in controller path; retry path alone does not explain full gap.
## Targeted retry diagnosis
- Planned retries from dry-run: 11; live triggered: 5; committed: 0.
- Retry commit gate appears strict or retry candidates low quality/unparseable in this sample; separate from cap truncation issue.
## Recommended next action
- Primary: fix_call_accounting_first.
- Suggested caps: 10-case smoke=30, full-50 rerun=132 (round up to 200 for safer full rerun).
## Caveats
- This diagnosis is no-API and based strictly on persisted artifacts from one truncated run.
