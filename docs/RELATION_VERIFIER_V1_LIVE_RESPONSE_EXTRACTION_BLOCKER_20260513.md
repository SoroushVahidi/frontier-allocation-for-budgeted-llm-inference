# Relation Verifier V1 Live Response Extraction Blocker

## Status

`relation_verifier_v1` engineering work is preserved, but the live Cohere diagnostics are not scientific evidence yet.

## What Happened

The first live attempt at `outputs/relation_verifier_v1_live_20cases_20260513T011800Z` failed before model output because the runner called the Cohere SDK with the wrong request shape. The failing path used `messages=[...]`, which produced a local SDK error.

The second corrected live attempt at `outputs/relation_verifier_v1_live_20cases_20260513T012431Z` fixed the call shape and reached the API boundary successfully for all 20 cases, but it captured `0/20` non-empty `raw_response` values. That run therefore produced `json_parse_failed=20` and no usable verifier labels.

## Exact Diagnosis

The installed local SDK is `cohere 6.1.0`. In this version, `Client.chat(message=...)` returns a `NonStreamedChatResponse` object whose primary reply payload is `response.text`. The prior runner only attempted to read `response.message.content[0].text`, which is not the primary non-streaming shape for this installed SDK.

That mismatch explains the second live artifact:

- the API call boundary succeeded for all 20 requests
- no exception was raised
- the runner looked in the wrong field
- every captured `raw_response` was an empty string
- downstream JSON parsing failed on all 20 rows

## Interpretation

Neither live run is scientific evidence:

- The first run failed locally before any model output.
- The second run completed the call boundary but did not capture model text, so semantic verifier behavior was not observed.

Do not claim that `relation_verifier_v1` works semantically. Do not claim that it fails semantically. The current blocker is response extraction, not verifier-method quality.

## Next Step

The runner now includes a robust `_extract_cohere_text(response)` helper that checks the installed SDK's `response.text` field first and then falls back across other plausible shapes:

- `response.text`
- `response.message`
- `response.message.content`
- `response.content`
- `response.generations[0].text`
- `response.response.text`
- dict-like `text`
- dict-like `message.content`
- dict-like `generations[0].text`

The runner also now records extraction diagnostics in raw-response logging without leaking prompt text:

- `response_type`
- `response_public_attrs`
- `response_repr` truncated safely
- `extraction_source`
- `extraction_issue`

No-API tests were added for these response shapes and for the empty-response failure mode. The existing live outputs remain invalid evidence because they were produced before this extraction fix was present, and no corrected live rerun has been performed yet.

## DO NOT RUN

Future live command, only after explicit approval:

```bash
python3 scripts/run_relation_verifier_v1.py \
  --provider-requests /tmp/relation_verifier_v1_preflight_fixed/provider_requests_dry_run.jsonl \
  --casebook docs/project_handoff_20260510/exhaustive_failure_audit/gold_absent_subpattern_analysis_20260510.csv \
  --out-dir outputs/relation_verifier_v1_live_20cases_$(date -u +%Y%m%dT%H%M%SZ) \
  --allow-api \
  --model command-r-plus-08-2024 \
  --max-tokens 1024 \
  --temperature 0.0
```
